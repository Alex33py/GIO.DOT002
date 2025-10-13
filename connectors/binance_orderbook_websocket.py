#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Binance Orderbook WebSocket - Real-time L2 orderbook stream
"""

import asyncio
import json
import time  # ← ДОБАВЛЕНО!
from typing import Optional, Dict, List
import websockets
from config.settings import logger


class BinanceOrderbookWebSocket:
    """
    WebSocket коннектор для Binance Orderbook (depth@100ms)

    Документация: https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams
    """

    def __init__(self, symbols: List[str], depth: int = 20):
        """
        Args:
            symbols: Список символов (например, ["BTCUSDT", "ETHUSDT"])
            depth: Глубина orderbook (5, 10, 20) - по умолчанию 20
        """
        self.symbols = [s.lower() for s in symbols]
        self.depth = depth
        self.orderbook_data = {}
        self.last_pressure_log: Dict[str, float] = {}  # ← ДОБАВЛЕНО!

        # WebSocket URL для фьючерсов
        self.ws_url = "wss://fstream.binance.com/stream"

        self.ws = None
        self.is_running = False

        logger.info(
            f"✅ BinanceOrderbookWebSocket инициализирован: {len(symbols)} символов, depth={depth}"
        )

    async def start(self):
        """Запуск WebSocket подключения"""
        if self.is_running:
            logger.warning("⚠️ Binance WS уже запущен")
            return

        self.is_running = True

        # Создаём подписку на все символы
        streams = [f"{symbol}@depth{self.depth}@100ms" for symbol in self.symbols]
        params = "/".join(streams)

        url = f"{self.ws_url}?streams={params}"

        logger.info(f"🔌 Подключение к Binance WebSocket: {len(self.symbols)} пар")

        try:
            async with websockets.connect(url) as ws:
                self.ws = ws
                logger.info("✅ Binance WebSocket подключен")

                while self.is_running:
                    try:
                        message = await asyncio.wait_for(ws.recv(), timeout=30)
                        await self._process_message(json.loads(message))

                    except asyncio.TimeoutError:
                        logger.warning("⚠️ Binance WS timeout, переподключение...")
                        await ws.ping()

                    except Exception as e:
                        logger.error(f"❌ Ошибка обработки сообщения: {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка Binance WebSocket: {e}")

        finally:
            self.is_running = False
            logger.info("🛑 Binance WebSocket отключен")

    async def _process_message(self, data: Dict):
        """Обработка входящего сообщения"""
        try:
            if "data" not in data:
                return

            msg = data["data"]
            symbol = msg["s"].upper()  # BTCUSDT

            # Обновляем orderbook
            self.orderbook_data[symbol] = {
                "bids": [[float(bid[0]), float(bid[1])] for bid in msg["b"]],
                "asks": [[float(ask[0]), float(ask[1])] for ask in msg["a"]],
                "timestamp": msg["E"],
            }

            # Рассчитываем дисбаланс
            imbalance = self._calculate_imbalance(symbol)

            # ========== THROTTLING: ЛОГИРУЕМ РАЗ В 30 СЕКУНД ==========
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
            logger.error(f"❌ Ошибка _process_message: {e}")

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

    async def stop(self):
        """Остановка WebSocket"""
        self.is_running = False
        if self.ws:
            await self.ws.close()
        logger.info("🛑 Binance WebSocket остановлен")
