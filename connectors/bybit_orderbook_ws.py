#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WebSocket коннектор для L2 Orderbook от Bybit
ОБНОВЛЁННАЯ ВЕРСИЯ с depth=200 и улучшениями
"""

import asyncio
import websockets
import json
from typing import Dict, List, Callable, Optional
from config.settings import logger


class BybitOrderbookWebSocket:
    """WebSocket для получения L2 orderbook от Bybit"""

    def __init__(
        self,
        symbol: str = "BTCUSDT",
        depth: int = 200,  # ← ИЗМЕНЕНО с 50 на 200!
        testnet: bool = False,
    ):
        """
        Инициализация WebSocket коннектора

        Args:
            symbol: Торговая пара
            depth: Глубина стакана (1, 50, 200, 500, 1000)
            testnet: Использовать testnet
        """
        self.symbol = symbol
        self.depth = depth

        # Проверка допустимых значений
        valid_depths = [1, 50, 200, 500, 1000]
        if depth not in valid_depths:
            logger.warning(f"⚠️ Недопустимый depth={depth}, используем 200")
            self.depth = 200

        # WebSocket URL
        if testnet:
            self.ws_url = "wss://stream-testnet.bybit.com/v5/public/linear"
        else:
            self.ws_url = "wss://stream.bybit.com/v5/public/linear"

        self.websocket = None
        self.callbacks = []
        self.is_running = False
        self._task = None

        # === Хранение полного orderbook ===
        self._orderbook = None
        self._snapshot_received = False

        logger.info(
            f"✅ BybitOrderbookWebSocket инициализирован "
            f"для {symbol} (depth={self.depth}, refresh={self._get_refresh_rate()}ms)"
        )

    def _get_refresh_rate(self):
        """Получить частоту обновлений"""
        refresh_rates = {
            1: 10,
            50: 20,
            200: 100,
            500: 100,
            1000: 300,
        }
        return refresh_rates.get(self.depth, 100)

    def add_callback(self, callback: Callable):
        """Добавить callback для обработки orderbook"""
        self.callbacks.append(callback)
        logger.debug(f"✅ Callback добавлен ({len(self.callbacks)} всего)")

    async def start(self):
        """Запуск WebSocket соединения"""
        try:
            logger.info(f"🔌 Подключение к {self.ws_url}...")

            self.websocket = await websockets.connect(
                self.ws_url, ping_interval=20, ping_timeout=10
            )

            # Подписка на orderbook
            subscribe_msg = {
                "op": "subscribe",
                "args": [f"orderbook.{self.depth}.{self.symbol}"],
            }

            await self.websocket.send(json.dumps(subscribe_msg))
            logger.info(f"✅ Подписка на orderbook.{self.depth}.{self.symbol}")

            self.is_running = True
            self._task = asyncio.create_task(self._listen())

        except Exception as e:
            logger.error(f"❌ Ошибка запуска WebSocket: {e}")
            raise

    async def _listen(self):
        """Прослушивание WebSocket сообщений"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)

                    # Обрабатываем только данные orderbook
                    if data.get("topic", "").startswith("orderbook"):
                        await self._process_message(data)

                except json.JSONDecodeError as e:
                    logger.error(f"❌ Ошибка парсинга JSON: {e}")
                except Exception as e:
                    logger.error(f"❌ Ошибка обработки сообщения: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("⚠️ WebSocket соединение закрыто")
            self.is_running = False
        except Exception as e:
            logger.error(f"❌ Критическая ошибка WebSocket: {e}")
            self.is_running = False

    async def _process_message(self, data: Dict):
        """
        Обработка сообщений от Bybit
        Правильная обработка snapshot и delta
        """
        try:
            if "data" not in data:
                return

            orderbook_data = data["data"]

            # Определяем тип сообщения
            message_type = data.get("type", "snapshot")

            bids = orderbook_data.get("b", [])
            asks = orderbook_data.get("a", [])
            timestamp = int(orderbook_data.get("ts", 0))
            update_id = orderbook_data.get("u", 0)

            # === SNAPSHOT: Полная инициализация orderbook ===
            if message_type == "snapshot":
                logger.info(
                    f"📸 Получен snapshot: bids={len(bids)}, asks={len(asks)} "
                    f"(depth={self.depth})"
                )

                self._orderbook = {
                    "symbol": orderbook_data.get("s", self.symbol),
                    "timestamp": timestamp,
                    "update_id": update_id,
                    "bids": [[float(b[0]), float(b[1])] for b in bids],
                    "asks": [[float(a[0]), float(a[1])] for a in asks],
                }

                self._snapshot_received = True

                # Вызываем callbacks с ПОЛНЫМ orderbook
                await self._notify_callbacks()
                return

            # === DELTA: Обновление существующих уровней ===
            elif message_type == "delta":
                # Проверяем что snapshot уже был получен
                if not self._snapshot_received or not self._orderbook:
                    logger.warning("⚠️ Delta получен до snapshot, игнорируем")
                    return

                # === ОБНОВЛЯЕМ BIDS ===
                for bid in bids:
                    try:
                        price = float(bid[0])
                        size = float(bid[1])

                        if size == 0:
                            # Удаляем уровень (цена исчезла из orderbook)
                            self._orderbook["bids"] = [
                                b for b in self._orderbook["bids"] if b[0] != price
                            ]
                        else:
                            # Обновляем или добавляем уровень
                            updated = False
                            for i, existing_bid in enumerate(self._orderbook["bids"]):
                                if existing_bid[0] == price:
                                    self._orderbook["bids"][i] = [price, size]
                                    updated = True
                                    break

                            if not updated:
                                # Новый уровень - добавляем
                                self._orderbook["bids"].append([price, size])

                    except (ValueError, IndexError) as e:
                        logger.warning(f"⚠️ Ошибка парсинга bid: {e}")
                        continue

                # === ОБНОВЛЯЕМ ASKS ===
                for ask in asks:
                    try:
                        price = float(ask[0])
                        size = float(ask[1])

                        if size == 0:
                            # Удаляем уровень
                            self._orderbook["asks"] = [
                                a for a in self._orderbook["asks"] if a[0] != price
                            ]
                        else:
                            # Обновляем или добавляем уровень
                            updated = False
                            for i, existing_ask in enumerate(self._orderbook["asks"]):
                                if existing_ask[0] == price:
                                    self._orderbook["asks"][i] = [price, size]
                                    updated = True
                                    break

                            if not updated:
                                # Новый уровень - добавляем
                                self._orderbook["asks"].append([price, size])

                    except (ValueError, IndexError) as e:
                        logger.warning(f"⚠️ Ошибка парсинга ask: {e}")
                        continue

                # === СОРТИРУЕМ И ОГРАНИЧИВАЕМ ===
                # Bids по убыванию цены (лучшая bid первая)
                self._orderbook["bids"].sort(key=lambda x: x[0], reverse=True)
                # Asks по возрастанию цены (лучшая ask первая)
                self._orderbook["asks"].sort(key=lambda x: x[0])

                # Ограничиваем до depth (200 уровней)
                self._orderbook["bids"] = self._orderbook["bids"][: self.depth]
                self._orderbook["asks"] = self._orderbook["asks"][: self.depth]

                # Обновляем timestamp
                self._orderbook["timestamp"] = timestamp
                self._orderbook["update_id"] = update_id

                from utils.log_batcher import log_batcher
                log_batcher.log_orderbook_update('Bybit', self.symbol)

                # Вызываем callbacks с ОБНОВЛЁННЫМ orderbook
                await self._notify_callbacks()

        except Exception as e:
            logger.error(f"❌ Ошибка обработки сообщения: {e}")
            import traceback

            logger.error(traceback.format_exc())

    async def _notify_callbacks(self):
        """Уведомление всех callbacks о новом состоянии orderbook"""
        try:
            if not self._orderbook:
                return

            # Вызываем все callbacks с ПОЛНЫМ orderbook
            for callback in self.callbacks:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(self._orderbook)
                    else:
                        callback(self._orderbook)
                except Exception as e:
                    logger.error(f"❌ Ошибка в callback: {e}")

        except Exception as e:
            logger.error(f"❌ Ошибка уведомления callbacks: {e}")

    async def stop(self):
        """Остановка WebSocket соединения"""
        try:
            logger.info("🔄 Закрытие WebSocket Orderbook...")

            self.is_running = False

            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

            if self.websocket:
                await self.websocket.close()

            logger.info("✅ WebSocket Orderbook закрыт")

        except Exception as e:
            logger.error(f"❌ Ошибка закрытия WebSocket: {e}")
