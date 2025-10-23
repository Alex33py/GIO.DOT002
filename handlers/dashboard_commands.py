#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard Commands - команды для работы с дашбордами
/market - главный дашборд рынка
/dashboard - GIO Dashboard
/dashboard live - GIO Dashboard с автообновлением
"""

import re
import asyncio
from typing import Optional
from datetime import datetime, timedelta
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

        # ✅ ИНИЦИАЛИЗАЦИЯ GIODashboardHandler
        try:
            from handlers.dashboard_handler import GIODashboardHandler

            self.dashboard_handler = GIODashboardHandler(bot_instance)
            logger.info("✅ GIODashboardHandler инициализирован")
        except ImportError as e:
            logger.error(f"❌ Не удалось импортировать GIODashboardHandler: {e}")
            self.dashboard_handler = None

        self.register_handlers()
        logger.info("✅ DashboardCommands зарегистрированы")

    def register_handlers(self):
        """Регистрация обработчиков команд"""
        # /market
        self.telegram_bot.register_message_handler(
            self.market_command, commands=["market"], pass_bot=True
        )
        logger.info("✅ Зарегистрирована команда /market")

        # ✅ /dashboard (с поддержкой "live")
        if self.dashboard_handler:
            self.telegram_bot.register_message_handler(
                self.dashboard_command, commands=["dashboard"], pass_bot=True
            )
            logger.info("✅ Зарегистрирована команда /dashboard [live]")

            # ✅ /gio
            self.telegram_bot.register_message_handler(
                self.gio_command, commands=["gio"], pass_bot=True
            )
            logger.info("✅ Зарегистрирована команда /gio")

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

    # ✅ НОВЫЙ МЕТОД: /dashboard [live]
    async def dashboard_command(self, message: Message):
        """
        Обработчик команды /dashboard [live] [SYMBOL]

        Использование:
            /dashboard - обычный dashboard для BTCUSDT
            /dashboard ETHUSDT - dashboard для ETHUSDT
            /dashboard live - dashboard с автообновлением (60 мин)
            /dashboard live ETHUSDT - live dashboard для ETHUSDT
        """
        try:
            # Парсим команду
            parts = message.text.split()
            is_live = len(parts) > 1 and parts[1].lower() == "live"

            # Извлекаем символ
            if is_live and len(parts) > 2:
                symbol = self._normalize_symbol(parts[2])
            elif not is_live and len(parts) > 1:
                symbol = self._normalize_symbol(parts[1])
            else:
                symbol = "BTCUSDT"

            logger.info(
                f"📊 /dashboard {'live' if is_live else ''} {symbol} "
                f"(user: {message.from_user.id})"
            )

            if is_live:
                await self._dashboard_live(message, symbol)
            else:
                await self._dashboard_normal(message, symbol)

        except Exception as e:
            logger.error(f"❌ Ошибка обработки /dashboard: {e}", exc_info=True)
            await self.telegram_bot.send_message(
                message.chat.id, f"❌ Ошибка: {str(e)}"
            )

    # ✅ НОВЫЙ МЕТОД: /gio
    async def gio_command(self, message: Message):
        """
        Обработчик команды /gio [SYMBOL]

        Использование:
            /gio - GIO Dashboard для BTCUSDT
            /gio ETHUSDT - GIO Dashboard для ETHUSDT
        """
        try:
            # Извлекаем символ
            parts = message.text.split()
            symbol = self._normalize_symbol(parts[1]) if len(parts) > 1 else "BTCUSDT"

            logger.info(f"📊 /gio {symbol} (user: {message.from_user.id})")

            await self._dashboard_normal(message, symbol)

        except Exception as e:
            logger.error(f"❌ Ошибка обработки /gio: {e}", exc_info=True)
            await self.telegram_bot.send_message(
                message.chat.id, f"❌ Ошибка: {str(e)}"
            )

    async def _dashboard_normal(self, message: Message, symbol: str):
        """Обычный dashboard (без автообновления)"""
        if not self.dashboard_handler:
            await self.telegram_bot.send_message(
                message.chat.id, "❌ GIODashboardHandler не доступен"
            )
            return

        loading_msg = await self.telegram_bot.send_message(
            message.chat.id, f"📊 Загрузка GIO Dashboard ({symbol})..."
        )

        try:
            dashboard_text = await self.dashboard_handler._build_dashboard(symbol)

            await self.telegram_bot.delete_message(
                message.chat.id, loading_msg.message_id
            )

            # ✅ ПРАВИЛЬНЫЙ ФОРМАТ ДЛЯ TELEBOT
            await self.telegram_bot.send_message(
                message.chat.id,
                dashboard_text,
                parse_mode="HTML",  # ✅ Правильно для telebot
                disable_web_page_preview=True,  # ✅ Отключает превью ссылок
            )

            logger.info(f"✅ GIO Dashboard {symbol} отправлен")

        except Exception as e:
            logger.error(f"❌ Ошибка генерации dashboard: {e}", exc_info=True)
            await self.telegram_bot.edit_message_text(
                f"❌ Ошибка: {str(e)}",
                message.chat.id,
                loading_msg.message_id,
            )

    async def _dashboard_live(self, message: Message, symbol: str):
        """Dashboard с автообновлением (60 минут)"""
        if not self.dashboard_handler:
            await self.telegram_bot.send_message(
                message.chat.id, "❌ GIODashboardHandler не доступен"
            )
            return

        loading_msg = await self.telegram_bot.send_message(
            message.chat.id, f"📊 Загрузка GIO Dashboard Live ({symbol})..."
        )

        try:
            # Генерируем первый dashboard
            dashboard_text = await self.dashboard_handler._build_dashboard(symbol)

            # Добавляем индикатор автообновления
            end_time = datetime.now() + timedelta(minutes=60)
            end_time_str = end_time.strftime("%H:%M")
            dashboard_text += f"\n\n🔄 <i>Автообновление: каждые 60 сек | Активно до {end_time_str}</i>"

            # ✅ ПРАВИЛЬНЫЙ ФОРМАТ ДЛЯ TELEBOT
            await self.telegram_bot.edit_message_text(
                dashboard_text,
                message.chat.id,
                loading_msg.message_id,
                parse_mode="HTML",  # ✅ Правильно
                disable_web_page_preview=True,  # ✅ Отключает превью ссылок
            )

            logger.info(
                f"✅ Live dashboard {symbol} запущен для user {message.from_user.id}"
            )

            # Запускаем автообновление
            asyncio.create_task(
                self._auto_update_dashboard(loading_msg, message.from_user.id, symbol)
            )

        except Exception as e:
            logger.error(f"❌ Ошибка live dashboard: {e}", exc_info=True)
            await self.telegram_bot.edit_message_text(
                f"❌ Ошибка: {str(e)}",
                message.chat.id,
                loading_msg.message_id,
            )

    async def _auto_update_dashboard(self, message, user_id: int, symbol: str):
        """Фоновое автообновление dashboard каждые 60 секунд"""
        try:
            logger.info(f"✅ Starting auto-update for user {user_id}")

            end_time = datetime.now() + timedelta(minutes=60)
            update_count = 0

            while datetime.now() < end_time:
                await asyncio.sleep(60)  # Ждём 60 секунд

                try:
                    update_count += 1
                    time_left = int((end_time - datetime.now()).total_seconds() / 60)

                    # Генерируем новый dashboard
                    dashboard_text = await self.dashboard_handler._build_dashboard(
                        symbol
                    )

                    # Добавляем индикатор
                    dashboard_text += f"\n\n🔄 <i>Обновлено #{update_count} | Осталось ~{time_left} мин</i>"

                    # ✅ ПРАВИЛЬНЫЙ ФОРМАТ ДЛЯ TELEBOT
                    await self.telegram_bot.edit_message_text(
                        dashboard_text,
                        message.chat.id,
                        message.message_id,
                        parse_mode="HTML",  # ✅ Правильно
                        disable_web_page_preview=True,  # ✅ Отключает превью ссылок
                    )

                    logger.info(
                        f"🔄 Dashboard updated #{update_count} for user {user_id}"
                    )

                except Exception as e:
                    if "message is not modified" in str(e).lower():
                        logger.debug("Dashboard unchanged, skipping")
                        continue
                    else:
                        logger.error(f"Error updating dashboard: {e}")
                        break

        except Exception as e:
            logger.error(f"Auto-update task error: {e}")

        finally:
            logger.info(f"🛑 Live dashboard stopped for user {user_id}")

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

        return self._normalize_symbol(text)

    def _normalize_symbol(self, text: str) -> str:
        """Нормализует символ к формату XXXUSDT"""
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
