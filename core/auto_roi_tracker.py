#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto ROI Tracker - Автоматическое отслеживание достижения TP/SL и фиксация ROI
"""

import asyncio
from typing import Dict, List
from datetime import datetime, timedelta
from config.settings import logger


class AutoROITracker:
    """Автоматическое отслеживание и фиксация ROI"""

    def __init__(self, bot_instance):
        """
        Args:
            bot_instance: Основной экземпляр GIOCryptoBot
        """
        self.bot = bot_instance
        self.is_running = False
        self.check_interval = 60  # ✅ Проверка каждые 60 секунд
        self.active_signals = {}
        self.tp1_percentage = 0.25
        self.tp2_percentage = 0.50
        self.tp3_percentage = 0.25

        logger.info("✅ AutoROITracker инициализирован")

    async def start(self):
        """Запуск автоматического отслеживания"""
        self.is_running = True
        logger.info("🎯 AutoROITracker запущен")
        await self.load_active_signals()

        while self.is_running:
            try:
                await self.check_all_signals()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"❌ Ошибка автоотслеживания ROI: {e}")
                await asyncio.sleep(60)

    async def stop(self):
        """Остановка отслеживания"""
        self.is_running = False
        logger.info("🛑 AutoROITracker остановлен")

    async def load_active_signals(self):
        """Загрузка активных сигналов из БД"""
        try:
            if not hasattr(self.bot, "signal_recorder"):
                return

            active_signals = self.bot.signal_recorder.get_active_signals()
            cutoff_time = datetime.now() - timedelta(hours=24)
            filtered_count = 0

            for signal in active_signals:
                signal_id = signal.get("id")

                # ========== ФИЛЬТР СТАРЫХ СИГНАЛОВ ==========
                created_at_str = signal.get("created_at")
                if created_at_str:
                    try:
                        created_at = datetime.fromisoformat(
                            created_at_str.replace("Z", "+00:00")
                        )
                        age_hours = (datetime.now() - created_at).total_seconds() / 3600

                        if created_at < cutoff_time:
                            filtered_count += 1
                            logger.info(
                                f"⏭️ Пропущен старый сигнал #{signal_id} (возраст: {age_hours:.1f}ч)"
                            )
                            continue
                    except Exception as e:
                        logger.warning(f"⚠️ Ошибка парсинга даты для #{signal_id}: {e}")

                tp1_hit = signal.get("tp1_hit", 0) == 1
                tp2_hit = signal.get("tp2_hit", 0) == 1
                tp3_hit = signal.get("tp3_hit", 0) == 1

                self.active_signals[signal_id] = {
                    "id": signal_id,
                    "symbol": signal.get("symbol"),
                    "direction": signal.get("direction"),
                    "entry_price": signal.get("entry_price"),
                    "stop_loss": signal.get("stop_loss"),
                    "tp1": signal.get("tp1"),
                    "tp2": signal.get("tp2"),
                    "tp3": signal.get("tp3"),
                    "tp1_reached": tp1_hit,
                    "tp2_reached": tp2_hit,
                    "tp3_reached": tp3_hit,
                    "breakeven_moved": False,
                    "trailing_started": False,
                    "realized_roi": 0.0,
                    "created_at": created_at_str,
                }

            logger.info(
                f"✅ Загружено {len(self.active_signals)} активных сигналов (отфильтровано {filtered_count} старых)"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки активных сигналов: {e}")

    async def add_signal(self, signal: Dict):
        """Добавление нового сигнала для отслеживания"""
        try:
            signal_id = signal.get("id")
            if signal_id:
                self.active_signals[signal_id] = {
                    "id": signal_id,
                    "symbol": signal.get("symbol"),
                    "direction": signal.get("direction"),
                    "entry_price": signal.get("entry_price"),
                    "stop_loss": signal.get("stop_loss"),
                    "tp1": signal.get("tp1"),
                    "tp2": signal.get("tp2"),
                    "tp3": signal.get("tp3"),
                    "tp1_reached": False,
                    "tp2_reached": False,
                    "tp3_reached": False,
                    "breakeven_moved": False,
                    "trailing_started": False,
                    "realized_roi": 0.0,
                    "created_at": signal.get("created_at", datetime.now().isoformat()),
                }
                logger.info(f"✅ Сигнал #{signal_id} добавлен в отслеживание")
        except Exception as e:
            logger.error(f"❌ Ошибка добавления сигнала: {e}")

    async def check_all_signals(self):
        """Проверка всех активных сигналов"""
        if not self.active_signals:
            return

        for signal_id in list(self.active_signals.keys()):
            try:
                await self.check_signal(signal_id, self.active_signals[signal_id])
            except Exception as e:
                logger.error(f"❌ Ошибка проверки сигнала #{signal_id}: {e}")

    async def check_signal(self, signal_id: int, signal: Dict):
        """Проверка одного сигнала"""
        try:
            symbol = signal.get("symbol")
            direction = signal.get("direction")
            entry_price = signal.get("entry_price")
            stop_loss = signal.get("stop_loss")
            tp1 = signal.get("tp1")
            tp2 = signal.get("tp2")
            tp3 = signal.get("tp3")

            current_price = await self._get_current_price(symbol)
            if not current_price:
                return

            if self._check_stop_loss_hit(current_price, stop_loss, direction):
                await self._handle_stop_loss(signal_id, signal, current_price)
                return

            if not signal.get("tp1_reached"):
                if tp1 and tp1 != 0 and tp1 != entry_price:
                    if self._check_tp_reached(current_price, tp1, direction):
                        await self._handle_tp1_reached(signal_id, signal, current_price)
                        signal["tp1_reached"] = True

            if signal.get("tp1_reached") and not signal.get("tp2_reached"):
                if tp2 and tp2 != 0 and tp2 != entry_price:
                    if self._check_tp_reached(current_price, tp2, direction):
                        await self._handle_tp2_reached(signal_id, signal, current_price)
                        signal["tp2_reached"] = True

            if signal.get("tp2_reached") and not signal.get("tp3_reached"):
                if tp3 and tp3 != 0 and tp3 != entry_price:
                    if self._check_tp_reached(current_price, tp3, direction):
                        await self._handle_tp3_reached(signal_id, signal, current_price)
                        signal["tp3_reached"] = True
                        del self.active_signals[signal_id]

        except Exception as e:
            logger.error(f"❌ Ошибка check_signal #{signal_id}: {e}")

    def _check_stop_loss_hit(
        self, current_price: float, stop_loss: float, direction: str
    ) -> bool:
        """Проверка достижения Stop Loss"""
        if direction == "LONG":
            return current_price <= stop_loss
        else:
            return current_price >= stop_loss

    def _check_tp_reached(
        self, current_price: float, tp: float, direction: str
    ) -> bool:
        """Проверка достижения Take Profit"""
        if direction == "LONG":
            return current_price >= tp
        else:
            return current_price <= tp

    async def _get_current_price(self, symbol: str) -> float:
        """Получение текущей цены"""
        try:
            ticker = await self.bot.bybit_connector.get_ticker(symbol)
            if ticker:
                return float(ticker.get("last_price", 0))
            return 0
        except Exception as e:
            logger.error(f"❌ Ошибка получения цены {symbol}: {e}")
            return 0

    async def _handle_tp1_reached(
        self, signal_id: int, signal: Dict, current_price: float
    ):
        """Обработка достижения TP1"""
        try:
            entry_price = signal.get("entry_price")
            tp1 = signal.get("tp1")
            direction = signal.get("direction")

            if not tp1 or tp1 == 0 or tp1 == entry_price:
                logger.info(
                    f"⏭️ Пропуск TP1 #{signal_id}: TP1 не установлен или равен entry"
                )
                return

            if signal.get("tp1_reached"):
                logger.info(f"⏭️ TP1 #{signal_id} уже был достигнут ранее")
                return

            # ========== ✅ ПРОВЕРКА ВОЗРАСТА СИГНАЛА ==========
            created_at_str = signal.get("created_at")
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                    age_hours = (datetime.now() - created_at).total_seconds() / 3600

                    if age_hours > 24:
                        logger.info(
                            f"⏭️ TP1 #{signal_id} пропущен (возраст: {age_hours:.1f}ч)"
                        )
                        return
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка парсинга даты для #{signal_id}: {e}")
            # ==================================================

            if direction == "LONG":
                roi = (
                    ((current_price - entry_price) / entry_price)
                    * 100
                    * self.tp1_percentage
                )
            else:
                roi = (
                    ((entry_price - current_price) / entry_price)
                    * 100
                    * self.tp1_percentage
                )

            signal["realized_roi"] += roi

            if hasattr(self.bot, "signal_recorder"):
                self.bot.signal_recorder.update_signal_tp_reached(
                    signal_id=signal_id, tp_level=1, realized_roi=signal["realized_roi"]
                )

            if signal_id in self.active_signals:
                self.active_signals[signal_id]["tp1_reached"] = True

            signal["stop_loss"] = entry_price
            signal["breakeven_moved"] = True

            if hasattr(self.bot, "telegram_bot") and self.bot.telegram_bot:
                await self.bot.telegram_bot.notify_tp1_reached(
                    {**signal, "profit_percent": roi}
                )

            logger.info(f"🎯 TP1 достигнут для #{signal_id}, ROI: +{roi:.2f}%")

        except Exception as e:
            logger.error(f"❌ Ошибка handle_tp1 #{signal_id}: {e}")

    async def _handle_tp2_reached(
        self, signal_id: int, signal: Dict, current_price: float
    ):
        """Обработка достижения TP2"""
        try:
            entry_price = signal.get("entry_price")
            tp2 = signal.get("tp2")
            direction = signal.get("direction")

            if not tp2 or tp2 == 0 or tp2 == entry_price:
                logger.info(
                    f"⏭️ Пропуск TP2 #{signal_id}: TP2 не установлен или равен entry"
                )
                return

            # ========== ✅ ПРОВЕРКА ВОЗРАСТА СИГНАЛА ==========
            created_at_str = signal.get("created_at")
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                    age_hours = (datetime.now() - created_at).total_seconds() / 3600

                    if age_hours > 24:
                        logger.info(
                            f"⏭️ TP2 #{signal_id} пропущен (возраст: {age_hours:.1f}ч)"
                        )
                        return
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка парсинга даты для #{signal_id}: {e}")
            # ==================================================

            if direction == "LONG":
                roi = (
                    ((current_price - entry_price) / entry_price)
                    * 100
                    * self.tp2_percentage
                )
            else:
                roi = (
                    ((entry_price - current_price) / entry_price)
                    * 100
                    * self.tp2_percentage
                )

            signal["realized_roi"] += roi

            if hasattr(self.bot, "signal_recorder"):
                self.bot.signal_recorder.update_signal_tp_reached(
                    signal_id=signal_id, tp_level=2, realized_roi=signal["realized_roi"]
                )

            if signal_id in self.active_signals:
                self.active_signals[signal_id]["tp2_reached"] = True

            if hasattr(self.bot, "telegram_bot") and self.bot.telegram_bot:
                await self.bot.telegram_bot.notify_tp2_reached(
                    {**signal, "profit_percent": roi}
                )

            logger.info(f"🎯🎯 TP2 достигнут для #{signal_id}, ROI: +{roi:.2f}%")

        except Exception as e:
            logger.error(f"❌ Ошибка handle_tp2 #{signal_id}: {e}")

    async def _handle_tp3_reached(
        self, signal_id: int, signal: Dict, current_price: float
    ):
        """Обработка достижения TP3"""
        try:
            entry_price = signal.get("entry_price")
            tp3 = signal.get("tp3")
            direction = signal.get("direction")

            if not tp3 or tp3 == 0 or tp3 == entry_price:
                logger.info(
                    f"⏭️ Пропуск TP3 #{signal_id}: TP3 не установлен или равен entry"
                )
                return

            # ========== ✅ ПРОВЕРКА ВОЗРАСТА СИГНАЛА ==========
            created_at_str = signal.get("created_at")
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(
                        created_at_str.replace("Z", "+00:00")
                    )
                    age_hours = (datetime.now() - created_at).total_seconds() / 3600

                    if age_hours > 24:
                        logger.info(
                            f"⏭️ TP3 #{signal_id} пропущен (возраст: {age_hours:.1f}ч)"
                        )
                        return
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка парсинга даты для #{signal_id}: {e}")
            # ==================================================

            if direction == "LONG":
                roi = (
                    ((current_price - entry_price) / entry_price)
                    * 100
                    * self.tp3_percentage
                )
            else:
                roi = (
                    ((entry_price - current_price) / entry_price)
                    * 100
                    * self.tp3_percentage
                )

            signal["realized_roi"] += roi

            if hasattr(self.bot, "signal_recorder"):
                self.bot.signal_recorder.close_signal(
                    signal_id=signal_id,
                    exit_price=current_price,
                    realized_roi=signal["realized_roi"],
                    status="completed",
                )

            if signal_id in self.active_signals:
                self.active_signals[signal_id]["tp3_reached"] = True

            if hasattr(self.bot, "telegram_bot") and self.bot.telegram_bot:
                await self.bot.telegram_bot.notify_tp3_reached(
                    {**signal, "profit_percent": roi}
                )

            logger.info(
                f"🎯🎯🎯 TP3 достигнут для #{signal_id}, Итого ROI: +{signal['realized_roi']:.2f}%"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка handle_tp3 #{signal_id}: {e}")

    async def _handle_stop_loss(
        self, signal_id: int, signal: Dict, current_price: float
    ):
        """Обработка достижения Stop Loss"""
        try:
            entry_price = signal.get("entry_price")
            direction = signal.get("direction")

            if direction == "LONG":
                loss = ((current_price - entry_price) / entry_price) * 100
            else:
                loss = ((entry_price - current_price) / entry_price) * 100

            total_roi = signal.get("realized_roi", 0) + loss * (
                1.0 - self.tp1_percentage - self.tp2_percentage
            )

            if hasattr(self.bot, "signal_recorder"):
                self.bot.signal_recorder.close_signal(
                    signal_id=signal_id,
                    exit_price=current_price,
                    realized_roi=total_roi,
                    status="stopped",
                )

            if hasattr(self.bot, "telegram_bot") and self.bot.telegram_bot:
                await self.bot.telegram_bot.notify_stop_loss_hit(
                    {**signal, "profit_percent": total_roi}
                )

            if signal_id in self.active_signals:
                del self.active_signals[signal_id]

            logger.info(f"🛑 Stop Loss для #{signal_id}, Итого ROI: {total_roi:.2f}%")

        except Exception as e:
            logger.error(f"❌ Ошибка handle_stop_loss #{signal_id}: {e}")
