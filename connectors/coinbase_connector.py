#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coinbase Connector для GIO Crypto Bot
REST API + WebSocket streams (Coinbase Advanced Trade API)
"""

import asyncio
import aiohttp
import websockets
import json
import hmac
import hashlib
import time
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from collections import deque
from config.settings import logger
from utils.validators import DataValidator


class CoinbaseConnector:
    """
    Полнофункциональный коннектор к Coinbase Advanced Trade API
    Объединяет REST API и WebSocket streams
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        symbols: Optional[List[str]] = None,
        enable_websocket: bool = True,
    ):
        """
        Инициализация Coinbase коннектора

        Args:
            api_key: API ключ Coinbase (опционально)
            api_secret: API секрет Coinbase
            symbols: Список пар для WebSocket ['BTC-USD', 'ETH-USD']
            enable_websocket: Включить WebSocket потоки
        """
        # REST API настройки (Advanced Trade API)
        self.base_url = "https://api.coinbase.com"
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = None
        self.is_initialized = False

        # WebSocket настройки
        self.enable_websocket = enable_websocket
        self.ws_base = "wss://advanced-trade-ws.coinbase.com"
        self.symbols = symbols or []
        self.ws_connections: Dict[str, Any] = {}
        self.is_ws_running = False

        # WebSocket callbacks
        self.callbacks: Dict[str, Callable] = {}

        # Orderbook cache для WebSocket
        self.orderbooks: Dict[str, Dict] = {}
        self.orderbook_initialized: Dict[str, bool] = {}
        self.last_pressure_log: Dict[str, float] = {}
        self.orderbook_data = {}
        self.large_trades = deque(maxlen=1000)

        # Statistics
        self.stats = {
            "rest_requests": 0,
            "rest_errors": 0,
            "ws_messages": 0,
            "ws_orderbook_updates": 0,
            "ws_trade_updates": 0,
            "ws_ticker_updates": 0,
            "ws_errors": 0,
        }

        logger.info("✅ CoinbaseConnector инициализирован")

    # ===========================================
    # INITIALIZATION
    # ===========================================

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
                logger.info("✅ Coinbase REST API подключен")
            else:
                logger.error("❌ Не удалось подключиться к Coinbase REST API")
                return False

            # 2. Инициализация WebSocket (опционально)
            if self.enable_websocket and self.symbols:
                logger.info(
                    f"🔌 Запуск Coinbase WebSocket для {len(self.symbols)} символов..."
                )
                # WebSocket запустится в методе start()
            else:
                logger.info("ℹ️ Coinbase WebSocket отключен")

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Coinbase: {e}")
            return False

    def set_callbacks(self, callbacks: Dict[str, Callable]):
        """
        Установить callback функции для WebSocket

        Args:
            callbacks: {
                'on_orderbook_update': func,
                'on_trade': func,
                'on_ticker': func
            }
        """
        self.callbacks = callbacks
        logger.info(f"✅ Установлено {len(callbacks)} callbacks для Coinbase WebSocket")

    # ===========================================
    # AUTHENTICATION
    # ===========================================

    def _generate_signature(
        self, timestamp: str, method: str, request_path: str, body: str = ""
    ) -> str:
        """
        Генерация подписи для Coinbase API

        Args:
            timestamp: Unix timestamp
            method: HTTP метод (GET, POST)
            request_path: API endpoint
            body: Request body (для POST)

        Returns:
            HMAC SHA256 signature
        """
        message = timestamp + method + request_path + body
        signature = hmac.new(
            self.api_secret.encode("utf-8"),
            message.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).hexdigest()
        return signature

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
        timestamp = str(int(time.time()))
        signature = self._generate_signature(timestamp, method, request_path, body)

        headers = {
            "CB-ACCESS-KEY": self.api_key,
            "CB-ACCESS-SIGN": signature,
            "CB-ACCESS-TIMESTAMP": timestamp,
            "Content-Type": "application/json",
        }

        return headers

    # ===========================================
    # REST API METHODS
    # ===========================================

    async def get_server_time(self) -> Optional[int]:
        """Получить время сервера Coinbase"""
        url = f"{self.base_url}/api/v3/brokerage/time"

        try:
            self.stats["rest_requests"] += 1
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    # Coinbase возвращает ISO8601 timestamp
                    return int(time.time())
                else:
                    logger.error(f"❌ Coinbase server time ошибка: {response.status}")
                    self.stats["rest_errors"] += 1
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка get_server_time: {e}")
            self.stats["rest_errors"] += 1
            return None

    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Получить ticker статистику

        Args:
            symbol: Торговая пара (BTC-USD)

        Returns:
            Dict с данными ticker
        """
        url = f"{self.base_url}/api/v3/brokerage/products/{symbol}/ticker"

        try:
            self.stats["rest_requests"] += 1
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()

                    ticker = {
                        "symbol": symbol,
                        "last_price": float(data.get("price", 0)),
                        "volume_24h": float(data.get("volume", 0)),
                        "bid_price": float(data.get("best_bid", 0)),
                        "ask_price": float(data.get("best_ask", 0)),
                        "timestamp": datetime.utcnow(),
                    }

                    if DataValidator.validate_price(ticker["last_price"], symbol):
                        return ticker
                    else:
                        logger.warning(f"⚠️ Невалидная цена в ticker {symbol}")
                        return None

                else:
                    logger.error(f"❌ Coinbase Ticker ошибка {response.status}")
                    self.stats["rest_errors"] += 1
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка get_ticker: {e}")
            self.stats["rest_errors"] += 1
            return None

    async def get_orderbook(self, symbol: str, level: int = 2) -> Optional[Dict]:
        """
        Получить L2 orderbook через REST API

        Args:
            symbol: Торговая пара (BTC-USD)
            level: Уровень depth (1, 2)

        Returns:
            Dict с данными orderbook
        """
        url = f"{self.base_url}/api/v3/brokerage/products/{symbol}/book"
        params = {"level": level}

        try:
            self.stats["rest_requests"] += 1
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    orderbook = {
                        "symbol": symbol,
                        "timestamp": datetime.utcnow(),
                        "bids": [
                            [float(price), float(size)]
                            for price, size, _ in data.get("bids", [])
                        ],
                        "asks": [
                            [float(price), float(size)]
                            for price, size, _ in data.get("asks", [])
                        ],
                    }

                    return orderbook

                else:
                    logger.error(f"❌ Coinbase Orderbook ошибка {response.status}")
                    self.stats["rest_errors"] += 1
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка get_orderbook: {e}")
            self.stats["rest_errors"] += 1
            return None

    async def get_candles(
        self, symbol: str, granularity: int = 60, limit: int = 300
    ) -> List[Dict]:
        """
        Получить исторические свечи

        Args:
            symbol: Торговая пара (BTC-USD)
            granularity: Интервал в секундах (60=1m, 300=5m, 3600=1h, 86400=1d)
            limit: Количество свечей (макс 300)

        Returns:
            Список словарей с данными свечей
        """
        url = f"{self.base_url}/api/v3/brokerage/products/{symbol}/candles"

        # Calculate start/end times
        end_time = int(time.time())
        start_time = end_time - (granularity * limit)

        params = {
            "start": start_time,
            "end": end_time,
            "granularity": granularity,
        }

        try:
            self.stats["rest_requests"] += 1
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    candles = []
                    for candle in data.get("candles", []):
                        c = {
                            "timestamp": int(candle["start"]),
                            "open": float(candle["open"]),
                            "high": float(candle["high"]),
                            "low": float(candle["low"]),
                            "close": float(candle["close"]),
                            "volume": float(candle["volume"]),
                        }

                        if DataValidator.validate_candle(c):
                            candles.append(c)

                    logger.debug(f"✅ Получено {len(candles)} валидных свечей {symbol}")
                    return candles

                else:
                    logger.error(
                        f"❌ Coinbase Candles ошибка {response.status} для {symbol}"
                    )
                    self.stats["rest_errors"] += 1
                    return []

        except Exception as e:
            logger.error(f"❌ Ошибка get_candles {symbol}: {e}")
            self.stats["rest_errors"] += 1
            return []

    async def get_trades(self, symbol: str, limit: int = 100) -> List[Dict]:
        """
        Получить последние сделки

        Args:
            symbol: Торговая пара (BTC-USD)
            limit: Количество сделок (макс 300)

        Returns:
            Список сделок
        """
        url = f"{self.base_url}/api/v3/brokerage/products/{symbol}/trades"
        params = {"limit": min(limit, 300)}

        try:
            self.stats["rest_requests"] += 1
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    trades = []
                    for trade in data.get("trades", []):
                        trades.append(
                            {
                                "trade_id": trade["trade_id"],
                                "price": float(trade["price"]),
                                "size": float(trade["size"]),
                                "timestamp": trade["time"],
                                "side": trade["side"],  # BUY/SELL
                            }
                        )

                    return trades

                else:
                    self.stats["rest_errors"] += 1
                    return []

        except Exception as e:
            logger.error(f"❌ Ошибка get_trades: {e}")
            self.stats["rest_errors"] += 1
            return []

    # ===========================================
    # WEBSOCKET METHODS
    # ===========================================

    async def start_websocket(self):
        """Запуск WebSocket потоков"""
        if not self.enable_websocket or not self.symbols:
            logger.info("ℹ️ Coinbase WebSocket отключен или нет символов")
            return

        self.is_ws_running = True
        tasks = []

        # Coinbase использует один WebSocket с подпиской на несколько каналов
        tasks.append(self._connect_websocket())

        logger.info(f"🚀 Запуск Coinbase WebSocket потока...")
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _connect_websocket(self):
        """WebSocket unified stream"""
        while self.is_ws_running:
            try:
                async with websockets.connect(
                    self.ws_base,
                    ping_interval=30,  # ← Было 20
                    ping_timeout=120,  # ← Было 60
                    close_timeout=10,  # ← Добавлено!
                ) as ws:
                    logger.info(f"✅ Coinbase WebSocket подключен")
                    self.ws_connections["main"] = ws

                    # Subscribe to channels
                    subscribe_msg = {
                        "type": "subscribe",
                        "product_ids": self.symbols,
                        "channels": [
                            "level2",  # Orderbook
                            "ticker",  # Ticker updates
                            "matches",  # Trades
                        ],
                    }

                    await ws.send(json.dumps(subscribe_msg))
                    logger.info(
                        f"✅ Подписка на Coinbase каналы для {len(self.symbols)} пар"
                    )

                    async for message in ws:
                        if not self.is_ws_running:
                            break

                        try:
                            data = json.loads(message)
                            await self._handle_ws_message(data)
                        except Exception as e:
                            logger.error(f"❌ Coinbase WS processing error: {e}")
                            self.stats["ws_errors"] += 1

            except websockets.exceptions.ConnectionClosed as e:
                if "keepalive ping timeout" in str(e):
                    logger.debug(f"⚠️ Coinbase ping timeout, reconnecting...")
                else:
                    logger.warning(f"⚠️ Coinbase WS closed, reconnecting...")
                await asyncio.sleep(5)
            except Exception as e:
                if "keepalive ping timeout" in str(e):
                    logger.debug(f"⚠️ Coinbase ping timeout, reconnecting...")
                else:
                    logger.error(f"❌ Coinbase WS error: {e}")
                    self.stats["ws_errors"] += 1
                await asyncio.sleep(5)

    async def _handle_ws_message(self, data: Dict):
        """Обработка WebSocket messages"""
        msg_type = data.get("type")

        if msg_type == "snapshot":
            # Orderbook snapshot
            await self._handle_orderbook_snapshot(data)

        elif msg_type == "l2update":
            # Orderbook update
            await self._handle_orderbook_update(data)

        elif msg_type == "ticker":
            # Ticker update
            await self._handle_ticker(data)

        elif msg_type == "match":
            # Trade
            await self._handle_trade(data)

        elif msg_type == "subscriptions":
            logger.debug(f"✅ Coinbase subscriptions confirmed")

    async def _handle_orderbook_snapshot(self, data: Dict):
        """Обработка orderbook snapshot"""
        symbol = data.get("product_id")

        if not symbol:
            return

        orderbook = {
            "symbol": symbol,
            "timestamp": datetime.utcnow(),
            "bids": {float(p): float(s) for p, s in data.get("bids", [])},
            "asks": {float(p): float(s) for p, s in data.get("asks", [])},
        }

        self.orderbooks[symbol] = orderbook
        self.orderbook_initialized[symbol] = True

        logger.info(f"📊 Coinbase orderbook snapshot: {symbol} initialized")

        self.stats["ws_messages"] += 1
        self.stats["ws_orderbook_updates"] += 1

        if "on_orderbook_update" in self.callbacks:
            await self.callbacks["on_orderbook_update"](symbol, orderbook)

    async def _handle_orderbook_update(self, data: Dict):
        """Обработка orderbook updates"""
        symbol = data.get("product_id")

        if not symbol or symbol not in self.orderbooks:
            return

        orderbook = self.orderbooks[symbol]

        # Update bids
        for side, price, size in data.get("changes", []):
            price = float(price)
            size = float(size)

            if side == "buy":
                if size == 0:
                    orderbook["bids"].pop(price, None)
                else:
                    orderbook["bids"][price] = size
            elif side == "sell":
                if size == 0:
                    orderbook["asks"].pop(price, None)
                else:
                    orderbook["asks"][price] = size

        orderbook["timestamp"] = datetime.utcnow()

        self.stats["ws_messages"] += 1
        self.stats["ws_orderbook_updates"] += 1

        # ========== ДОБАВИТЬ РАСЧЁТ ДИСБАЛАНСА ==========
        try:
            # Сортируем для получения топ уровней
            sorted_bids = sorted(orderbook["bids"].items(), reverse=True)[:5]
            sorted_asks = sorted(orderbook["asks"].items())[:5]

            if sorted_bids and sorted_asks:
                # Суммируем объёмы топ 5 уровней
                bid_volume = sum([size for price, size in sorted_bids])
                ask_volume = sum([size for price, size in sorted_asks])

                total = bid_volume + ask_volume
                if total > 0:
                    imbalance = ((bid_volume - ask_volume) / total) * 100

                    # Логируем только сильный дисбаланс
                    if abs(imbalance) > 70:
                        current_time = time.time()
                        last_log = self.last_pressure_log.get(symbol, 0)

                        # Логируем только раз в 30 секунд
                        if current_time - last_log >= 30:
                            direction = "📈 BUY" if imbalance > 0 else "📉 SELL"
                            logger.info(
                                f"🔥 Coinbase {symbol}: {abs(imbalance):.1f}% {direction} pressure"
                            )
                            self.last_pressure_log[symbol] = current_time

        except Exception as e:
            logger.debug(f"⚠️ Coinbase imbalance calc error: {e}")

        if "on_orderbook_update" in self.callbacks:
            await self.callbacks["on_orderbook_update"](symbol, orderbook)

    async def _handle_ticker(self, data: Dict):
        """Обработка ticker updates"""
        ticker_data = {
            "symbol": data.get("product_id"),
            "price": float(data.get("price", 0)),
            "bid": float(data.get("best_bid", 0)),
            "ask": float(data.get("best_ask", 0)),
            "volume_24h": float(data.get("volume_24h", 0)),
            "timestamp": data.get("time"),
        }

        self.stats["ws_messages"] += 1
        self.stats["ws_ticker_updates"] += 1

        if "on_ticker" in self.callbacks:
            await self.callbacks["on_ticker"](ticker_data["symbol"], ticker_data)

    async def _handle_trade(self, data: Dict):
        """Обработка trades"""
        trade_data = {
            "symbol": data.get("product_id"),
            "trade_id": data.get("trade_id"),
            "price": float(data.get("price", 0)),
            "size": float(data.get("size", 0)),
            "side": data.get("side"),  # buy/sell
            "timestamp": data.get("time"),
        }

        self.stats["ws_messages"] += 1
        self.stats["ws_trade_updates"] += 1

        # 🚀 НОВОЕ: Детект large trades
        usd_value = trade_data["price"] * trade_data["size"]
        if usd_value >= 100000:  # $100k threshold
            self.large_trades.append(trade_data)
            logger.debug(
                f"💰 Coinbase Large trade: {trade_data['symbol']} ${usd_value:,.0f}"
            )

        if "on_trade" in self.callbacks:
            await self.callbacks["on_trade"](trade_data["symbol"], trade_data)

    # ===========================================
    # HELPER METHODS
    # ===========================================

    def get_ws_orderbook(self, symbol: str, depth: int = 20) -> Optional[Dict]:
        """Получить текущий WebSocket orderbook из кэша"""
        if symbol not in self.orderbooks:
            return None

        ob = self.orderbooks[symbol]
        sorted_bids = sorted(ob["bids"].items(), reverse=True)[:depth]
        sorted_asks = sorted(ob["asks"].items())[:depth]

        return {
            "bids": sorted_bids,
            "asks": sorted_asks,
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
            logger.info("🛑 Closing Coinbase connector...")

            # Stop WebSocket
            self.is_ws_running = False

            for name, ws in list(self.ws_connections.items()):
                try:
                    if ws is not None:
                        await ws.close()
                        logger.debug(f"✅ Closed {name}")
                except Exception as e:
                    logger.debug(f"⚠️ Error closing {name}: {e}")

            # Очищаем словарь соединений
            self.ws_connections.clear()

            # Close REST session
            if self.session and not self.session.closed:
                await self.session.close()
                logger.info("✅ Coinbase REST session closed")

            self.is_initialized = False

            # Log final statistics
            logger.info(f"📊 Final Coinbase stats: {self.get_statistics()}")

        except Exception as e:
            logger.error(f"❌ Error closing Coinbase connector: {e}")


# Экспорт
__all__ = ["CoinbaseConnector"]
