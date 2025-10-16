#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Binance Connector для GIO Crypto Bot
REST API + WebSocket orderbook через BinanceOrderbookWebSocket
"""

import asyncio
import aiohttp
from typing import Dict, List, Optional
from collections import deque
from config.settings import logger
from utils.validators import DataValidator
from connectors.binance_orderbook_websocket import BinanceOrderbookWebSocket


class BinanceConnector:
    """
    Полнофункциональный коннектор к Binance
    REST API + WebSocket orderbook
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
            symbols: Список пар для WebSocket ['BTCUSDT', 'ETHUSDT']
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
        self.symbols = symbols or []
        self.orderbook_ws = None
        self.orderbook_data = {}
        self.large_trades = deque(maxlen=1000)

        # Statistics
        self.stats = {
            "rest_requests": 0,
            "rest_errors": 0,
            "ws_messages": 0,
            "ws_errors": 0,
        }

        logger.info("✅ BinanceConnector инициализирован")

    # ===========================================
    # INITIALIZATION
    # ===========================================

    async def initialize(self) -> bool:
        """Инициализация REST сессии и WebSocket"""
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

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации Binance: {e}")
            return False

    # ===========================================
    # REST API METHODS
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
        """Получить исторические свечи (klines/candlesticks)"""
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

                    return candles

                elif response.status == 429:
                    logger.warning(f"⚠️ Binance rate limit для {symbol}")
                    self.stats["rest_errors"] += 1
                    return []
                else:
                    logger.error(f"❌ Binance API ошибка {response.status}")
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
                        trade_obj = {
                            "id": trade["id"],
                            "price": float(trade["price"]),
                            "quantity": float(trade["qty"]),
                            "timestamp": trade["time"],
                            "is_buyer_maker": trade["isBuyerMaker"],
                            "symbol": symbol  # ← ДОБАВЬ!
                        }

                        trades.append(trade_obj)

                        # 🚀 НОВОЕ: Детект large trades
                        usd_value = trade_obj["price"] * trade_obj["quantity"]
                        if usd_value >= 100000:  # $100k threshold
                            self.large_trades.append(trade_obj)
                            logger.debug(f"💰 Binance Large trade: {symbol} ${usd_value:,.0f}")

                    return trades
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
        """Запуск WebSocket подключений"""
        if not self.enable_websocket or not self.symbols:
            logger.info("ℹ️ WebSocket отключен или нет символов")
            return

        logger.info("🚀 Запуск Binance WebSocket потоков...")

        try:
            self.orderbook_ws = BinanceOrderbookWebSocket(
                symbols=self.symbols, connector=self, depth=20
            )
            asyncio.create_task(self.orderbook_ws.start())
            logger.info("✅ Binance WebSocket запущен")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска Binance WebSocket: {e}")

    # ===========================================
    # HELPER METHODS
    # ===========================================

    def get_statistics(self) -> Dict:
        """Получить статистику работы коннектора"""
        ws_stats = {}
        if self.orderbook_ws:
            ws_stats = self.orderbook_ws.get_stats()

        return {
            **self.stats,
            "rest_initialized": self.is_initialized,
            "ws_running": self.orderbook_ws is not None,
            "ws_stats": ws_stats,
        }

    # ===========================================
    # SHUTDOWN
    # ===========================================

    async def close(self):
        """Graceful shutdown REST + WebSocket"""
        try:
            logger.info("🛑 Closing Binance connector...")

            # Stop WebSocket
            if self.orderbook_ws:
                await self.orderbook_ws.stop()

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
