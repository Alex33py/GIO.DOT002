#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIO Crypto Bot - Position Notifications Module
Real-time уведомления о сопровождении сделки
"""

import asyncio
from datetime import datetime
from typing import Optional, Dict, List
from config.settings import logger


class PositionNotifications:
    """
    Модуль для отправки real-time уведомлений о сопровождении сделки

    Отправляет уведомления при:
    - Достижении TP1/TP2/TP3
    - Risky Entry
    - Досрочном выходе
    - Активации стопа
    """

    def __init__(self, telegram_handler):
        """
        Инициализация модуля уведомлений

        Args:
            telegram_handler: Экземпляр TelegramBotHandler для отправки уведомлений
        """
        self.telegram = telegram_handler
        self.notified_signals = {
            'tp1': set(),  # ID сигналов, для которых отправлено уведомление TP1
            'tp2': set(),  # ID сигналов, для которых отправлено уведомление TP2
            'tp3': set(),  # ID сигналов, для которых отправлено уведомление TP3
            'stop': set(), # ID сигналов, для которых отправлено уведомление STOP
            'early_exit': set()  # ID сигналов с досрочным выходом
        }
        logger.info("✅ PositionNotifications инициализирован")

    async def check_tp_levels(self, signal: Dict) -> None:
        """
        Проверяет достижение уровней TP1/TP2/TP3 и отправляет уведомления

        Args:
            signal: Словарь с данными сигнала
        """
        try:
            signal_id = signal.get('id')
            symbol = signal.get('symbol', 'N/A')
            direction = signal.get('direction', 'N/A')
            entry_price = signal.get('entry_price', 0)
            current_price = signal.get('current_price', 0)
            tp1 = signal.get('tp1', 0)
            tp2 = signal.get('tp2', 0)
            tp3 = signal.get('tp3', 0)
            stop_loss = signal.get('stop_loss', 0)
            quality_score = signal.get('quality_score', 0)

            # Проверка на risky entry (качество сигнала < 50%)
            is_risky = quality_score < 50

            # Проверка достижения TP1
            if self._check_tp_reached(current_price, tp1, direction) and signal_id not in self.notified_signals['tp1']:
                await self._send_tp1_notification(signal, is_risky)
                self.notified_signals['tp1'].add(signal_id)

            # Проверка достижения TP2
            elif self._check_tp_reached(current_price, tp2, direction) and signal_id not in self.notified_signals['tp2']:
                await self._send_tp2_notification(signal)
                self.notified_signals['tp2'].add(signal_id)

            # Проверка достижения TP3
            elif self._check_tp_reached(current_price, tp3, direction) and signal_id not in self.notified_signals['tp3']:
                await self._send_tp3_notification(signal)
                self.notified_signals['tp3'].add(signal_id)

            # Проверка активации стопа
            elif self._check_stop_hit(current_price, stop_loss, direction) and signal_id not in self.notified_signals['stop']:
                await self._send_stop_notification(signal)
                self.notified_signals['stop'].add(signal_id)

        except Exception as e:
            logger.error(f"❌ Ошибка check_tp_levels: {e}")

    def _check_tp_reached(self, current_price: float, tp_level: float, direction: str) -> bool:
        """
        Проверяет достижение уровня TP

        Args:
            current_price: Текущая цена
            tp_level: Уровень TP
            direction: Направление сделки (LONG/SHORT)

        Returns:
            True если TP достигнут, иначе False
        """
        if direction == "LONG":
            return current_price >= tp_level
        elif direction == "SHORT":
            return current_price <= tp_level
        return False

    def _check_stop_hit(self, current_price: float, stop_loss: float, direction: str) -> bool:
        """
        Проверяет активацию стопа

        Args:
            current_price: Текущая цена
            stop_loss: Уровень стоп-лосса
            direction: Направление сделки (LONG/SHORT)

        Returns:
            True если стоп активирован, иначе False
        """
        if direction == "LONG":
            return current_price <= stop_loss
        elif direction == "SHORT":
            return current_price >= stop_loss
        return False

    async def _send_tp1_notification(self, signal: Dict, is_risky: bool = False) -> None:
        """
        Отправляет уведомление о достижении TP1

        Args:
            signal: Словарь с данными сигнала
            is_risky: Флаг risky entry
        """
        try:
            symbol = signal.get('symbol', 'N/A')
            direction = signal.get('direction', 'N/A')
            entry_price = signal.get('entry_price', 0)
            current_price = signal.get('current_price', 0)
            tp1 = signal.get('tp1', 0)
            profit_percent = ((current_price - entry_price) / entry_price * 100) if direction == "LONG" else ((entry_price - current_price) / entry_price * 100)

            # Формируем сообщение
            if is_risky:
                message = (
                    f"🎯 TP1 ДОСТИГНУТ (RISKY ENTRY) 🎯\n\n"
                    f"⚠️ Повышенный риск!\n\n"
                    f"📊 {symbol} {direction}\n"
                    f"💰 Entry: ${entry_price:.2f}\n"
                    f"📈 Current: ${current_price:.2f}\n"
                    f"🎯 TP1: ${tp1:.2f}\n"
                    f"💵 Profit: {profit_percent:.2f}%\n\n"
                    f"✅ Рекомендация:\n"
                    f"   • Зафиксируй 50% позиции\n"
                    f"   • Переведи стоп в безубыток\n"
                    f"   • Остаток держим до TP2"
                )
            else:
                message = (
                    f"🎯 TP1 ДОСТИГНУТ 🎯\n\n"
                    f"📊 {symbol} {direction}\n"
                    f"💰 Entry: ${entry_price:.2f}\n"
                    f"📈 Current: ${current_price:.2f}\n"
                    f"🎯 TP1: ${tp1:.2f}\n"
                    f"💵 Profit: {profit_percent:.2f}%\n\n"
                    f"✅ Рекомендация:\n"
                    f"   • Зафиксируй 25% позиции\n"
                    f"   • Переведи стоп в безубыток\n"
                    f"   • Остаток держим до TP2"
                )

            await self.telegram.send_alert(message)
            logger.info(f"✅ Отправлено уведомление TP1 для {symbol}")

        except Exception as e:
            logger.error(f"❌ Ошибка _send_tp1_notification: {e}")

    async def _send_tp2_notification(self, signal: Dict) -> None:
        """
        Отправляет уведомление о достижении TP2

        Args:
            signal: Словарь с данными сигнала
        """
        try:
            symbol = signal.get('symbol', 'N/A')
            direction = signal.get('direction', 'N/A')
            entry_price = signal.get('entry_price', 0)
            current_price = signal.get('current_price', 0)
            tp2 = signal.get('tp2', 0)
            profit_percent = ((current_price - entry_price) / entry_price * 100) if direction == "LONG" else ((entry_price - current_price) / entry_price * 100)

            message = (
                f"🎯 TP2 ДОСТИГНУТ 🎯\n\n"
                f"📊 {symbol} {direction}\n"
                f"💰 Entry: ${entry_price:.2f}\n"
                f"📈 Current: ${current_price:.2f}\n"
                f"🎯 TP2: ${tp2:.2f}\n"
                f"💵 Profit: {profit_percent:.2f}%\n\n"
                f"✅ Рекомендация:\n"
                f"   • Зафиксируй 50% позиции\n"
                f"   • Остаток держим до TP3\n"
                f"   • Стоп уже в безубытке"
            )

            await self.telegram.send_alert(message)
            logger.info(f"✅ Отправлено уведомление TP2 для {symbol}")

        except Exception as e:
            logger.error(f"❌ Ошибка _send_tp2_notification: {e}")

    async def _send_tp3_notification(self, signal: Dict) -> None:
        """
        Отправляет уведомление о достижении TP3

        Args:
            signal: Словарь с данными сигнала
        """
        try:
            symbol = signal.get('symbol', 'N/A')
            direction = signal.get('direction', 'N/A')
            entry_price = signal.get('entry_price', 0)
            current_price = signal.get('current_price', 0)
            tp3 = signal.get('tp3', 0)
            profit_percent = ((current_price - entry_price) / entry_price * 100) if direction == "LONG" else ((entry_price - current_price) / entry_price * 100)

            message = (
                f"🎯 TP3 ДОСТИГНУТ 🎯\n\n"
                f"📊 {symbol} {direction}\n"
                f"💰 Entry: ${entry_price:.2f}\n"
                f"📈 Current: ${current_price:.2f}\n"
                f"🎯 TP3: ${tp3:.2f}\n"
                f"💵 Profit: {profit_percent:.2f}%\n\n"
                f"✅ Рекомендация:\n"
                f"   • Трейлим остаток (trailing stop)\n"
                f"   • Или фиксируем полностью\n"
                f"   • Сделка успешна! 🎉"
            )

            await self.telegram.send_alert(message)
            logger.info(f"✅ Отправлено уведомление TP3 для {symbol}")

        except Exception as e:
            logger.error(f"❌ Ошибка _send_tp3_notification: {e}")

    async def _send_stop_notification(self, signal: Dict) -> None:
        """
        Отправляет уведомление об активации стопа

        Args:
            signal: Словарь с данными сигнала
        """
        try:
            symbol = signal.get('symbol', 'N/A')
            direction = signal.get('direction', 'N/A')
            entry_price = signal.get('entry_price', 0)
            current_price = signal.get('current_price', 0)
            stop_loss = signal.get('stop_loss', 0)
            loss_percent = ((entry_price - current_price) / entry_price * 100) if direction == "LONG" else ((current_price - entry_price) / entry_price * 100)

            message = (
                f"🛑 СТОП АКТИВИРОВАН 🛑\n\n"
                f"📊 {symbol} {direction}\n"
                f"💰 Entry: ${entry_price:.2f}\n"
                f"📉 Current: ${current_price:.2f}\n"
                f"🛑 Stop Loss: ${stop_loss:.2f}\n"
                f"💸 Loss: -{loss_percent:.2f}%\n\n"
                f"❌ Сделка закрыта\n"
                f"   • Убыток зафиксирован\n"
                f"   • Анализируем причины\n"
                f"   • Ждём новую возможность"
            )

            await self.telegram.send_alert(message)
            logger.info(f"✅ Отправлено уведомление STOP для {symbol}")

        except Exception as e:
            logger.error(f"❌ Ошибка _send_stop_notification: {e}")

    async def check_early_exit(self, signal: Dict, volume_data: Dict) -> None:
        """
        Проверяет условия для досрочного выхода (падение объёмов)

        Args:
            signal: Словарь с данными сигнала
            volume_data: Данные об объёмах торговли
        """
        try:
            signal_id = signal.get('id')

            # Проверка: объёмы падают, подтверждения нет
            if signal_id not in self.notified_signals['early_exit']:
                volume_declining = volume_data.get('declining', False)
                no_confirmation = volume_data.get('no_confirmation', False)

                if volume_declining and no_confirmation:
                    await self._send_early_exit_notification(signal)
                    self.notified_signals['early_exit'].add(signal_id)

        except Exception as e:
            logger.error(f"❌ Ошибка check_early_exit: {e}")

    async def _send_early_exit_notification(self, signal: Dict) -> None:
        """
        Отправляет уведомление о досрочном выходе

        Args:
            signal: Словарь с данными сигнала
        """
        try:
            symbol = signal.get('symbol', 'N/A')
            direction = signal.get('direction', 'N/A')
            entry_price = signal.get('entry_price', 0)
            current_price = signal.get('current_price', 0)
            tp2 = signal.get('tp2', 0)

            message = (
                f"⚠️ ДОСРОЧНЫЙ ВЫХОД ⚠️\n\n"
                f"📊 {symbol} {direction}\n"
                f"💰 Entry: ${entry_price:.2f}\n"
                f"📈 Current: ${current_price:.2f}\n"
                f"🎯 Рекомендуемый выход: ${tp2:.2f}\n\n"
                f"⚠️ Причина:\n"
                f"   • Объёмы падают\n"
                f"   • Подтверждения нет\n"
                f"   • Рекомендуется выйти на TP2"
            )

            await self.telegram.send_alert(message)
            logger.info(f"✅ Отправлено уведомление EARLY EXIT для {symbol}")

        except Exception as e:
            logger.error(f"❌ Ошибка _send_early_exit_notification: {e}")

    def reset_notifications(self, signal_id: int) -> None:
        """
        Сбрасывает уведомления для сигнала (например, при закрытии сделки)

        Args:
            signal_id: ID сигнала
        """
        for key in self.notified_signals:
            self.notified_signals[key].discard(signal_id)
        logger.info(f"✅ Сброшены уведомления для сигнала #{signal_id}")
