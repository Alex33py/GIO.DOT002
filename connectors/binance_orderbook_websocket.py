#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Binance Orderbook WebSocket
Получение данных orderbook через WebSocket с robust connection management
"""

import asyncio
import time
from typing import List, Dict, Optional
from utils.websocket_manager import WebSocketManager
from config.settings import logger


class BinanceOrderbookWebSocket:
    """
    Binance Orderbook WebSocket с автореконнектом

    Документация: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams
    """

    def __init__(self, symbols: List[str], connector, depth: int = 20):
        """
        Args:
            symbols: Список символов (например, ["BTCUSDT", "ETHUSDT"])
            connector: BinanceConnector instance
            depth: Глубина orderbook (5, 10, 20) - по умолчанию 20
        """
        self.symbols = symbols
        self.connector = connector
        self.depth = depth
        self.orderbook_data = {}
        self.last_pressure_log: Dict[str, float] = {}  # Throttling для логов

        # Создание streams для futures
        self.streams = [f"{s.lower()}@depth{depth}@100ms" for s in symbols]

        # WebSocket URL для futures
        url = f"wss://fstream.binance.com/stream?streams={'/'.join(self.streams)}"

        # Создание WebSocket Manager
        self.ws_manager = WebSocketManager(
            url=url,
            on_message=self._process_message,
            on_connect=self._on_connect,
            on_disconnect=self._on_disconnect,
            ping_interval=20,
            ping_timeout=15,
            reconnect_delay=5,
            max_reconnect_attempts=10,
            name="Binance-Orderbook",
        )

        logger.info(
            f"✅ Binance Orderbook WS инициализирован: "
            f"{len(symbols)} символов, depth={depth}"
        )

    async def start(self):
        """Запуск WebSocket"""
        await self.ws_manager.start()

    async def stop(self):
        """Остановка WebSocket"""
        await self.ws_manager.stop()

    async def _on_connect(self):
        """Callback при подключении"""
        logger.info(f"🎉 Binance Orderbook WS подключён: {len(self.symbols)} потоков")

    async def _on_disconnect(self):
        """Callback при отключении"""
        logger.warning("⚠️ Binance Orderbook WS отключён")

    async def _process_message(self, data: Dict):
        """Обработка сообщения"""
        try:
            if "data" not in data:
                return

            msg = data["data"]
            symbol = msg.get("s", "").upper()  # BTCUSDT

            if not symbol:
                return

            # Обновляем orderbook
            self.orderbook_data[symbol] = {
                "bids": [[float(bid[0]), float(bid[1])] for bid in msg.get("b", [])],
                "asks": [[float(ask[0]), float(ask[1])] for ask in msg.get("a", [])],
                "timestamp": msg.get("E", 0),
            }

            # Обновление в connector (для совместимости)
            if hasattr(self.connector, "orderbook_data"):
                self.connector.orderbook_data[symbol] = self.orderbook_data[symbol]

            # Рассчитываем дисбаланс и логируем (throttled)
            imbalance = self._calculate_imbalance(symbol)

            if imbalance and abs(imbalance) > 70:
                current_time = time.time()
                last_log = self.last_pressure_log.get(symbol, 0)

                # Логируем только раз в 30 секунд
                if current_time - last_log >= 30:
                    direction = "📈 BUY" if imbalance > 0 else "📉 SELL"
                    logger.info(
                        f"🔥 Binance {symbol}: {abs(imbalance):.1f}% {direction} pressure"
                    )
                    self.last_pressure_log[symbol] = current_time

        except Exception as e:
            logger.error(f"❌ Ошибка обработки orderbook: {e}")

    def _calculate_imbalance(self, symbol: str) -> Optional[float]:
        """Расчёт дисбаланса bid/ask"""
        try:
            orderbook = self.orderbook_data.get(symbol)
            if not orderbook:
                return None

            bids = orderbook["bids"]
            asks = orderbook["asks"]

            if not bids or not asks:
                return None

            # Сумма объёмов bid/ask
            bid_volume = sum([bid[1] for bid in bids])
            ask_volume = sum([ask[1] for ask in asks])

            total = bid_volume + ask_volume
            if total == 0:
                return 0

            # % дисбаланс
            imbalance = ((bid_volume - ask_volume) / total) * 100
            return imbalance

        except Exception as e:
            logger.error(f"❌ Ошибка _calculate_imbalance: {e}")
            return None

    def get_orderbook(self, symbol: str) -> Optional[Dict]:
        """Получить orderbook для символа"""
        return self.orderbook_data.get(symbol.upper())

    def get_stats(self) -> Dict:
        """Получить статистику WebSocket"""
        return self.ws_manager.get_stats()

    def is_healthy(self) -> bool:
        """Проверка здоровья соединения"""
        return self.ws_manager.is_healthy()
