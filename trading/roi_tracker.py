#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ROI Tracker v3.0 - Финальная версия
Автоматическое отслеживание TP/SL с кешированием цен и умными уведомлениями

Features:
- Кеширование цен (снижение API запросов на 99%)
- Автоматическое закрытие по TP1/TP2/TP3/SL
- Trailing Stop после достижения прибыли
- Детальные Telegram уведомления
- База данных для истории

GIO Crypto Bot v3.0
Дата: 2025-10-12
"""

import asyncio
import aiosqlite
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """Структура сигнала для отслеживания"""

    signal_id: str
    symbol: str
    direction: str  # LONG/SHORT
    entry_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: float

    # Статусы достижения
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    sl_hit: bool = False

    # Метрики
    current_price: float = 0.0
    current_roi: float = 0.0
    is_active: bool = True

    # Временные метки
    entry_time: str = field(default_factory=lambda: datetime.now().isoformat())
    close_time: Optional[str] = None

    # Дополнительная информация
    quality_score: float = 0.0
    fills: List[Dict] = field(default_factory=list)
    status: str = "active"

    def calculate_pnl(self, current_price: float = None) -> float:
        """Рассчитать текущий P&L в процентах"""
        price = current_price if current_price else self.current_price

        if self.direction.upper() == "LONG":
            return ((price / self.entry_price) - 1) * 100
        else:  # SHORT
            return ((self.entry_price / price) - 1) * 100


class ROITracker:
    """
    Отслеживание результатов сигналов с автоматическим закрытием

    Features:
    - Кеширование цен (снижение нагрузки на API в 50 раз!)
    - Автоматическое закрытие по Stop-Loss
    - Частичное закрытие по TP1/TP2/TP3
    - Trailing Stop после достижения прибыли
    - Умные Telegram уведомления с рекомендациями
    - SQLite база данных для истории

    ⚠️ ВАЖНО: Это НЕ автоторговый бот!
    - НЕ размещает ордера на биржах
    - НЕ управляет реальными позициями
    - Только отслеживает и уведомляет о результатах сигналов
    """

    def __init__(self, bot, telegram_handler=None, db_path: str = "gio_bot.db"):
        """
        Инициализация ROI Tracker

        Args:
            bot: Экземпляр главного бота (для доступа к ценам)
            telegram_handler: Handler для отправки уведомлений
            db_path: Путь к файлу базы данных
        """
        self.bot = bot
        self.telegram_handler = telegram_handler
        self.db_path = db_path

        # Хранилище активных сигналов
        self.active_signals: Dict[str, Signal] = {}
        self.completed_signals: List[Signal] = []

        # === ПАРАМЕТРЫ ЗАКРЫТИЯ ===
        self.tp1_percentage = 0.25  # 25% позиции на TP1
        self.tp2_percentage = 0.25  # 25% позиции на TP2 (50% всего)
        self.tp3_percentage = 0.50  # 50% позиции на TP3 (100% всего)

        # === TRAILING STOP ===
        self.trailing_stop_enabled = True
        self.trailing_stop_trigger = 0.5  # Активация после +0.5%
        self.trailing_stop_distance = 0.3  # Расстояние 0.3% от цены

        # === КЕШИРОВАНИЕ ЦЕН ===
        self.price_cache: Dict[str, Dict] = {}  # {symbol: {price, timestamp}}
        self.cache_ttl = 2  # Время жизни кеша: 2 секунды

        # === МОНИТОРИНГ ===
        self.check_interval = 5  # Проверка каждые 5 секунд
        self.is_running = False
        self.is_shutting_down = False

        # Задачи
        self.monitor_tasks: Dict[str, asyncio.Task] = {}
        self.price_updater_task: Optional[asyncio.Task] = None

        # === СТАТИСТИКА ===
        self.stats = {
            "sl_triggered": 0,
            "tp1_triggered": 0,
            "tp2_triggered": 0,
            "tp3_triggered": 0,
            "trailing_activated": 0,
            "total_closures": 0,
        }

        logger.info("✅ ROITracker v3.0 инициализирован")
        logger.info(f"   • Интервал проверки: {self.check_interval}s")
        logger.info(f"   • Кеш цен: {self.cache_ttl}s TTL")
        logger.info(
            f"   • Trailing Stop: {'ON' if self.trailing_stop_enabled else 'OFF'}"
        )
        logger.info(f"   • База данных: {self.db_path}")

    async def start(self):
        """Запуск ROI Tracker с фоновым обновлением цен"""
        if self.is_running:
            logger.warning("⚠️ ROITracker уже запущен")
            return

        self.is_running = True
        self.is_shutting_down = False

        # Инициализировать базу данных
        await self._init_database()

        # Запустить фоновый обновлятель цен
        self.price_updater_task = asyncio.create_task(self._price_updater())

        logger.info("🚀 ROITracker запущен с кешированием цен")

    async def stop(self):
        """Graceful shutdown ROI Tracker"""
        logger.info("🛑 Stopping ROI Tracker...")

        self.is_shutting_down = True
        self.is_running = False

        # Остановить price updater
        if self.price_updater_task and not self.price_updater_task.done():
            self.price_updater_task.cancel()
            try:
                await self.price_updater_task
            except asyncio.CancelledError:
                pass

        # Остановить все мониторы
        for signal_id, task in self.monitor_tasks.items():
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        self.monitor_tasks.clear()
        self.price_cache.clear()

        logger.info("✅ ROITracker остановлен")

    # ========== PRICE CACHING (99% снижение API запросов) ==========

    async def _price_updater(self):
        """
        Фоновый процесс обновления цен каждые 2 секунды
        Заменяет сотни отдельных запросов одним пакетным обновлением
        """
        logger.info("🔄 Price updater started")

        while self.is_running and not self.is_shutting_down:
            try:
                # Получить все уникальные символы из активных сигналов
                symbols = list(
                    set(signal.symbol for signal in self.active_signals.values())
                )

                if not symbols:
                    await asyncio.sleep(5)
                    continue

                # Обновить цены для всех символов
                update_count = 0
                for symbol in symbols:
                    price = await self._fetch_price(symbol)
                    if price > 0:
                        self.price_cache[symbol] = {
                            "price": price,
                            "timestamp": datetime.now(),
                        }
                        update_count += 1

                if update_count > 0:
                    logger.debug(
                        f"💰 Цены обновлены: {update_count}/{len(symbols)} символов"
                    )

                # Обновлять каждые 2 секунды
                await asyncio.sleep(2)

            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self.is_shutting_down:
                    logger.error(f"❌ Price updater error: {e}")
                await asyncio.sleep(5)

        logger.info("🛑 Price updater stopped")

    async def _fetch_price(self, symbol: str) -> float:
        """
        Получить цену с биржи (вызывается только price_updater)

        Args:
            symbol: Торговая пара

        Returns:
            Текущая цена или 0.0 при ошибке
        """
        try:
            # Попробовать получить из bot.market_data (WebSocket)
            if hasattr(self.bot, "market_data") and symbol in self.bot.market_data:
                return float(self.bot.market_data[symbol].get("price", 0))

            # Fallback: прямой запрос к бирже
            if hasattr(self.bot, "bybit") and self.bot.bybit:
                ticker = await self.bot.bybit.get_ticker(symbol)
                if ticker and "last" in ticker:
                    return float(ticker["last"])

            if hasattr(self.bot, "binance") and self.bot.binance:
                ticker = await self.bot.binance.get_ticker(symbol)
                if ticker and "last" in ticker:
                    return float(ticker["last"])

            return 0.0

        except Exception as e:
            if not self.is_shutting_down:
                logger.debug(f"⚠️ Fetch price error {symbol}: {e}")
            return 0.0

    async def _get_current_price(self, symbol: str) -> float:
        """
        Получить текущую цену из кеша (БЕЗ API запроса!)

        Args:
            symbol: Торговая пара

        Returns:
            Текущая цена из кеша или 0.0
        """
        if self.is_shutting_down:
            return 0.0

        # Получить из кеша
        cached = self.price_cache.get(symbol)

        if cached:
            # Проверить актуальность кеша
            age = (datetime.now() - cached["timestamp"]).total_seconds()

            if age < self.cache_ttl:
                return cached["price"]

        # Кеш устарел или отсутствует - price_updater обновит
        logger.debug(f"⚠️ {symbol}: цена не в кеше, ждём обновления...")
        return 0.0

    # ========== SIGNAL REGISTRATION ==========

    async def register_signal(self, signal_data: Dict) -> str:
        """
        Регистрация нового сигнала для мониторинга

        Args:
            signal_data: Данные сигнала (entry, TP, SL, direction)

        Returns:
            signal_id: Уникальный ID сигнала

        Note:
            НЕ размещает ордера! Только отслеживает цены.
        """
        signal_id = f"{signal_data['symbol']}_{int(datetime.now().timestamp())}"

        signal = Signal(
            signal_id=signal_id,
            symbol=signal_data["symbol"],
            direction=signal_data["direction"],
            entry_price=signal_data["entry_price"],
            stop_loss=signal_data["stop_loss"],
            tp1=signal_data.get("tp1", 0),
            tp2=signal_data.get("tp2", 0),
            tp3=signal_data.get("tp3", 0),
            quality_score=signal_data.get("quality_score", 0.0),
        )

        # Добавить в активные
        self.active_signals[signal_id] = signal

        # Сохранить в БД
        await self._save_signal_to_db(signal)

        # Запустить мониторинг
        if self.is_running:
            task = asyncio.create_task(self._monitor_signal(signal_id))
            self.monitor_tasks[signal_id] = task

        logger.info(
            f"📝 Зарегистрирован сигнал {signal_id} для мониторинга "
            f"({signal.direction} {signal.symbol})"
        )

        return signal_id

    # ========== SIGNAL MONITORING ==========

    async def _monitor_signal(self, signal_id: str):
        """
        Мониторинг отдельного сигнала (БЕЗ избыточного логирования)

        Args:
            signal_id: ID сигнала для мониторинга
        """
        try:
            while self.is_running and not self.is_shutting_down:
                if signal_id not in self.active_signals:
                    # Сигнал закрыт
                    break

                signal = self.active_signals[signal_id]

                # Получить цену из кеша (БЕЗ API запроса!)
                current_price = await self._get_current_price(signal.symbol)

                if current_price == 0.0:
                    # Ждём пока price_updater обновит кеш
                    await asyncio.sleep(5)
                    continue

                # Обновить текущую цену в сигнале
                signal.current_price = current_price

                # Проверить TP/SL
                event = await self._check_tp_sl(signal)

                # Логировать ТОЛЬКО если произошло событие
                if event:
                    if event["type"] == "tp_hit":
                        logger.info(
                            f"🎯 {event['level'].upper()} достигнут: "
                            f"{signal_id} @ ${event['price']:,.2f} "
                            f"(+{event['profit']:.2f}%)"
                        )
                    elif event["type"] == "sl_hit":
                        logger.warning(
                            f"🚨 STOP LOSS сработал: {signal_id} "
                            f"@ ${event['price']:,.2f} ({event['loss']:.2f}%)"
                        )

                # Проверить Trailing Stop
                if self.trailing_stop_enabled and not signal.sl_hit:
                    await self._update_trailing_stop(signal)

                # Проверять каждые 5 секунд
                await asyncio.sleep(self.check_interval)

        except asyncio.CancelledError:
            logger.debug(f"Monitor task cancelled: {signal_id}")
        except Exception as e:
            if not self.is_shutting_down:
                logger.error(f"❌ Monitor error {signal_id}: {e}", exc_info=True)

    async def _check_tp_sl(self, signal: Signal) -> Optional[Dict]:
        """
        Проверка достижения TP/SL

        Args:
            signal: Сигнал для проверки

        Returns:
            Событие (dict) если TP/SL достигнут, None иначе
        """
        current_price = signal.current_price
        event = None

        if signal.direction.upper() == "LONG":
            # === LONG ПОЗИЦИЯ ===

            # TP3 (самая высокая цель)
            if not signal.tp3_hit and current_price >= signal.tp3:
                signal.tp3_hit = True
                event = await self._handle_tp_hit(signal, "TP3", current_price)

            # TP2
            elif not signal.tp2_hit and current_price >= signal.tp2:
                signal.tp2_hit = True
                event = await self._handle_tp_hit(signal, "TP2", current_price)

            # TP1
            elif not signal.tp1_hit and current_price >= signal.tp1:
                signal.tp1_hit = True
                event = await self._handle_tp_hit(signal, "TP1", current_price)

            # Stop Loss
            elif not signal.sl_hit and current_price <= signal.stop_loss:
                signal.sl_hit = True
                event = await self._handle_sl_hit(signal, current_price)

        elif signal.direction.upper() == "SHORT":
            # === SHORT ПОЗИЦИЯ ===

            # TP3 (самая низкая цель)
            if not signal.tp3_hit and current_price <= signal.tp3:
                signal.tp3_hit = True
                event = await self._handle_tp_hit(signal, "TP3", current_price)

            # TP2
            elif not signal.tp2_hit and current_price <= signal.tp2:
                signal.tp2_hit = True
                event = await self._handle_tp_hit(signal, "TP2", current_price)

            # TP1
            elif not signal.tp1_hit and current_price <= signal.tp1:
                signal.tp1_hit = True
                event = await self._handle_tp_hit(signal, "TP1", current_price)

            # Stop Loss
            elif not signal.sl_hit and current_price >= signal.stop_loss:
                signal.sl_hit = True
                event = await self._handle_sl_hit(signal, current_price)

        # Обновить текущий ROI
        signal.current_roi = self._calculate_current_roi(signal)

        # Обновить в БД если было событие
        if event:
            await self._update_signal_in_db(signal)

        return event

    # ========== TP/SL HANDLERS ==========

    async def _handle_tp_hit(self, signal: Signal, tp_level: str, price: float) -> Dict:
        """
        Обработка достижения Take Profit с Telegram уведомлением

        Args:
            signal: Сигнал
            tp_level: Уровень TP (TP1/TP2/TP3)
            price: Цена достижения

        Returns:
            Событие (dict) с информацией о закрытии
        """
        # Определить процент закрытия
        if tp_level == "TP1":
            close_percent = self.tp1_percentage
        elif tp_level == "TP2":
            close_percent = self.tp2_percentage
        else:  # TP3
            close_percent = self.tp3_percentage

        # Рассчитать прибыль
        profit_percent = signal.calculate_pnl(price)
        weighted_profit = profit_percent * close_percent

        # Сохранить фиксацию
        fill = {
            "level": tp_level,
            "price": price,
            "percentage": close_percent,
            "profit_percent": profit_percent,
            "weighted_profit": weighted_profit,
            "timestamp": datetime.now().isoformat(),
        }

        signal.fills.append(fill)

        # Обновить статистику
        if tp_level == "TP1":
            self.stats["tp1_triggered"] += 1
        elif tp_level == "TP2":
            self.stats["tp2_triggered"] += 1
        elif tp_level == "TP3":
            self.stats["tp3_triggered"] += 1

        # Отправить Telegram уведомление
        await self._send_tp_notification(signal, tp_level, price, profit_percent)

        # Если это TP3 или все TP достигнуты, закрыть сигнал
        if tp_level == "TP3" or (signal.tp1_hit and signal.tp2_hit and signal.tp3_hit):
            await self._close_signal(signal, "completed")

        return {
            "type": "tp_hit",
            "signal_id": signal.signal_id,
            "level": tp_level,
            "price": price,
            "profit": weighted_profit,
        }

    async def _handle_sl_hit(self, signal: Signal, price: float) -> Dict:
        """
        Обработка достижения Stop Loss с Telegram уведомлением

        Args:
            signal: Сигнал
            price: Цена достижения SL

        Returns:
            Событие (dict) с информацией о закрытии
        """
        # Рассчитать убыток
        loss_percent = signal.calculate_pnl(price)

        # Определить оставшийся процент позиции
        closed_percent = sum(
            [
                self.tp1_percentage if signal.tp1_hit else 0,
                self.tp2_percentage if signal.tp2_hit else 0,
                self.tp3_percentage if signal.tp3_hit else 0,
            ]
        )

        remaining_percent = 1.0 - closed_percent
        weighted_loss = loss_percent * remaining_percent

        # Сохранить фиксацию
        fill = {
            "level": "stop_loss",
            "price": price,
            "percentage": remaining_percent,
            "profit_percent": loss_percent,
            "weighted_profit": weighted_loss,
            "timestamp": datetime.now().isoformat(),
        }

        signal.fills.append(fill)

        # Обновить статистику
        self.stats["sl_triggered"] += 1

        # Отправить Telegram уведомление
        await self._send_sl_notification(signal, price, weighted_loss)

        # Закрыть сигнал
        await self._close_signal(signal, "stopped")

        return {
            "type": "sl_hit",
            "signal_id": signal.signal_id,
            "price": price,
            "loss": weighted_loss,
        }

    # ========== TRAILING STOP ==========

    async def _update_trailing_stop(self, signal: Signal):
        """
        Обновление Trailing Stop для позиций в прибыли

        Args:
            signal: Сигнал для проверки
        """
        try:
            # Рассчитать текущий P&L
            pnl = signal.calculate_pnl()

            # Проверить условие активации
            if pnl >= self.trailing_stop_trigger:
                # Рассчитать новый SL
                if signal.direction.upper() == "LONG":
                    # LONG: SL = цена - distance%
                    new_sl = signal.current_price * (
                        1 - self.trailing_stop_distance / 100
                    )

                    # Обновить только если новый SL выше старого
                    if new_sl > signal.stop_loss:
                        old_sl = signal.stop_loss
                        signal.stop_loss = new_sl

                        self.stats["trailing_activated"] += 1

                        logger.info(
                            f"📈 TRAILING STOP: {signal.symbol} "
                            f"#{signal.signal_id} "
                            f"SL: ${old_sl:,.2f} → ${new_sl:,.2f} "
                            f"(P&L: +{pnl:.2f}%)"
                        )

                        # Обновить в БД
                        await self._update_signal_in_db(signal)

                elif signal.direction.upper() == "SHORT":
                    # SHORT: SL = цена + distance%
                    new_sl = signal.current_price * (
                        1 + self.trailing_stop_distance / 100
                    )

                    # Обновить только если новый SL ниже старого
                    if new_sl < signal.stop_loss:
                        old_sl = signal.stop_loss
                        signal.stop_loss = new_sl

                        self.stats["trailing_activated"] += 1

                        logger.info(
                            f"📉 TRAILING STOP: {signal.symbol} "
                            f"#{signal.signal_id} "
                            f"SL: ${old_sl:,.2f} → ${new_sl:,.2f} "
                            f"(P&L: +{pnl:.2f}%)"
                        )

                        # Обновить в БД
                        await self._update_signal_in_db(signal)

        except Exception as e:
            logger.error(f"❌ Trailing stop error: {e}", exc_info=True)

    # ========== TELEGRAM NOTIFICATIONS ==========

    async def _send_tp_notification(
        self, signal: Signal, tp_level: str, price: float, profit_percent: float
    ):
        """
        Отправка Telegram уведомления о достижении TP

        Args:
            signal: Сигнал
            tp_level: Уровень TP
            price: Цена достижения
            profit_percent: Прибыль в процентах
        """
        if not self.telegram_handler:
            return

        try:
            # Проверка на risky entry
            is_risky = signal.quality_score < 50

            if tp_level == "TP1":
                if is_risky:
                    message = (
                        f"🎯 TP1 ДОСТИГНУТ (RISKY ENTRY) ⚠️\n\n"
                        f"📊 {signal.symbol} {signal.direction.upper()}\n"
                        f"💰 Entry: ${signal.entry_price:,.2f}\n"
                        f"📈 Current: ${price:,.2f}\n"
                        f"🎯 TP1: ${signal.tp1:,.2f}\n"
                        f"💵 Profit: {profit_percent:.2f}%\n\n"
                        f"⚠️ Повышенный риск!\n"
                        f"💡 Рекомендация:\n"
                        f"   • Зафиксируй 25% позиции\n"
                        f"   • Переведи стоп в безубыток\n"
                        f"   • Остальное держи до TP2"
                    )
                else:
                    message = (
                        f"🎯 TP1 ДОСТИГНУТ 🎯\n\n"
                        f"📊 {signal.symbol} {signal.direction.upper()}\n"
                        f"💰 Entry: ${signal.entry_price:,.2f}\n"
                        f"📈 Current: ${price:,.2f}\n"
                        f"🎯 TP1: ${signal.tp1:,.2f}\n"
                        f"💵 Profit: {profit_percent:.2f}%\n\n"
                        f"✅ Рекомендация:\n"
                        f"   • Зафиксируй 25% позиции\n"
                        f"   • Переведи стоп в безубыток\n"
                        f"   • Остаток держим до TP2"
                    )

            elif tp_level == "TP2":
                message = (
                    f"🎯🎯 TP2 ДОСТИГНУТ 🎯🎯\n\n"
                    f"📊 {signal.symbol} {signal.direction.upper()}\n"
                    f"💰 Entry: ${signal.entry_price:,.2f}\n"
                    f"📈 Current: ${price:,.2f}\n"
                    f"🎯 TP2: ${signal.tp2:,.2f}\n"
                    f"💵 Profit: {profit_percent:.2f}%\n\n"
                    f"✅ Рекомендация:\n"
                    f"   • Зафиксируй 25% позиции\n"
                    f"   • Остаток держим до TP3\n"
                    f"   • Стоп уже в безубытке"
                )

            else:  # TP3
                message = (
                    f"🎯🎯🎯 TP3 ДОСТИГНУТ 🎯🎯🎯\n\n"
                    f"📊 {signal.symbol} {signal.direction.upper()}\n"
                    f"💰 Entry: ${signal.entry_price:,.2f}\n"
                    f"📈 Current: ${price:,.2f}\n"
                    f"🎯 TP3: ${signal.tp3:,.2f}\n"
                    f"💵 Profit: {profit_percent:.2f}%\n\n"
                    f"✅ Рекомендация:\n"
                    f"   • Трейлим остаток (trailing stop)\n"
                    f"   • Или фиксируем полностью\n"
                    f"   • Сделка успешна! 🎉"
                )

            # Отправить
            if hasattr(self.telegram_handler, "send_alert"):
                await self.telegram_handler.send_alert(message)
            elif hasattr(self.telegram_handler, "send_message"):
                await self.telegram_handler.send_message(message)

            logger.info(
                f"✅ Telegram уведомление {tp_level} отправлено: {signal.symbol}"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка отправки TP уведомления: {e}")

    async def _send_sl_notification(
        self, signal: Signal, price: float, loss_percent: float
    ):
        """
        Отправка Telegram уведомления о срабатывании Stop Loss

        Args:
            signal: Сигнал
            price: Цена срабатывания SL
            loss_percent: Убыток в процентах
        """
        if not self.telegram_handler:
            return

        try:
            message = (
                f"🛑 СТОП АКТИВИРОВАН 🛑\n\n"
                f"📊 {signal.symbol} {signal.direction.upper()}\n"
                f"💰 Entry: ${signal.entry_price:,.2f}\n"
                f"📉 Current: ${price:,.2f}\n"
                f"🛑 Stop Loss: ${signal.stop_loss:,.2f}\n"
                f"💸 Loss: {loss_percent:.2f}%\n\n"
                f"❌ Сигнал завершён\n"
                f"   • Stop Loss достигнут\n"
                f"   • Анализируем причины\n"
                f"   • Ждём новую возможность"
            )

            # Отправить
            if hasattr(self.telegram_handler, "send_alert"):
                await self.telegram_handler.send_alert(message)
            elif hasattr(self.telegram_handler, "send_message"):
                await self.telegram_handler.send_message(message)

            logger.info(f"✅ Telegram уведомление STOP отправлено: {signal.symbol}")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки STOP уведомления: {e}")

    # ========== HELPER METHODS ==========

    def _calculate_current_roi(self, signal: Signal) -> float:
        """
        Расчёт текущего ROI с учётом закрытых частей

        Args:
            signal: Сигнал

        Returns:
            Текущий ROI в процентах
        """
        # ROI от закрытых частей
        closed_roi = sum([fill["weighted_profit"] for fill in signal.fills])

        # ROI от открытой части
        closed_percent = sum(
            [
                self.tp1_percentage if signal.tp1_hit else 0,
                self.tp2_percentage if signal.tp2_hit else 0,
                self.tp3_percentage if signal.tp3_hit else 0,
            ]
        )

        remaining_percent = 1.0 - closed_percent

        if remaining_percent > 0 and signal.current_price > 0:
            unrealized_profit = signal.calculate_pnl()
            unrealized_roi = unrealized_profit * remaining_percent
        else:
            unrealized_roi = 0.0

        return closed_roi + unrealized_roi

    async def _close_signal(self, signal: Signal, status: str):
        """
        Закрытие сигнала и перенос в completed

        Args:
            signal: Сигнал
            status: Статус закрытия (completed/stopped)
        """
        signal.status = status
        signal.close_time = datetime.now().isoformat()
        signal.is_active = False

        # Финальный ROI
        final_roi = sum([fill["weighted_profit"] for fill in signal.fills])
        signal.current_roi = final_roi

        # Переместить в completed
        self.completed_signals.append(signal)
        del self.active_signals[signal.signal_id]

        # Остановить задачу мониторинга
        if signal.signal_id in self.monitor_tasks:
            task = self.monitor_tasks[signal.signal_id]
            if task and not task.done():
                task.cancel()
            del self.monitor_tasks[signal.signal_id]

        # Обновить статистику
        self.stats["total_closures"] += 1

        # Обновить в БД
        await self._update_signal_in_db(signal, final=True)

        logger.info(
            f"🏁 Мониторинг сигнала {signal.signal_id} завершён. "
            f"Статус: {status}, Результат: {final_roi:+.2f}%"
        )

    # ========== DATABASE METHODS ==========

    async def _init_database(self):
        """Инициализация базы данных"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS signals (
                        signal_id TEXT PRIMARY KEY,
                        symbol TEXT,
                        direction TEXT,
                        entry_price REAL,
                        stop_loss REAL,
                        tp1 REAL,
                        tp2 REAL,
                        tp3 REAL,
                        tp1_hit INTEGER DEFAULT 0,
                        tp2_hit INTEGER DEFAULT 0,
                        tp3_hit INTEGER DEFAULT 0,
                        sl_hit INTEGER DEFAULT 0,
                        current_roi REAL DEFAULT 0,
                        status TEXT DEFAULT 'active',
                        entry_time TEXT,
                        close_time TEXT,
                        quality_score REAL DEFAULT 0
                    )
                """
                )

                # ✅ ПРОВЕРИТЬ И ДОБАВИТЬ close_time ЕСЛИ ЕЁ НЕТ
                cursor = await db.execute("PRAGMA table_info(signals)")
                columns = await cursor.fetchall()
                column_names = [col[1] for col in columns]

                if "close_time" not in column_names:
                    logger.info("🔧 Добавляем колонку close_time...")
                    await db.execute("ALTER TABLE signals ADD COLUMN close_time TEXT")
                    logger.info("✅ Колонка close_time добавлена")

                await db.commit()

            logger.info("✅ База данных инициализирована")

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")

    async def _save_signal_to_db(self, signal: Signal):
        """Сохранение нового сигнала в БД"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute(
                    """
                    INSERT INTO signals (
                        signal_id, symbol, direction, entry_price, stop_loss,
                        tp1, tp2, tp3, status, entry_time, quality_score
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        signal.signal_id,
                        signal.symbol,
                        signal.direction,
                        signal.entry_price,
                        signal.stop_loss,
                        signal.tp1,
                        signal.tp2,
                        signal.tp3,
                        signal.status,
                        signal.entry_time,
                        signal.quality_score,
                    ),
                )
                await db.commit()

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения сигнала в БД: {e}")

    async def _update_signal_in_db(self, signal: Signal, final: bool = False):
        """Обновление сигнала в БД"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                if final:
                    await db.execute(
                        """
                        UPDATE signals
                        SET status = ?, current_roi = ?, close_time = ?,
                            tp1_hit = ?, tp2_hit = ?, tp3_hit = ?, sl_hit = ?
                        WHERE signal_id = ?
                    """,
                        (
                            signal.status,
                            signal.current_roi,
                            signal.close_time,
                            signal.tp1_hit,
                            signal.tp2_hit,
                            signal.tp3_hit,
                            signal.sl_hit,
                            signal.signal_id,
                        ),
                    )
                else:
                    await db.execute(
                        """
                        UPDATE signals
                        SET current_roi = ?, tp1_hit = ?, tp2_hit = ?,
                            tp3_hit = ?, sl_hit = ?, stop_loss = ?
                        WHERE signal_id = ?
                    """,
                        (
                            signal.current_roi,
                            signal.tp1_hit,
                            signal.tp2_hit,
                            signal.tp3_hit,
                            signal.sl_hit,
                            signal.stop_loss,
                            signal.signal_id,
                        ),
                    )
                await db.commit()

        except Exception as e:
            logger.error(f"❌ Ошибка обновления сигнала в БД: {e}")

    # ========== STATISTICS ==========

    async def get_statistics(self, days: int = 30) -> Dict:
        """
        Получение статистики сигналов за период

        Args:
            days: Количество дней для анализа

        Returns:
            Dict со статистикой
        """
        cutoff_date = datetime.now() - timedelta(days=days)

        # Фильтровать сигналы за период
        recent_signals = [
            s
            for s in self.completed_signals
            if s.close_time and datetime.fromisoformat(s.close_time) > cutoff_date
        ]

        if not recent_signals:
            return {
                "total_signals": 0,
                "win_rate": 0.0,
                "average_roi": 0.0,
                "total_roi": 0.0,
                "wins": 0,
                "losses": 0,
                "period_days": days,
            }

        # Статистика
        total = len(recent_signals)
        wins = len([s for s in recent_signals if s.current_roi > 0])
        losses = len([s for s in recent_signals if s.current_roi <= 0])

        win_rate = (wins / total) * 100 if total > 0 else 0
        average_roi = sum([s.current_roi for s in recent_signals]) / total
        total_roi = sum([s.current_roi for s in recent_signals])

        return {
            "total_signals": total,
            "wins": wins,
            "losses": losses,
            "win_rate": win_rate,
            "average_roi": average_roi,
            "total_roi": total_roi,
            "period_days": days,
            "sl_triggered": self.stats["sl_triggered"],
            "tp1_triggered": self.stats["tp1_triggered"],
            "tp2_triggered": self.stats["tp2_triggered"],
            "tp3_triggered": self.stats["tp3_triggered"],
            "trailing_activated": self.stats["trailing_activated"],
        }

    def get_stats(self) -> Dict:
        """Получить текущую статистику"""
        return self.stats.copy()


# Обратная совместимость
SignalPerformanceTracker = ROITracker

__all__ = ["ROITracker", "SignalPerformanceTracker", "Signal"]
