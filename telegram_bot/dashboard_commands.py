#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard Commands - команды для работы с дашбордами
/market - главный дашборд рынка
"""

import re
from typing import Optional
from telebot.async_telebot import AsyncTeleBot
from telebot.types import Message
from config.settings import logger, TRACKED_SYMBOLS


class DashboardCommands:
    """Обработчики команд дашбордов"""

    def __init__(self, bot: AsyncTeleBot, bot_instance):
        """
        Args:
            bot: Экземпляр AsyncTeleBot
            bot_instance: Экземпляр GIOCryptoBot
        """
        self.telegram_bot = bot
        self.bot = bot_instance
        self.register_handlers()
        logger.info("✅ DashboardCommands зарегистрированы")

    def register_handlers(self):
        """Регистрация обработчиков команд"""
        self.telegram_bot.register_message_handler(
            self.market_command, commands=["market"], pass_bot=True
        )
        logger.info("✅ Зарегистрирована команда /market")

    async def market_command(self, message: Message):
        """
        Обработчик команды /market

        Использование:
            /market - показать дашборд для BTCUSDT (по умолчанию)
            /market ETHUSDT - показать дашборд для ETHUSDT
            /market eth - показать дашборд для ETHUSDT (автодополнение)
        """
        try:
            # Извлекаем символ из команды
            symbol = self._extract_symbol(message.text)

            logger.info(
                f"📊 /market запрошен для {symbol} (user: {message.from_user.id})"
            )

            # Проверяем доступность MarketDashboard
            if not hasattr(self.bot, "market_dashboard"):
                await self.telegram_bot.send_message(
                    message.chat.id,
                    "❌ Market Dashboard не инициализирован. "
                    "Обратитесь к администратору.",
                )
                return

            # Отправляем "Загрузка..." сообщение
            loading_msg = await self.telegram_bot.send_message(
                message.chat.id, f"⏳ Загрузка dashboard для {symbol}..."
            )

            # Генерируем dashboard
            try:
                dashboard_text = await self.bot.market_dashboard.generate_dashboard(
                    symbol
                )

                # Удаляем "Загрузка..." и отправляем dashboard
                await self.telegram_bot.delete_message(
                    message.chat.id, loading_msg.message_id
                )

                await self.telegram_bot.send_message(
                    message.chat.id, dashboard_text, parse_mode="Markdown"
                )

                logger.info(
                    f"✅ Dashboard для {symbol} отправлен (user: {message.from_user.id})"
                )

            except Exception as e:
                logger.error(
                    f"❌ Ошибка генерации dashboard для {symbol}: {e}", exc_info=True
                )

                await self.telegram_bot.edit_message_text(
                    f"❌ Ошибка генерации dashboard для {symbol}:\n{str(e)}",
                    message.chat.id,
                    loading_msg.message_id,
                )

        except Exception as e:
            logger.error(f"❌ Ошибка обработки /market: {e}", exc_info=True)
            await self.telegram_bot.send_message(
                message.chat.id, f"❌ Ошибка выполнения команды: {str(e)}"
            )

    def _extract_symbol(self, text: str) -> str:
        """
        Извлекает символ из текста команды

        Args:
            text: Текст команды (например, "/market ETHUSDT" или "/market eth")

        Returns:
            Символ в формате "BTCUSDT"
        """
        # Удаляем команду /market
        text = text.replace("/market", "").strip()

        # Если нет параметра, возвращаем BTCUSDT по умолчанию
        if not text:
            return "BTCUSDT"

        # Преобразуем в верхний регистр
        symbol = text.upper()

        # Автодополнение USDT если не указано
        if not symbol.endswith("USDT"):
            symbol = f"{symbol}USDT"

        # Проверяем что символ в списке отслеживаемых
        if symbol not in TRACKED_SYMBOLS:
            logger.warning(
                f"⚠️ Символ {symbol} не в TRACKED_SYMBOLS, "
                f"но продолжаем (может быть валидным)"
            )

        return symbol


# Экспорт
__all__ = ["DashboardCommands"]
