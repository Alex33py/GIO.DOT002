#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OKX Connector для GIO Crypto Bot
REST API + WebSocket streams
"""

import asyncio
import aiohttp
import websockets
import json
import hmac
import base64
import time  # ← ДОБАВЛЕНО В НАЧАЛО!
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from config.settings import logger
from utils.validators import DataValidator


class OKXConnector:
    """
    Полнофункциональный коннектор к OKX
    Объединяет REST API и WebSocket streams
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        passphrase: Optional[str] = None,
        symbols: Optional[List[str]] = None,
        enable_websocket: bool = True,
        demo_mode: bool = False,
    ):
        """
        Инициализация OKX коннектора

        Args:
            api_key: API ключ OKX (опционально)
            api_secret: API секрет OKX
            passphrase: API passphrase OKX
            symbols: Список пар для WebSocket ['BTC-USDT', 'ETH-USDT']
            enable_websocket: Включить WebSocket потоки
            demo_mode: Demo trading mode (default: False)
        """
        # REST API настройки
        self.base_url = "https://www.okx.com"
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.session = None
        self.is_initialized = False
        self.demo_mode = demo_mode

        # WebSocket настройки
        self.enable_websocket = enable_websocket
        if demo_mode:
            self.ws_public = "wss://wspap.okx.com:8443/ws/v5/public"
            self.ws_private = "wss://wspap.okx.com:8443/ws/v5/private"
        else:
            self.ws_public = "wss://ws.okx.com:8443/ws/v5/public"
            self.ws_private = "wss://ws.okx.com:8443/ws/v5/private"

        self.symbols = symbols or []
        self.ws_connections: Dict[str, Any] = {}
        self.is_ws_running = False

        # WebSocket callbacks
        self.callbacks: Dict[str, Callable] = {}

        # Orderbook cache для WebSocket
        self.orderbooks: Dict[str, Dict] = {}
        self.orderbook_initialized: Dict[str, bool] = {}
        self.last_pressure_log: Dict[str, float] = {}
        self.orderbook_pressure: Dict[str, float] = {}
        self.orderbook_data: Dict[str, Dict] = {}
        self.large_trades = []  # Список крупных трейдов
        self.large_trade_threshold = 50000  # $50k минимум
        # CVD tracking (НОВОЕ!)
        self.cvd = {}  # {symbol: cumulative_delta}
        self.cvd_window = 300  # 5 минут window для CVD
        self.cvd_trades = {}  # {symbol: [(timestamp, delta), ...]}


        # Statistics
        self.stats = {
            "rest_requests": 0,
            "rest_errors": 0,
            "ws_messages": 0,
            "ws_orderbook_updates": 0,
            "ws_trade_updates": 0,
            "ws_errors": 0,
        }

        logger.info("✅ OKXConnector инициализирован")



    async def initialize(self) -> bool:
        """
        Инициализация REST сессии и WebSocket

        Returns:
            True если успешно
        """
        try:
            # 1. Инициализация REST API
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )

            # Проверка подключения
            server_time = await self.get_server_time()

            if server_time:
                self.is_initialized = True
                logger.info("✅ OKX REST API подключен")
            else:
                logger.error("❌ Не удалось подключиться к OKX REST API")
                return False

            # 2. Инициализация WebSocket (опционально)
            if self.enable_websocket and self.symbols:
                logger.info(
                    f"🔌 Запуск OKX WebSocket для {len(self.symbols)} символов..."
                )
                # WebSocket запустится в методе start()
            else:
                logger.info("ℹ️ OKX WebSocket отключен")

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации OKX: {e}")
            return False

    def _calculate_orderbook_pressure(self, symbol: str, bids: list, asks: list) -> float:
        """Рассчитывает давление orderbook для символа"""
        try:
            if not bids or not asks:
                return 0.0

            total_bids = sum([float(bid[1]) for bid in bids[:20]])
            total_asks = sum([float(ask[1]) for ask in asks[:20]])

            if total_bids + total_asks == 0:
                return 0.0

            buy_pressure = (total_bids / (total_bids + total_asks)) * 100
            pressure = (buy_pressure - 50) * 2

            return round(pressure, 2)

        except Exception as e:
            logger.error(f"❌ _calculate_orderbook_pressure error {symbol}: {e}")
            return 0.0


    async def _handle_trade_for_cvd(self, trade_data: Dict):
        """Обрабатывает трейды для расчёта CVD"""
        try:
            symbol = trade_data.get('instId', '').replace('-', '')
            if symbol not in self.symbols:
                return

            side = trade_data.get('side')
            size = float(trade_data.get('sz', 0))
            timestamp = int(trade_data.get('ts', 0)) / 1000

            delta = size if side == 'buy' else -size

            if symbol not in self.cvd:
                self.cvd[symbol] = 0
                self.cvd_trades[symbol] = []

            self.cvd_trades[symbol].append((timestamp, delta))

            cutoff_time = timestamp - self.cvd_window
            self.cvd_trades[symbol] = [
                (ts, d) for ts, d in self.cvd_trades[symbol]
                if ts > cutoff_time
            ]

            self.cvd[symbol] = sum(d for ts, d in self.cvd_trades[symbol])
            logger.debug(f"📊 OKX CVD updated {symbol}: {self.cvd[symbol]:.2f}")

        except Exception as e:
            logger.error(f"❌ OKX CVD calculation error: {e}")


    def get_cvd(self, symbol: str) -> float:
        """Возвращает текущий CVD для символа"""
        return self.cvd.get(symbol, 0)


    def get_cvd_percentage(self, symbol: str) -> float:
        """Возвращает CVD в процентах от общего объёма"""
        try:
            if symbol not in self.cvd_trades or not self.cvd_trades[symbol]:
                return 0

            total_volume = sum(abs(d) for ts, d in self.cvd_trades[symbol])

            if total_volume == 0:
                return 0

            cvd_pct = (self.cvd[symbol] / total_volume) * 100
            return cvd_pct

        except Exception as e:
            logger.error(f"❌ OKX CVD percentage error: {e}")
            return 0


    def set_callbacks(self, callbacks: Dict[str, Callable]):
        """Установить callback функции для WebSocket"""
        self.callbacks = callbacks
        logger.info(f"✅ Установлено {len(callbacks)} callbacks для OKX WebSocket")



    def get_cvd_percentage(self, symbol: str) -> float:
        """
        Возвращает CVD в процентах от общего объёма

        Args:
            symbol: Торговая пара

        Returns:
            float: CVD в процентах (-100 до +100)
        """
        try:
            if symbol not in self.cvd_trades or not self.cvd_trades[symbol]:
                return 0

            # Сумма всех трейдов (по модулю)
            total_volume = sum(abs(d) for ts, d in self.cvd_trades[symbol])

            if total_volume == 0:
                return 0

            # CVD в процентах
            cvd_pct = (self.cvd[symbol] / total_volume) * 100
            return cvd_pct

        except Exception as e:
            logger.error(f"❌ OKX CVD percentage error: {e}")
            return 0


            # Суммируем объёмы (первые 20 уровней)
            total_bids = sum([float(bid[1]) for bid in bids[:20]])
            total_asks = sum([float(ask[1]) for ask in asks[:20]])

            if total_bids + total_asks == 0:
                return 0.0

            # Рассчитываем buy pressure (0-100%)
            buy_pressure = (total_bids / (total_bids + total_asks)) * 100

            # Нормализуем от -100 до +100
            # 50% = 0 (neutral), 100% = +100 (strong buy), 0% = -100 (strong sell)
            pressure = (buy_pressure - 50) * 2

            return round(pressure, 2)

        except Exception as e:
            logger.error(f"❌ _calculate_orderbook_pressure error {symbol}: {e}")
            return 0.0


    def set_callbacks(self, callbacks: Dict[str, Callable]):
        """
        Установить callback функции для WebSocket

        Args:
            callbacks: {
                'on_orderbook_update': func,
                'on_trade': func,
            }
        """
        self.callbacks = callbacks
        logger.info(f"✅ Установлено {len(callbacks)} callbacks для OKX WebSocket")

    # ===========================================
    # AUTHENTICATION
    # ===========================================

    def _generate_signature(
        self, timestamp: str, method: str, request_path: str, body: str = ""
    ) -> str:
        """
        Генерация подписи для OKX API

        Args:
            timestamp: Unix timestamp в секундах
            method: HTTP метод (GET, POST)
            request_path: API endpoint
            body: Request body (для POST)

        Returns:
            Base64-encoded HMAC SHA256 signature
        """
        message = timestamp + method + request_path + body
        mac = hmac.new(
            bytes(self.api_secret, encoding="utf8"),
            bytes(message, encoding="utf-8"),
            digestmod="sha256",
        )
        return base64.b64encode(mac.digest()).decode()

    def _get_headers(
        self, method: str, request_path: str, body: str = ""
    ) -> Dict[str, str]:
        """
        Получить headers для authenticated запроса

        Args:
            method: HTTP метод
            request_path: API endpoint
            body: Request body

        Returns:
            Dict с headers
        """
        timestamp = datetime.utcnow().isoformat(timespec="milliseconds") + "Z"
        signature = self._generate_signature(timestamp, method, request_path, body)

        headers = {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }

        if self.demo_mode:
            headers["x-simulated-trading"] = "1"

        return headers

    # ===========================================
    # REST API METHODS
    # ===========================================

    async def get_server_time(self) -> Optional[int]:
        """Получить время сервера OKX"""
        url = f"{self.base_url}/api/v5/public/time"

        try:
            self.stats["rest_requests"] += 1
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if data["code"] == "0":
                        return int(data["data"][0]["ts"])
                    else:
                        logger.error(f"❌ OKX server time ошибка: {data['msg']}")
                        self.stats["rest_errors"] += 1
                        return None
                else:
                    logger.error(f"❌ OKX server time HTTP ошибка: {response.status}")
                    self.stats["rest_errors"] += 1
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка get_server_time: {e}")
            self.stats["rest_errors"] += 1
            return None

    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Получить 24h ticker статистику

        Args:
            symbol: Торговая пара (BTC-USDT)

        Returns:
            Dict с данными ticker
        """
        url = f"{self.base_url}/api/v5/market/ticker"
        params = {"instId": symbol}

        try:
            self.stats["rest_requests"] += 1
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    if data["code"] == "0" and len(data["data"]) > 0:
                        tick = data["data"][0]

                        ticker = {
                            "symbol": tick["instId"],
                            "last_price": float(tick["last"]),
                            "high_24h": float(tick["high24h"]),
                            "low_24h": float(tick["low24h"]),
                            "volume_24h": float(tick["vol24h"]),
                            "volume_currency_24h": float(tick["volCcy24h"]),
                            "bid_price": float(tick["bidPx"]),
                            "ask_price": float(tick["askPx"]),
                            "open_price": float(tick["open24h"]),
                            "timestamp": int(tick["ts"]),
                        }

                        if DataValidator.validate_price(ticker["last_price"], symbol):
                            return ticker
                        else:
                            logger.warning(f"⚠️ Невалидная цена в ticker {symbol}")
                            return None
                    else:
                        logger.error(
                            f"❌ OKX ticker error: {data.get('msg', 'Unknown')}"
                        )
                        self.stats["rest_errors"] += 1
                        return None

                else:
                    logger.error(f"❌ OKX Ticker HTTP ошибка {response.status}")
                    self.stats["rest_errors"] += 1
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка get_ticker: {e}")
            self.stats["rest_errors"] += 1
            return None

    async def get_orderbook(self, symbol: str, depth: int = 100) -> Optional[Dict]:
        """
        Получить L2 orderbook через REST API

        Args:
            symbol: Торговая пара (BTC-USDT)
            depth: Глубина orderbook (1-400)

        Returns:
            Dict с данными orderbook
        """
        url = f"{self.base_url}/api/v5/market/books"

        # OKX limits: 1, 5, 10, 20, 50, 100, 200, 400
        valid_limits = [1, 5, 10, 20, 50, 100, 200, 400]
        depth = min(valid_limits, key=lambda x: abs(x - depth))

        params = {"instId": symbol, "sz": depth}

        try:
            self.stats["rest_requests"] += 1
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    if data["code"] == "0" and len(data["data"]) > 0:
                        book = data["data"][0]

                        orderbook = {
                            "symbol": symbol,
                            "timestamp": int(book["ts"]),
                            "bids": [
                                [float(price), float(qty), int(orders)]
                                for price, qty, _, orders in book["bids"]
                            ],
                            "asks": [
                                [float(price), float(qty), int(orders)]
                                for price, qty, _, orders in book["asks"]
                            ],
                        }

                        return orderbook
                    else:
                        logger.error(
                            f"❌ OKX orderbook error: {data.get('msg', 'Unknown')}"
                        )
                        self.stats["rest_errors"] += 1
                        return None

                else:
                    logger.error(f"❌ OKX Orderbook HTTP ошибка {response.status}")
                    self.stats["rest_errors"] += 1
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка get_orderbook: {e}")
            self.stats["rest_errors"] += 1
            return None

    async def get_recent_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """
        Получить последние сделки

        Args:
            symbol: Торговая пара (BTC-USDT)
            limit: Количество сделок (макс 500)

        Returns:
            Список сделок
        """
        url = f"{self.base_url}/api/v5/market/trades"
        params = {"instId": symbol, "limit": min(limit, 500)}

        try:
            self.stats["rest_requests"] += 1
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    if data["code"] == "0":
                        trades = []
                        for trade in data["data"]:
                            trades.append(
                                {
                                    "id": trade["tradeId"],
                                    "price": float(trade["px"]),
                                    "quantity": float(trade["sz"]),
                                    "timestamp": int(trade["ts"]),
                                    "side": trade["side"],  # buy/sell
                                }
                            )

                        return trades
                    else:
                        self.stats["rest_errors"] += 1
                        return []

                else:
                    self.stats["rest_errors"] += 1
                    return []

        except Exception as e:
            logger.error(f"❌ Ошибка get_recent_trades: {e}")
            self.stats["rest_errors"] += 1
            return []

    # ===========================================
    # WEBSOCKET METHODS
    # ===========================================

    async def start_websocket(self):
        """Запуск WebSocket потоков"""
        if not self.enable_websocket or not self.symbols:
            logger.info("ℹ️ OKX WebSocket отключен или нет символов")
            return

        self.is_ws_running = True
        tasks = []

        for symbol in self.symbols:
            tasks.append(self._connect_orderbook_stream(symbol))
            tasks.append(self._connect_trade_stream(symbol))

        logger.info(f"🚀 Запуск {len(tasks)} OKX WebSocket потоков...")
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _connect_orderbook_stream(self, symbol: str):
        """WebSocket orderbook stream"""
        while self.is_ws_running:
            try:
                async with websockets.connect(
                    self.ws_public, ping_interval=30, ping_timeout=120, close_timeout=10
                ) as ws:
                    logger.info(f"✅ OKX orderbook WS: {symbol}")
                    self.ws_connections[f"books_{symbol}"] = ws

                    subscribe_msg = {
                        "op": "subscribe",
                        "args": [{"channel": "books", "instId": symbol}],
                    }

                    await ws.send(json.dumps(subscribe_msg))

                    async for message in ws:
                        if not self.is_ws_running:
                            break

                        try:
                            data = json.loads(message)
                            if "data" in data:
                                await self._handle_orderbook_update(symbol, data)
                        except Exception as e:
                            logger.error(f"❌ OKX orderbook processing error: {e}")
                            self.stats["ws_errors"] += 1

            except websockets.exceptions.ConnectionClosed as e:
                if "keepalive ping timeout" in str(e):
                    logger.debug(f"⚠️ OKX {symbol} ping timeout, reconnecting...")
                else:
                    logger.warning(
                        f"⚠️ OKX orderbook WS {symbol} closed, reconnecting..."
                    )
                await asyncio.sleep(5)
            except Exception as e:
                if "keepalive ping timeout" in str(e):
                    logger.debug(f"⚠️ OKX {symbol} ping timeout, reconnecting...")
                else:
                    logger.error(f"❌ OKX orderbook WS error {symbol}: {e}")
                    self.stats["ws_errors"] += 1
                await asyncio.sleep(5)

    async def _connect_trade_stream(self, symbol: str):
        """WebSocket trade stream"""
        while self.is_ws_running:
            try:
                async with websockets.connect(
                    self.ws_public, ping_interval=30, ping_timeout=120, close_timeout=10
                ) as ws:
                    logger.info(f"✅ OKX trade WS: {symbol}")

                    subscribe_msg = {
                        "op": "subscribe",
                        "args": [{"channel": "trades", "instId": symbol}],
                    }

                    await ws.send(json.dumps(subscribe_msg))

                    async for message in ws:
                        if not self.is_ws_running:
                            break

                        try:
                            data = json.loads(message)
                            if "data" in data:
                                await self._handle_trade(symbol, data)
                        except Exception as e:
                            logger.error(f"❌ OKX trade error: {e}")
                            self.stats["ws_errors"] += 1

            except websockets.exceptions.ConnectionClosed as e:
                if "keepalive ping timeout" in str(e):
                    logger.debug(f"⚠️ OKX {symbol} trade ping timeout, reconnecting...")
                else:
                    logger.warning(f"⚠️ OKX trade WS {symbol} closed, reconnecting...")
                await asyncio.sleep(5)
            except Exception as e:
                if "keepalive ping timeout" in str(e):
                    logger.debug(f"⚠️ OKX {symbol} trade ping timeout, reconnecting...")
                else:
                    logger.error(f"❌ OKX trade WS error: {e}")
                    self.stats["ws_errors"] += 1
                await asyncio.sleep(5)

    async def _handle_orderbook_update(self, symbol: str, data: Dict):
        """Обработка WebSocket orderbook updates"""
        if "data" not in data:
            return

        for book_data in data["data"]:
            bids_raw = book_data["bids"]
            asks_raw = book_data["asks"]

            orderbook = {
                "symbol": symbol,
                "timestamp": int(book_data["ts"]),
                "bids": [
                    [float(price), float(qty), int(orders)]
                    for price, qty, _, orders in bids_raw
                ],
                "asks": [
                    [float(price), float(qty), int(orders)]
                    for price, qty, _, orders in asks_raw
                ],
            }

            self.orderbooks[symbol] = orderbook
            self.orderbook_initialized[symbol] = True

            self.stats["ws_messages"] += 1
            self.stats["ws_orderbook_updates"] += 1

            # ✅ ДОБАВЬ ЭТУ ЧАСТЬ:
            # Рассчитываем и сохраняем давление
            bids = orderbook["bids"]
            asks = orderbook["asks"]

            pressure = self._calculate_orderbook_pressure(symbol, bids, asks)
            self.orderbook_pressure[symbol] = pressure

            # Сохраняем полные данные
            self.orderbook_data[symbol] = {
                'bids': bids,
                'asks': asks,
                'timestamp': orderbook["timestamp"],
                'pressure': pressure
            }

            # Логируем давление (throttled)
            current_time = time.time()
            last_log = self.last_pressure_log.get(symbol, 0)

            if abs(pressure) > 20 and (current_time - last_log > 30):  # Раз в 30 секунд
                direction = "📈 BUY" if pressure > 0 else "📉 SELL"
                logger.info(f"📊 OKX {symbol} Pressure: {pressure:+.1f}% {direction}")
                self.last_pressure_log[symbol] = current_time

            # ========== РАСЧЁТ ДИСБАЛАНСА (существующий код) ==========
            try:
                if bids and asks:
                    bid_volume = sum([bid[1] for bid in bids[:5]])
                    ask_volume = sum([ask[1] for ask in asks[:5]])

                    total = bid_volume + ask_volume
                    if total > 0:
                        imbalance = ((bid_volume - ask_volume) / total) * 100

                        # Проверка дисбаланса
                        if abs(imbalance) >= 70:
                            # ✅ ДОБАВИТЬ БАТЧИНГ:
                            from utils.log_batcher import log_batcher
                            if hasattr(log_batcher, 'log_imbalance'):
                                log_batcher.log_imbalance('OKX', symbol, imbalance)
                            else:
                                # Fallback: логируем реже (раз в 10 секунд)
                                if not hasattr(self, '_last_imbalance_log'):
                                    self._last_imbalance_log = {}

                                now = datetime.now().timestamp()
                                last_log = self._last_imbalance_log.get(symbol, 0)

                                if now - last_log > 10:  # Раз в 10 секунд
                                    direction = "📈 BUY" if imbalance > 0 else "📉 SELL"
                                    logger.info(
                                        f"🔥 OKX {symbol}: {abs(imbalance):.1f}% {direction} pressure"
                                    )
                                    self._last_imbalance_log[symbol] = now

            except Exception as e:
                logger.debug(f"⚠️ OKX imbalance calc error: {e}")

            # Callback
            if "on_orderbook_update" in self.callbacks:
                await self.callbacks["on_orderbook_update"](symbol, orderbook)


    async def _handle_trade(self, symbol: str, data: Dict):
        """Обработка WebSocket trades с обнаружением whale activity"""
        if "data" not in data:
            return

        for trade in data["data"]:
            # CVD tracking
            await self._handle_trade_for_cvd(trade)

            # Parse trade data
            price = float(trade["px"])
            quantity = float(trade["sz"])
            timestamp_ms = int(trade["ts"])
            side = trade["side"]  # buy/sell

            trade_data = {
                "symbol": symbol,
                "trade_id": trade["tradeId"],
                "price": price,
                "quantity": quantity,
                "timestamp": timestamp_ms,
                "side": side,
                "datetime": datetime.fromtimestamp(timestamp_ms / 1000),
            }

            # Calculate trade value
            trade_value = price * quantity

            # ⭐ НОВОЕ: Обнаружение крупных трейдов (whale activity)
            if trade_value >= self.large_trade_threshold:
                whale_trade = {
                    'symbol': symbol.replace('-', ''),  # BTC-USDT -> BTCUSDT
                    'side': side.upper(),  # buy -> BUY
                    'size': quantity,
                    'price': price,
                    'value': trade_value,
                    'timestamp': datetime.fromtimestamp(timestamp_ms / 1000),
                    'exchange': 'OKX'
                }

                # Добавляем в список
                self.large_trades.append(whale_trade)

                # Ограничиваем размер (храним последние 100)
                if len(self.large_trades) > 100:
                    self.large_trades = self.large_trades[-100:]

                # Логируем крупную сделку
                logger.info(
                    f"🐋 OKX {symbol} Large Trade {side.upper()} "
                    f"{quantity:.4f} @ ${price:,.2f} = ${trade_value:,.0f}"
                )

            self.stats["ws_messages"] += 1
            self.stats["ws_trade_updates"] += 1

            if "on_trade" in self.callbacks:
                await self.callbacks["on_trade"](symbol, trade_data)


    # HELPER METHODS
    # ===========================================

    def get_ws_orderbook(self, symbol: str, depth: int = 20) -> Optional[Dict]:
        """Получить текущий WebSocket orderbook из кэша"""
        if symbol not in self.orderbooks:
            return None

        ob = self.orderbooks[symbol]

        return {
            "bids": ob["bids"][:depth],
            "asks": ob["asks"][:depth],
            "timestamp": ob["timestamp"],
        }

    def get_best_bid_ask(self, symbol: str) -> Optional[tuple]:
        """Получить лучшие bid/ask из WebSocket cache"""
        orderbook = self.get_ws_orderbook(symbol, depth=1)
        if not orderbook or not orderbook["bids"] or not orderbook["asks"]:
            return None

        best_bid = orderbook["bids"][0][0]
        best_ask = orderbook["asks"][0][0]

        return (best_bid, best_ask)

    def get_spread(self, symbol: str) -> Optional[float]:
        """Получить спред между bid и ask"""
        ba = self.get_best_bid_ask(symbol)
        if not ba:
            return None
        return ba[1] - ba[0]

    def get_statistics(self) -> Dict:
        """Получить статистику работы коннектора"""
        return {
            **self.stats,
            "rest_initialized": self.is_initialized,
            "ws_running": self.is_ws_running,
            "ws_symbols": len(self.symbols),
            "orderbooks_cached": len(self.orderbooks),
        }

    # ===========================================
    # SHUTDOWN
    # ===========================================

    async def close(self):
        """Graceful shutdown REST + WebSocket"""
        try:
            logger.info("🛑 Closing OKX connector...")

            # Stop WebSocket
            self.is_ws_running = False

            for name, ws in self.ws_connections.items():
                try:
                    if hasattr(ws, "close"):
                        await ws.close()
                        logger.debug(f"✅ Closed {name}")
                except Exception as e:
                    logger.debug(f"⚠️ Error closing {name}: {e}")

            # Close REST session
            if self.session and not self.session.closed:
                await self.session.close()
                logger.info("✅ OKX REST session closed")

            self.is_initialized = False

            # Log final statistics
            logger.info(f"📊 Final OKX stats: {self.get_statistics()}")

        except Exception as e:
            logger.error(f"❌ Error closing OKX connector: {e}")
    def get_orderbook_pressure(self, symbol: str) -> float:
        """
        Получить текущее давление orderbook для символа

        Args:
            symbol: Торговая пара (например, BTC-USDT)

        Returns:
            float: Давление от -100 до +100
        """
        return self.orderbook_pressure.get(symbol, 0.0)


# Экспорт
__all__ = ["OKXConnector"]
