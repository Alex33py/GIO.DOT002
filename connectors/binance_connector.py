#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Binance Connector для GIO Crypto Bot
REST API + WebSocket streams в одном классе
"""

import asyncio
import aiohttp
import websockets
import json
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from collections import deque
from config.settings import logger
from utils.validators import DataValidator


class BinanceConnector:
    """
    Полнофункциональный коннектор к Binance
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
        Инициализация Binance коннектора

        Args:
            api_key: API ключ Binance (опционально)
            api_secret: API секрет Binance
            symbols: Список пар для WebSocket ['btcusdt', 'ethusdt']
            enable_websocket: Включить WebSocket потоки
        """
        # REST API настройки
        self.base_url = "https://api.binance.com"
        self.api_key = api_key
        self.api_secret = api_secret
        self.session = None
        self.is_initialized = False

        # WebSocket настройки
        self.enable_websocket = enable_websocket
        self.ws_base = "wss://stream.binance.com:443"
        self.symbols = [s.lower() for s in (symbols or [])]
        self.ws_connections: Dict[str, Any] = {}
        self.is_ws_running = False

        # WebSocket callbacks
        self.callbacks: Dict[str, Callable] = {}

        # Orderbook cache для WebSocket
        self.orderbooks: Dict[str, Dict] = {}
        self.orderbook_initialized: Dict[str, bool] = {}
        self.last_update_id: Dict[str, int] = {}

        # Statistics
        self.stats = {
            "rest_requests": 0,
            "rest_errors": 0,
            "ws_messages": 0,
            "ws_orderbook_updates": 0,
            "ws_trade_updates": 0,
            "ws_kline_updates": 0,
            "ws_errors": 0,
        }

        logger.info("✅ BinanceConnector инициализирован")

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
                logger.info("✅ Binance REST API подключен")
            else:
                logger.error("❌ Не удалось подключиться к Binance REST API")
                return False

            # 2. Инициализация WebSocket (опционально)
            if self.enable_websocket and self.symbols:
                logger.info(
                    f"🔌 Запуск Binance WebSocket для {len(self.symbols)} символов..."
                )
                # WebSocket запустится в методе start()
            else:
                logger.info("ℹ️ Binance WebSocket отключен")

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Binance: {e}")
            return False

    def set_callbacks(self, callbacks: Dict[str, Callable]):
        """
        Установить callback функции для WebSocket

        Args:
            callbacks: {
                'on_orderbook_update': func,
                'on_trade': func,
                'on_kline': func,
                'on_ticker': func
            }
        """
        self.callbacks = callbacks
        logger.info(f"✅ Установлено {len(callbacks)} callbacks для WebSocket")

    # ===========================================
    # REST API METHODS (существующий код)
    # ===========================================

    async def get_server_time(self) -> Optional[int]:
        """Получить время сервера Binance"""
        url = f"{self.base_url}/api/v3/time"

        try:
            self.stats["rest_requests"] += 1
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    return data["serverTime"]
                else:
                    logger.error(f"❌ Binance server time ошибка: {response.status}")
                    self.stats["rest_errors"] += 1
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка get_server_time: {e}")
            self.stats["rest_errors"] += 1
            return None

    async def get_klines(
        self, symbol: str, interval: str, limit: int = 100
    ) -> List[Dict]:
        """
        Получить исторические свечи (klines/candlesticks)

        Args:
            symbol: Торговая пара (BTCUSDT)
            interval: Интервал (1m, 5m, 15m, 1h, 4h, 1d)
            limit: Количество свечей (макс 1000)

        Returns:
            Список словарей с данными свечей
        """
        url = f"{self.base_url}/api/v3/klines"

        params = {"symbol": symbol, "interval": interval, "limit": min(limit, 1000)}

        try:
            self.stats["rest_requests"] += 1
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    candles = []
                    for item in data:
                        candle = {
                            "timestamp": int(item[0]),
                            "open": float(item[1]),
                            "high": float(item[2]),
                            "low": float(item[3]),
                            "close": float(item[4]),
                            "volume": float(item[5]),
                            "close_time": int(item[6]),
                            "quote_volume": float(item[7]),
                            "trades": int(item[8]),
                        }

                        if DataValidator.validate_candle(candle):
                            candles.append(candle)
                        else:
                            logger.warning(f"⚠️ Невалидная свеча {symbol} отброшена")

                    logger.debug(
                        f"✅ Получено {len(candles)} валидных свечей {symbol} ({interval})"
                    )
                    return candles

                elif response.status == 429:
                    logger.warning(f"⚠️ Binance rate limit для {symbol}")
                    self.stats["rest_errors"] += 1
                    return []

                else:
                    logger.error(
                        f"❌ Binance API ошибка {response.status} для {symbol}"
                    )
                    self.stats["rest_errors"] += 1
                    return []

        except Exception as e:
            logger.error(f"❌ Ошибка get_klines {symbol}: {e}")
            self.stats["rest_errors"] += 1
            return []

    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """Получить 24h ticker статистику"""
        url = f"{self.base_url}/api/v3/ticker/24hr"
        params = {"symbol": symbol}

        try:
            self.stats["rest_requests"] += 1
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    ticker = {
                        "symbol": data["symbol"],
                        "last_price": float(data["lastPrice"]),
                        "price_24h_pcnt": float(data["priceChangePercent"]),
                        "volume_24h": float(data["volume"]),
                        "quote_volume_24h": float(data["quoteVolume"]),
                        "high_24h": float(data["highPrice"]),
                        "low_24h": float(data["lowPrice"]),
                        "bid_price": float(data["bidPrice"]),
                        "ask_price": float(data["askPrice"]),
                        "open_price": float(data["openPrice"]),
                        "trades_count": int(data["count"]),
                    }

                    if DataValidator.validate_price(ticker["last_price"], symbol):
                        return ticker
                    else:
                        logger.warning(f"⚠️ Невалидная цена в ticker {symbol}")
                        return None

                else:
                    logger.error(f"❌ Ticker ошибка {response.status}")
                    self.stats["rest_errors"] += 1
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка get_ticker: {e}")
            self.stats["rest_errors"] += 1
            return None

    async def get_orderbook(self, symbol: str, limit: int = 100) -> Optional[Dict]:
        """Получить L2 orderbook через REST API"""
        url = f"{self.base_url}/api/v3/depth"

        valid_limits = [5, 10, 20, 50, 100, 500, 1000, 5000]
        limit = min(valid_limits, key=lambda x: abs(x - limit))

        params = {"symbol": symbol, "limit": limit}

        try:
            self.stats["rest_requests"] += 1
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    orderbook = {
                        "symbol": symbol,
                        "timestamp": data.get("lastUpdateId", 0),
                        "bids": [
                            [float(price), float(qty)] for price, qty in data["bids"]
                        ],
                        "asks": [
                            [float(price), float(qty)] for price, qty in data["asks"]
                        ],
                    }

                    return orderbook

                else:
                    logger.error(f"❌ Orderbook ошибка {response.status}")
                    self.stats["rest_errors"] += 1
                    return None

        except Exception as e:
            logger.error(f"❌ Ошибка get_orderbook: {e}")
            self.stats["rest_errors"] += 1
            return None

    async def get_recent_trades(self, symbol: str, limit: int = 500) -> List[Dict]:
        """Получить последние сделки"""
        url = f"{self.base_url}/api/v3/trades"
        params = {"symbol": symbol, "limit": min(limit, 1000)}

        try:
            self.stats["rest_requests"] += 1
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    trades = []
                    for trade in data:
                        trades.append(
                            {
                                "id": trade["id"],
                                "price": float(trade["price"]),
                                "quantity": float(trade["qty"]),
                                "timestamp": trade["time"],
                                "is_buyer_maker": trade["isBuyerMaker"],
                            }
                        )

                    return trades

                else:
                    self.stats["rest_errors"] += 1
                    return []

        except Exception as e:
            logger.error(f"❌ Ошибка get_recent_trades: {e}")
            self.stats["rest_errors"] += 1
            return []

    async def get_agg_trades(self, symbol: str, limit: int = 1000) -> List[Dict]:
        """Получить агрегированные сделки"""
        url = f"{self.base_url}/api/v3/aggTrades"
        params = {"symbol": symbol, "limit": min(limit, 1000)}

        try:
            self.stats["rest_requests"] += 1
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()

                    agg_trades = []
                    for trade in data:
                        agg_trades.append(
                            {
                                "agg_trade_id": trade["a"],
                                "price": float(trade["p"]),
                                "quantity": float(trade["q"]),
                                "timestamp": trade["T"],
                                "is_buyer_maker": trade["m"],
                            }
                        )

                    return agg_trades

                else:
                    self.stats["rest_errors"] += 1
                    return []

        except Exception as e:
            logger.error(f"❌ Ошибка get_agg_trades: {e}")
            self.stats["rest_errors"] += 1
            return []

    # ===========================================
    # WEBSOCKET METHODS (новый код)
    # ===========================================

    async def start_websocket(self):
        """Запуск WebSocket потоков"""
        if not self.enable_websocket or not self.symbols:
            logger.info("ℹ️ WebSocket отключен или нет символов")
            return

        self.is_ws_running = True
        tasks = []

        for symbol in self.symbols:
            tasks.append(self._connect_depth_stream(symbol))
            tasks.append(self._connect_trade_stream(symbol))
            tasks.append(self._connect_kline_stream(symbol, "1m"))
            tasks.append(self._connect_ticker_stream(symbol))

        logger.info(f"🚀 Запуск {len(tasks)} WebSocket потоков...")
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _connect_depth_stream(self, symbol: str):
        """WebSocket depth stream - orderbook updates"""
        stream_name = f"{symbol}@depth@100ms"
        url = f"{self.ws_base}/ws/{stream_name}"

        while self.is_ws_running:
            try:
                async with websockets.connect(
                    url, ping_interval=20, ping_timeout=60
                ) as ws:
                    logger.info(f"✅ Binance depth WS: {symbol}")
                    self.ws_connections[f"depth_{symbol}"] = ws

                    # Initialize orderbook snapshot
                    if not self.orderbook_initialized.get(symbol, False):
                        await self._initialize_orderbook_snapshot(symbol)

                    async for message in ws:
                        if not self.is_ws_running:
                            break

                        try:
                            data = json.loads(message)
                            await self._handle_depth_update(symbol, data)
                        except Exception as e:
                            logger.error(f"❌ Depth processing error: {e}")
                            self.stats["ws_errors"] += 1

            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"⚠️ Depth WS {symbol} closed, reconnecting...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"❌ Depth WS error {symbol}: {e}")
                self.stats["ws_errors"] += 1
                await asyncio.sleep(5)

    async def _initialize_orderbook_snapshot(self, symbol: str):
        """Инициализация orderbook snapshot через REST"""
        try:
            symbol_upper = symbol.upper()
            orderbook_data = await self.get_orderbook(symbol_upper, limit=1000)

            if orderbook_data:
                self.orderbooks[symbol] = {
                    "lastUpdateId": orderbook_data["timestamp"],
                    "bids": {float(p): float(q) for p, q in orderbook_data["bids"]},
                    "asks": {float(p): float(q) for p, q in orderbook_data["asks"]},
                    "timestamp": datetime.utcnow(),
                }

                self.last_update_id[symbol] = orderbook_data["timestamp"]
                self.orderbook_initialized[symbol] = True

                logger.info(f"📊 Orderbook snapshot: {symbol} initialized")

        except Exception as e:
            logger.error(f"❌ Orderbook snapshot error: {e}")

    async def _handle_depth_update(self, symbol: str, data: Dict):
        """Обработка WebSocket depth updates"""
        if not self.orderbook_initialized.get(symbol, False):
            return

        if data.get("e") != "depthUpdate":
            return

        first_update_id = data["U"]
        final_update_id = data["u"]
        last_update_id = self.last_update_id.get(symbol, 0)

        # Validate sequence
        if final_update_id <= last_update_id:
            return

        if first_update_id > last_update_id + 1:
            logger.warning(f"⚠️ Gap detected {symbol}, reinitializing...")
            self.orderbook_initialized[symbol] = False
            await self._initialize_orderbook_snapshot(symbol)
            return

        orderbook = self.orderbooks[symbol]

        # Update bids
        for price_str, qty_str in data["b"]:
            price, qty = float(price_str), float(qty_str)
            if qty == 0:
                orderbook["bids"].pop(price, None)
            else:
                orderbook["bids"][price] = qty

        # Update asks
        for price_str, qty_str in data["a"]:
            price, qty = float(price_str), float(qty_str)
            if qty == 0:
                orderbook["asks"].pop(price, None)
            else:
                orderbook["asks"][price] = qty

        orderbook["lastUpdateId"] = final_update_id
        orderbook["timestamp"] = datetime.utcnow()
        self.last_update_id[symbol] = final_update_id

        self.stats["ws_messages"] += 1
        self.stats["ws_orderbook_updates"] += 1

        # Callback
        if "on_orderbook_update" in self.callbacks:
            await self.callbacks["on_orderbook_update"](symbol, orderbook)

    async def _connect_trade_stream(self, symbol: str):
        """WebSocket trade stream"""
        stream_name = f"{symbol}@trade"
        url = f"{self.ws_base}/ws/{stream_name}"

        while self.is_ws_running:
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    logger.info(f"✅ Binance trade WS: {symbol}")

                    async for message in ws:
                        if not self.is_ws_running:
                            break

                        try:
                            data = json.loads(message)
                            await self._handle_trade(symbol, data)
                        except Exception as e:
                            logger.error(f"❌ Trade error: {e}")
                            self.stats["ws_errors"] += 1

            except Exception as e:
                logger.error(f"❌ Trade WS error: {e}")
                self.stats["ws_errors"] += 1
                await asyncio.sleep(5)

    async def _handle_trade(self, symbol: str, data: Dict):
        """Обработка WebSocket trades"""
        if data.get("e") != "trade":
            return

        trade_data = {
            "symbol": data["s"],
            "trade_id": data["t"],
            "price": float(data["p"]),
            "quantity": float(data["q"]),
            "timestamp": data["T"],
            "is_buyer_maker": data["m"],
            "datetime": datetime.fromtimestamp(data["T"] / 1000),
        }

        self.stats["ws_messages"] += 1
        self.stats["ws_trade_updates"] += 1

        if "on_trade" in self.callbacks:
            await self.callbacks["on_trade"](symbol, trade_data)

    async def _connect_kline_stream(self, symbol: str, interval: str = "1m"):
        """WebSocket kline stream"""
        stream_name = f"{symbol}@kline_{interval}"
        url = f"{self.ws_base}/ws/{stream_name}"

        while self.is_ws_running:
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    logger.info(f"✅ Binance kline WS: {symbol} {interval}")

                    async for message in ws:
                        if not self.is_ws_running:
                            break

                        try:
                            data = json.loads(message)
                            await self._handle_kline(symbol, data)
                        except Exception as e:
                            logger.error(f"❌ Kline error: {e}")
                            self.stats["ws_errors"] += 1

            except Exception as e:
                logger.error(f"❌ Kline WS error: {e}")
                self.stats["ws_errors"] += 1
                await asyncio.sleep(5)

    async def _handle_kline(self, symbol: str, data: Dict):
        """Обработка WebSocket klines"""
        if data.get("e") != "kline":
            return

        k = data["k"]

        kline_data = {
            "symbol": k["s"],
            "interval": k["i"],
            "open": float(k["o"]),
            "high": float(k["h"]),
            "low": float(k["l"]),
            "close": float(k["c"]),
            "volume": float(k["v"]),
            "is_closed": k["x"],
            "timestamp": k["t"],
        }

        self.stats["ws_messages"] += 1
        self.stats["ws_kline_updates"] += 1

        if "on_kline" in self.callbacks:
            await self.callbacks["on_kline"](symbol, kline_data)

    async def _connect_ticker_stream(self, symbol: str):
        """WebSocket ticker stream"""
        stream_name = f"{symbol}@miniTicker"
        url = f"{self.ws_base}/ws/{stream_name}"

        while self.is_ws_running:
            try:
                async with websockets.connect(url, ping_interval=20) as ws:
                    logger.info(f"✅ Binance ticker WS: {symbol}")

                    async for message in ws:
                        if not self.is_ws_running:
                            break

                        try:
                            data = json.loads(message)
                            await self._handle_ticker(symbol, data)
                        except Exception as e:
                            logger.error(f"❌ Ticker error: {e}")
                            self.stats["ws_errors"] += 1

            except Exception as e:
                logger.error(f"❌ Ticker WS error: {e}")
                self.stats["ws_errors"] += 1
                await asyncio.sleep(5)

    async def _handle_ticker(self, symbol: str, data: Dict):
        """Обработка WebSocket ticker"""
        ticker_data = {
            "symbol": data["s"],
            "close": float(data["c"]),
            "open": float(data["o"]),
            "high": float(data["h"]),
            "low": float(data["l"]),
            "volume": float(data["v"]),
            "timestamp": data["E"],
        }

        if "on_ticker" in self.callbacks:
            await self.callbacks["on_ticker"](symbol, ticker_data)

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
            "lastUpdateId": ob["lastUpdateId"],
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
            logger.info("🛑 Closing Binance connector...")

            # Stop WebSocket
            self.is_ws_running = False

            for name, ws in self.ws_connections.items():
                try:
                    if hasattr(ws, "close") and not getattr(ws, 'closed', True):
                        await ws.close()
                        logger.info(f"✅ Closed {name}")
                except Exception as e:
                    logger.error(f"❌ Error closing {name}: {e}")

            # Close REST session
            if self.session and not self.session.closed:
                await self.session.close()
                logger.info("✅ REST session closed")

            self.is_initialized = False

            # Log final statistics
            logger.info(f"📊 Final Binance stats: {self.get_statistics()}")

        except Exception as e:
            logger.error(f"❌ Error closing Binance connector: {e}")


# Экспорт
__all__ = ["BinanceConnector"]
