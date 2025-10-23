#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Binance Trade Stream WebSocket
Real-time трейды для WhaleTracker интеграции
"""

import asyncio
import json
import time
from typing import List, Optional, Dict
import websockets
from config.settings import logger


class BinanceTradeWebSocket:
    """
    WebSocket для real-time трейдов с Binance
    """

    def __init__(
        self,
        symbols: List[str],
        connector=None
    ):
        """
        Args:
            symbols: Список пар ['BTCUSDT', 'ETHUSDT']
            connector: Ссылка на BinanceConnector
        """
        self.symbols = [s.lower() for s in symbols]
        self.connector = connector
        self.ws_url = "wss://stream.binance.com:9443/ws"
        self.ws = None
        self.running = False

        # Statistics
        self.stats = {
            "trades_received": 0,
            "trades_processed": 0,
            "trades_failed": 0,
            "last_trade_time": None,
            "connection_time": None,
        }

        logger.info(f"✅ BinanceTradeWebSocket готов для {len(symbols)} символов")

    # ===========================================
    # WEBSOCKET CONNECTION
    # ===========================================

    async def start(self):
        """Запуск WebSocket подключения"""
        self.running = True
        logger.info("🚀 Запуск Binance Trade WebSocket...")

        while self.running:
            try:
                # Формируем stream для нескольких пар
                streams = "/".join([f"{sym}@trade" for sym in self.symbols])
                url = f"{self.ws_url}/{streams}"

                async with websockets.connect(url, ping_interval=20) as ws:
                    self.ws = ws
                    self.stats["connection_time"] = time.time()
                    logger.info(f"✅ Binance Trade WebSocket подключён: {len(self.symbols)} пар")

                    # Слушаем сообщения
                    async for message in ws:
                        if not self.running:
                            break
                        await self._handle_message(message)

            except websockets.ConnectionClosed:
                logger.warning("⚠️ Binance Trade WebSocket отключён, переподключение...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"❌ Ошибка Binance Trade WebSocket: {e}")
                await asyncio.sleep(5)

        logger.info("🛑 Binance Trade WebSocket остановлен")

    async def stop(self):
        """Остановка WebSocket"""
        logger.info("🛑 Остановка Binance Trade WebSocket...")
        self.running = False
        if self.ws:
            await self.ws.close()

    # ===========================================
    # MESSAGE HANDLING
    # ===========================================

    async def _handle_message(self, message: str):
        """Обработка входящих сообщений"""
        try:
            data = json.loads(message)

            # Binance trade stream format:
            # {
            #   "e": "trade",
            #   "E": 1234567890,
            #   "s": "BTCUSDT",
            #   "t": 12345,
            #   "p": "0.001",
            #   "q": "100",
            #   "b": 88,
            #   "a": 50,
            #   "T": 123456785,
            #   "m": true,
            #   "M": true
            # }

            if data.get("e") != "trade":
                return

            self.stats["trades_received"] += 1

            symbol = data.get("s")  # "BTCUSDT"
            price = float(data.get("p"))
            quantity = float(data.get("q"))
            timestamp = data.get("T")  # milliseconds
            is_buyer_maker = data.get("m")  # True = sell, False = buy

            side = "sell" if is_buyer_maker else "buy"

            # ✅ ОТПРАВКА В WHALETRACKER
            if self.connector and hasattr(self.connector, 'whale_tracker') and self.connector.whale_tracker:
                await self.connector.whale_tracker.process_trade(
                    symbol=symbol,
                    side=side,
                    price=price,
                    quantity=quantity,
                    timestamp=timestamp
                )
                self.stats["trades_processed"] += 1

            self.stats["last_trade_time"] = time.time()

        except Exception as e:
            logger.error(f"❌ Ошибка обработки Binance trade: {e}")
            self.stats["trades_failed"] += 1

    # ===========================================
    # STATISTICS
    # ===========================================

    def get_stats(self) -> Dict:
        """Получить статистику"""
        uptime = None
        if self.stats["connection_time"]:
            uptime = time.time() - self.stats["connection_time"]

        return {
            **self.stats,
            "uptime_seconds": uptime,
            "is_running": self.running,
        }


# Экспорт
__all__ = ["BinanceTradeWebSocket"]
