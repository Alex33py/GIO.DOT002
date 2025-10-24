#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIO Crypto Bot - Telegram Bot Handler
Полный обработчик Telegram команд с real-time уведомлениями
"""

import asyncio
import os
import time
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from telegram import Update
from handlers.dashboard_handler import GIODashboardHandler
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode
from config.settings import logger, TELEGRAM_CONFIG, DATA_DIR
from handlers.unified_dashboard import UnifiedDashboardHandler
import pandas as pd
import sqlite3
from handlers.support_resistance_detector import AdvancedSupportResistanceDetector

from telegram.request import HTTPXRequest
from ai.gemini_interpreter import GeminiInterpreter
from config.settings import GEMINI_API_KEY


class TelegramBotHandler:
    """Обработчик Telegram бота с полным функционалом"""

    def __init__(self, bot_instance):
        self.bot_instance = bot_instance
        self.token = TELEGRAM_CONFIG.get("token", "")
        self.chat_id = TELEGRAM_CONFIG.get("chat_id", "")
        self.user_id = self.chat_id
        self.enabled = TELEGRAM_CONFIG.get("enabled", False)
        self.auto_signals = TELEGRAM_CONFIG.get("auto_signals", True)
        self.application = None
        self.is_running = False
        self.gio_dashboard = GIODashboardHandler(bot_instance)
        self.db_path = os.path.join(DATA_DIR, "gio_crypto_bot.db")
        try:
            from core.market_dashboard import MarketDashboard

            self.market_dashboard = MarketDashboard(bot_instance)
            logger.info("✅ MarketDashboard initialized in TelegramBotHandler")
        except ImportError as e:
            logger.warning(f"⚠️ MarketDashboard not found: {e}")
            self.market_dashboard = None
        self.unified_dashboard_handler = UnifiedDashboardHandler(self)
        self.sr_detector = AdvancedSupportResistanceDetector(
            atr_multiplier=0.5, volume_threshold=1.5
        )
        logger.info("✅ SR Detector initialized")

        # ✅ DEBUG: Проверка GEMINI_API_KEY
        print(
            f"🔍 DEBUG: GEMINI_API_KEY = {GEMINI_API_KEY[:20] if GEMINI_API_KEY else 'EMPTY'}"
        )
        logger.info(
            f"🔍 DEBUG: GEMINI_API_KEY = {GEMINI_API_KEY[:20] if GEMINI_API_KEY else 'EMPTY'}"
        )

        if GEMINI_API_KEY:
            try:
                self.gemini_interpreter = GeminiInterpreter(GEMINI_API_KEY)
                logger.info("✅ GeminiInterpreter создан успешно")
            except Exception as e:
                logger.error(
                    f"❌ Ошибка создания GeminiInterpreter: {e}", exc_info=True
                )
                self.gemini_interpreter = None
        else:
            logger.warning("⚠️ GEMINI_API_KEY пустой, GeminiInterpreter отключён")
            self.gemini_interpreter = None

        logger.info("✅ Unified Dashboard Handler initialized")

        if not self.enabled:
            logger.warning("⚠️ Telegram bot disabled")
        else:
            logger.info("✅ TelegramBotHandler инициализирован")

    async def initialize(self):
        """Инициализация Telegram Application"""
        if not self.enabled:
            return False

        try:
            request = HTTPXRequest(
                connection_pool_size=8,
                connect_timeout=30.0,
                read_timeout=30.0,
                write_timeout=30.0,
                pool_timeout=30.0,
            )

            self.application = (
                Application.builder().token(self.token).request(request).build()
            )

            # Регистрируем все команды
            self.application.add_handler(CommandHandler("start", self.cmd_start))
            self.application.add_handler(CommandHandler("help", self.cmd_help))
            self.application.add_handler(CommandHandler("status", self.cmd_status))
            self.application.add_handler(
                CommandHandler("signalstats", self.cmd_signal_stats)
            )

            self.application.add_handler(
                CommandHandler("signalhistory", self.cmd_signal_history)
            )
            self.application.add_handler(CommandHandler("analyze", self.cmd_analyze))
            self.application.add_handler(CommandHandler("stats", self.cmd_stats))
            self.application.add_handler(CommandHandler("signals", self.cmd_signals))
            self.application.add_handler(
                CommandHandler("autosignals", self.cmd_autosignals)
            )
            self.application.add_handler(CommandHandler("export", self.cmd_export))
            self.application.add_handler(
                CommandHandler("analyzebatching", self.cmd_analyze_batching)
            )
            self.application.add_handler(CommandHandler("pairs", self.cmd_pairs))
            self.application.add_handler(CommandHandler("add", self.cmd_add))
            self.application.add_handler(CommandHandler("remove", self.cmd_remove))
            self.application.add_handler(CommandHandler("enable", self.cmd_enable))
            self.application.add_handler(CommandHandler("disable", self.cmd_disable))
            self.application.add_handler(
                CommandHandler("available", self.cmd_available)
            )
            self.application.add_handler(CommandHandler("trades", self.cmd_trades))
            self.application.add_handler(CommandHandler("mtf", self.cmd_mtf))
            self.application.add_handler(CommandHandler("filters", self.cmd_filters))
            self.application.add_handler(CommandHandler("market", self.cmd_market))
            # self.application.add_handler(CommandHandler("overview", self.cmd_overview))
            self.application.add_handler(CommandHandler("advanced", self.cmd_advanced))
            # self.application.add_handler(CommandHandler("whale", self.cmd_whale))
            self.application.add_handler(
                CommandHandler("gio", self.gio_dashboard.cmd_gio)
            )
            # self.application.add_handler(CommandHandler("refresh", self.cmd_refresh))
            self.application.add_handler(CommandHandler("roi", self.cmd_roi))
            self.application.add_handler(
                CommandHandler(
                    "dashboard", self.unified_dashboard_handler.handle_dashboard
                )
            )
            logger.info("✅ Unified Dashboard handler registered with LIVE support")

            # Enhanced Overview (объединение /overview + /correlation)

            logger.info("🔧 BEFORE TRY: Готовимся регистрировать EnhancedOverview...")
            try:
                logger.info("🔍 DEBUG: Попытка импорта EnhancedOverview...")
                from analytics.enhanced_overview import EnhancedOverview

                logger.info("🔍 DEBUG: EnhancedOverview импортирован успешно")

                self.enhanced_overview = EnhancedOverview(self.bot_instance)
                logger.info("🔍 DEBUG: EnhancedOverview instance создан")

                self.application.add_handler(
                    CommandHandler("overview", self.cmd_enhanced_overview)
                )
                self.application.add_handler(
                    CommandHandler("correlation", self.cmd_overview)
                )
                logger.info(
                    "✅ Enhanced Overview handler registered (overview + correlation)"
                )
            except ImportError as e:
                logger.error(
                    f"❌ ImportError при загрузке EnhancedOverview: {e}", exc_info=True
                )
            except Exception as e:
                logger.error(
                    f"❌ Ошибка регистрации Enhanced Overview: {e}", exc_info=True
                )

                # Fallback: оставить старую correlation
                self.application.add_handler(
                    CommandHandler(
                        "correlation", self.correlation_handler.cmd_correlation
                    )
                )

            # Correlation commands
            self.application.add_handler(
                CommandHandler(
                    "correlation", self.bot_instance.correlation_handler.cmd_correlation
                )
            )
            self.application.add_handler(
                CommandHandler(
                    "corrpair",
                    self.bot_instance.correlation_handler.cmd_correlation_pair,
                )
            )
            logger.info("   ✅ Correlation handlers зарегистрированы")

            # Liquidity commands
            self.application.add_handler(
                CommandHandler(
                    "liquidity", self.bot_instance.liquidity_handler.cmd_liquidity
                )
            )
            logger.info("   ✅ Liquidity handler зарегистрирован")

            # Performance commands
            self.application.add_handler(
                CommandHandler(
                    "performance", self.bot_instance.performance_handler.cmd_performance
                )
            )
            self.application.add_handler(
                CommandHandler(
                    "bestsignals", self.bot_instance.performance_handler.cmd_bestsignals
                )
            )
            self.application.add_handler(
                CommandHandler(
                    "worstsignals",
                    self.bot_instance.performance_handler.cmd_worstsignals,
                )
            )
            logger.info("   ✅ Performance handlers зарегистрированы")

            logger.info("✅ Telegram bot команды зарегистрированы")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации: {e}")
            return False

    async def start(self):
        """Запуск Telegram бота"""
        if not self.enabled or not self.application:
            return

        try:
            await self.application.initialize()
            await self.application.start()

            # Отправляем приветственное сообщение
            await self.send_message(
                "*GIO Crypto Bot запущен!*\n\nИспользуйте /help для списка команд."
            )

            # Запускаем polling в отдельной задаче
            asyncio.create_task(self._run_polling())

            self.is_running = True
            logger.info("✅ Telegram bot запущен")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска: {e}")

    async def _run_polling(self):
        """Запуск polling для получения обновлений"""
        try:
            await self.application.updater.start_polling(
                allowed_updates=Update.ALL_TYPES, drop_pending_updates=True
            )
            logger.info("✅ Telegram bot polling запущен")

            while self.is_running:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"❌ Polling ошибка: {e}")

    async def stop(self):
        """Остановка Telegram бота"""
        if not self.is_running:
            return

        try:
            if self.application and self.application.updater:
                await self.application.updater.stop()

            if self.application:
                await self.application.stop()
                await self.application.shutdown()

            self.is_running = False
            logger.info("✅ Telegram bot остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка остановки: {e}")

    async def send_alert(self, message: str, priority: str = "medium"):
        """
        Отправка алерта в Telegram

        Args:
            message: Текст сообщения
            priority: Приоритет (low, medium, high)
        """
        try:
            if not self.enabled or not self.chat_id:
                logger.warning("⚠️ Telegram bot не настроен для алертов")
                return

            # Emoji по приоритету
            priority_emoji = {"low": "ℹ️", "medium": "⚠️", "high": "🚨"}

            emoji = priority_emoji.get(priority, "📢")
            formatted_message = f"{emoji} {message}"

            await self.application.bot.send_message(
                chat_id=self.chat_id,  # ← ИСПРАВЛЕНО!
                text=formatted_message,
                parse_mode=None,  # Без HTML, чтобы избежать проблем с символами
            )

            logger.info(f"✅ Алерт отправлен в Telegram (приоритет: {priority})")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки алерта: {e}")

    async def send_message(self, text: str, parse_mode: str = ParseMode.MARKDOWN):
        """Отправка сообщения в Telegram"""
        if not self.enabled or not self.application:
            return

        try:
            await self.application.bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode=parse_mode,
                disable_web_page_preview=True,
            )
        except Exception as e:
            logger.error(f"❌ Ошибка отправки: {e}")

    # ==================== ОСНОВНЫЕ КОМАНДЫ ====================

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /start"""
        await update.message.reply_text(
            "🤖 *Добро пожаловать в GIO Crypto Bot!*\n\n"
            "Профессиональный бот для анализа крипто рынка.\n\n"
            "Используйте /help для списка команд.",
            parse_mode=ParseMode.MARKDOWN,
        )

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /help - показывает список команд"""
        try:
            userid = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            logger.info(f"cmd_help: userid={userid}, username={username}")

            text = """<b>📋 GIO MARKET INTELLIGENCE — КОМАНДЫ</b>

    <b>🎯 Главный Дашборд:</b>
    • /dashboard — Unified GIO Dashboard (все метрики)
    • /dashboard live — С автообновлением (60 мин)

    <b>📊 Детальный Анализ:</b>
    • /market SYMBOL — Полный анализ актива (Market Intelligence)
    • /advanced SYMBOL — Продвинутые индикаторы (MACD, BB, ATR)

    <b>📈 Обзор Рынка:</b>
    • /overview — Multi-Symbol Overview (8 активов + корреляции)

    <b>💧 Ликвидность:</b>
    • /liquidity SYMBOL — Анализ глубины ликвидности

    <b>📊 Статистика:</b>
    • /performance [days] — Статистика сигналов
    • /bestsignals — Топ-10 лучших сигналов
    • /worstsignals — Топ-10 худших сигналов

    <b>🔧 Вспомогательные:</b>
    • /status — Статус системы
    • /pairs — Список отслеживаемых пар

    ━━━━━━━━━━━━━━━━━━━━━━

    <b>💡 Примеры использования:</b>
        /dashboard live
        /market BTCUSDT
        /overview

    ━━━━━━━━━━━━━━━━━━━━━━

    <b>📖 О GIO:</b>
    GIO Market Intelligence - аналитическая
    платформа с AI-интерпретацией данных.
    🎯 Фокус: Аналитика, Сигналы, Уведомления"""

            await update.message.reply_text(text, parse_mode=ParseMode.HTML)
            logger.info(f"✅ cmd_help: username={username}")

        except Exception as e:
            logger.error(f"❌ cmd_help: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def cmd_enhanced_overview(self, update: Update, context):
        """🎯 Enhanced Overview с Gemini 2.0"""
        try:
            user = update.effective_user
            logger.info(  # ✅ ИСПРАВЛЕНО: было self.logger
                f"📊 cmd_enhanced_overview вызвана (user_id={user.id}, username={user.username})"
            )

            loading_msg = await update.message.reply_text(
                "📊 Загрузка market overview...", parse_mode=ParseMode.MARKDOWN
            )

            logger.info("🔍 Вызываю enhanced_overview.generate_full_overview()...")
            overview_text = await self.enhanced_overview.generate_full_overview()
            logger.info(f"✅ Overview получен, длина: {len(overview_text)} символов")

            await loading_msg.edit_text(
                overview_text, parse_mode="HTML", disable_web_page_preview=True
            )

            logger.info(  # ✅ ИСПРАВЛЕНО
                f"✅ Enhanced Overview отправлен (username={user.username})"
            )

        except Exception as e:
            logger.error(
                f"❌ Error in cmd_enhanced_overview: {e}", exc_info=True
            )  # ✅ ИСПРАВЛЕНО
            await update.message.reply_text(f"❌ Ошибка: {str(e)[:500]}")

    async def cmd_signal_stats(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Показать статистику отслеживаемых сигналов"""
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            logger.info(
                f"📊 cmd_signal_stats вызвана (user_id={user_id}, username={username})"
            )

            args = context.args
            symbol = args[0].upper() if args else None

            # Получить активные сигналы из ROI Tracker
            if not hasattr(self.bot_instance, "roi_tracker"):
                await update.message.reply_text("❌ ROI Tracker не инициализирован")
                return

            active_signals = self.bot_instance.roi_tracker.active_signals

            if not active_signals:
                text = "📊 *СТАТИСТИКА СИГНАЛОВ*\n\n"
                text += "Нет отслеживаемых сигналов"
                await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
                return

            # Фильтровать по символу если указан
            if symbol:
                filtered_signals = {
                    sid: metrics
                    for sid, metrics in active_signals.items()
                    if metrics.symbol == symbol
                }
            else:
                filtered_signals = active_signals

            if not filtered_signals:
                text = f"📊 *СТАТИСТИКА СИГНАЛОВ* - {symbol}\n\n"
                text += f"Нет отслеживаемых сигналов для {symbol}"
                await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
                return

            # Подсчитать статистику
            total = len(filtered_signals)
            in_profit = sum(1 for m in filtered_signals.values() if m.current_roi > 0)
            in_loss = sum(1 for m in filtered_signals.values() if m.current_roi < 0)
            neutral = total - in_profit - in_loss

            avg_roi = (
                sum(m.current_roi for m in filtered_signals.values()) / total
                if total > 0
                else 0
            )
            profit_rate = (in_profit / total * 100) if total > 0 else 0
            loss_rate = (in_loss / total * 100) if total > 0 else 0

            # Форматировать ответ
            text = f"📊 *СТАТИСТИКА СИГНАЛОВ*"
            if symbol:
                text += f" - {symbol}"
            text += f"\n\n"
            text += f"📈 *Отслеживается:* {total} сигналов\n"
            text += f"🟢 *В прибыли:* {in_profit} ({profit_rate:.1f}%)\n"
            text += f"🔴 *В убытке:* {in_loss} ({loss_rate:.1f}%)\n"
            text += f"⚪ *Нейтральные:* {neutral}\n"
            text += f"\n"
            text += f"💰 *Средний ROI:* {avg_roi:+.2f}%\n"

            # Показать топ-5 сигналов
            text += f"\n📋 *Топ-5 сигналов:*\n"
            sorted_signals = sorted(
                filtered_signals.values(), key=lambda x: x.current_roi, reverse=True
            )[:5]

            for metrics in sorted_signals:
                roi_emoji = (
                    "🟢"
                    if metrics.current_roi > 0
                    else "🔴" if metrics.current_roi < 0 else "⚪"
                )
                direction = "🟢 LONG" if metrics.direction == "long" else "🔴 SHORT"
                text += f"\n{direction} *{metrics.symbol}*\n"
                text += f"├─ Entry: ${metrics.entry_price:.2f}\n"
                text += f"├─ ROI: {roi_emoji} {metrics.current_roi:+.2f}%\n"
                text += f"└─ TP: {sum([metrics.tp1_hit, metrics.tp2_hit, metrics.tp3_hit])}/3\n"

            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
            logger.info(f"✅ cmd_signal_stats успешно отправлена (username={username})")

        except Exception as e:
            logger.error(f"❌ Ошибка в cmd_signal_stats: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def cmd_signal_history(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Команда /signalhistory - История сигналов"""
        try:
            # Параметры
            limit = 10
            if context.args and context.args[0].isdigit():
                limit = min(int(context.args[0]), 50)  # Максимум 50

            db_path = os.path.join(DATA_DIR, "gio_crypto_bot.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Получаем последние сигналы
            cursor.execute(
                """
                SELECT symbol, direction, entry_price, timestamp, status, roi
                FROM signals
                ORDER BY timestamp DESC
                LIMIT ?
            """,
                (limit,),
            )

            signals = cursor.fetchall()
            conn.close()

            if not signals:
                await update.message.reply_text("📭 История сигналов пуста.")
                return

            # Формируем сообщение
            message = f"📜 *ИСТОРИЯ СИГНАЛОВ* (последние {len(signals)})\n\n"

            for i, (symbol, direction, price, timestamp, status, roi) in enumerate(
                signals, 1
            ):
                emoji = "🟢" if direction == "LONG" else "🔴"
                roi_str = (
                    f"+{roi:.2f}%"
                    if roi and roi > 0
                    else f"{roi:.2f}%" if roi else "N/A"
                )
                status_emoji = "✅" if status == "closed" else "⏳"

                message += f"{i}. {emoji} *{symbol}* {direction}\n"
                message += f"   💰 Entry: ${price:.2f}\n"
                message += f"   📊 ROI: {roi_str} {status_emoji}\n"
                message += f"   🕐 {timestamp}\n\n"

            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"Error in cmd_signal_history: {e}")
            await update.message.reply_text(f"❌ Ошибка получения истории: {str(e)}")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /status - Статус системы С ПОЛНОЙ СТАТИСТИКОЙ"""
        try:
            # ========== MEMORY ==========
            memory = self.bot_instance.memory_manager.get_statistics()

            # ========== SIGNALS FROM DB ==========
            db_path = os.path.join(DATA_DIR, "gio_crypto_bot.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM signals")
            total_signals = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM signals WHERE timestamp > datetime('now', '-24 hours')"
            )
            signals_24h = cursor.fetchone()[0]

            conn.close()

            # ========== CACHE STATS ==========
            cache_stats = {"hit_rate": 0, "total_items": 0}
            try:
                if hasattr(self.bot_instance, "bybit_connector"):
                    connector = self.bot_instance.bybit_connector
                    if hasattr(connector, "get_cache_statistics"):
                        cache_stats = connector.get_cache_statistics()
            except Exception as e:
                logger.warning(f"⚠️ Cache stats недоступны: {e}")

            # ========== RATE LIMITER STATS ==========
            rate_limiter_stats = {}
            try:
                if hasattr(self.bot_instance, "bybit_connector"):
                    connector = self.bot_instance.bybit_connector
                    if hasattr(connector, "get_rate_limiter_stats"):
                        rate_limiter_stats = connector.get_rate_limiter_stats()
            except Exception as e:
                logger.warning(f"⚠️ Rate limiter stats недоступны: {e}")

            # ========== UPTIME ==========
            uptime = "Unknown"
            try:
                if hasattr(self.bot_instance, "start_time"):
                    uptime_seconds = time.time() - self.bot_instance.start_time
                    hours = int(uptime_seconds // 3600)
                    minutes = int((uptime_seconds % 3600) // 60)
                    uptime = f"{hours}h {minutes}m"
            except:
                pass

            # ========== ФОРМИРУЕМ ОТВЕТ ==========
            text = (
                f"📊 *СТАТУС СИСТЕМЫ GIO CRYPTO BOT*\n\n"
                f"⏰ *Время:* {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"⏱️ *Uptime:* {uptime}\n"
                f"💾 *Память:* {memory.get('current_usage_mb', 0):.1f} MB "
                f"({memory.get('current_usage_percent', 0):.1f}%)\n\n"
                f"📈 *Всего сигналов:* {total_signals}\n"
                f"📊 *Сигналов (24ч):* {signals_24h}\n\n"
            )

            # Cache Statistics
            if cache_stats:
                hit_rate = cache_stats.get("hit_rate", 0)
                total_items = cache_stats.get("total_items", 0)
                total_size = cache_stats.get("total_size_mb", 0)

                text += (
                    f"💾 *CACHE:*\n"
                    f"├─ Hit Rate: {hit_rate:.1f}%\n"
                    f"├─ Items: {total_items}\n"
                    f"└─ Size: {total_size:.2f} MB\n\n"
                )

            # ✅ НОВЫЙ КОД (ПРАВИЛЬНЫЙ):
            if rate_limiter_stats:
                total_calls = rate_limiter_stats.get("total_requests", 0)
                text += f"⚡ *API CALLS:*\n" f"├─ Total: {total_calls}\n"

                # Итерируем по endpoints (исключая total_requests)
                count = 0
                for endpoint, count_val in rate_limiter_stats.items():
                    if endpoint != "total_requests" and count < 3:  # Top 3
                        endpoint_safe = endpoint.replace(
                            "_", "\\_"
                        )  # Escape underscores
                        text += f"├─ {endpoint_safe}: {count_val}\n"
                        count += 1
                text += "\n"

            text += (
                f"🔄 *Бот:* ✅ Работает\n"
                f"📱 *Telegram:* ✅ Подключен\n"
                f"🌐 *WebSocket:* ✅ Активен"
            )

            await update.message.reply_text(text, parse_mode=None)

        except Exception as e:
            logger.error(f"❌ Ошибка cmd_status: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def cmd_analyze(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /analyze [SYMBOL] - Анализ актива (Bybit + Binance)"""
        try:
            # Получаем символ из аргументов
            if context.args:
                symbol = context.args[0].upper()
            else:
                symbol = "BTCUSDT"

            await update.message.reply_text(f"🔍 Анализирую {symbol}... Подождите...")

            # ========== ПОЛУЧАЕМ ДАННЫЕ С BYBIT ==========
            bybit_price = 0
            bybit_volume = 0
            bybit_change = 0
            bybit_high = 0
            bybit_low = 0

            try:
                ticker = await self.bot_instance.bybit_connector.get_ticker(symbol)

                if ticker:
                    bybit_price = (
                        float(ticker.get("lastPrice", 0))
                        or float(ticker.get("last_price", 0))
                        or float(ticker.get("last", 0))
                        or float(ticker.get("price", 0))
                        or 0
                    )

                    bybit_volume = (
                        float(ticker.get("volume24h", 0))
                        or float(ticker.get("volume_24h", 0))
                        or float(ticker.get("volume", 0))
                    )

                    change_24h_str = ticker.get("price24hPcnt") or ticker.get(
                        "price_24h_pcnt", "0"
                    )
                    bybit_change = float(change_24h_str) * 100 if change_24h_str else 0

                    bybit_high = (
                        float(ticker.get("highPrice24h", 0))
                        or float(ticker.get("high_24h", 0))
                        or float(ticker.get("high", 0))
                    )

                    bybit_low = (
                        float(ticker.get("lowPrice24h", 0))
                        or float(ticker.get("low_24h", 0))
                        or float(ticker.get("low", 0))
                    )

            except Exception as e:
                logger.error(f"❌ Bybit error: {e}")
                pass

            # ========== ПОЛУЧАЕМ ДАННЫЕ С BINANCE ==========
            binance_price = 0
            binance_volume = 0
            binance_change = 0
            binance_high = 0
            binance_low = 0

            try:
                import aiohttp

                async with aiohttp.ClientSession() as session:
                    url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
                    async with session.get(url) as resp:
                        if resp.status == 200:
                            binance_data = await resp.json()
                            binance_price = float(binance_data.get("lastPrice", 0))
                            binance_change = float(
                                binance_data.get("priceChangePercent", 0)
                            )
                            binance_high = float(binance_data.get("highPrice", 0))
                            binance_low = float(binance_data.get("lowPrice", 0))
                            binance_volume = float(binance_data.get("volume", 0))
            except Exception as e:
                pass

            # ========== ОБЪЕДИНЯЕМ ДАННЫЕ ==========
            price = bybit_price if bybit_price > 0 else binance_price
            change_24h = binance_change if binance_change != 0 else bybit_change
            high_24h = binance_high if binance_high > 0 else bybit_high
            low_24h = binance_low if binance_low > 0 else bybit_low
            volume_24h = binance_volume if binance_volume > 0 else bybit_volume

            if price == 0:
                await update.message.reply_text(
                    f"❌ Не удалось получить данные для {symbol}"
                )
                return

            # ========== АНАЛИЗ ТРЕНДА ==========
            if change_24h > 5:
                trend = "📈 СИЛЬНЫЙ РОСТ"
                recommendation = "🚀 Восходящий тренд - можно рассмотреть LONG"
            elif change_24h > 2:
                trend = "📈 РОСТ"
                recommendation = "⬆️ Умеренный рост - осторожный LONG"
            elif change_24h > -2:
                trend = "➡️ ФЛЭТ"
                recommendation = "⏸️ Боковое движение - лучше подождать"
            elif change_24h > -5:
                trend = "📉 ПАДЕНИЕ"
                recommendation = "⬇️ Умеренное падение - осторожный SHORT"
            else:
                trend = "📉 СИЛЬНОЕ ПАДЕНИЕ"
                recommendation = "📉 Нисходящий тренд - можно рассмотреть SHORT"

            # ========== ФОРМИРУЕМ ОТВЕТ ==========
            text = f"📊 *АНАЛИЗ {symbol}*\n"
            text += f"_Данные: Bybit + Binance_\n\n"
            text += f"💰 *Цена:* ${price:,.2f}\n"

            if bybit_price > 0 and binance_price > 0:
                spread_percent = ((binance_price - bybit_price) / bybit_price) * 100
                text += f"   _Bybit: ${bybit_price:,.2f}_\n"
                text += f"   _Binance: ${binance_price:,.2f}_\n"
                text += f"   _Спред: {spread_percent:+.3f}%_\n\n"
            elif bybit_price > 0:
                text += f"   _Источник: Bybit_\n\n"
            elif binance_price > 0:
                text += f"   _Источник: Binance_\n\n"
            else:
                text += "\n"

            text += f"📊 *Изм. 24ч:* {change_24h:+.2f}%\n"

            if high_24h > 0 and low_24h > 0:
                text += f"📈 *Макс 24ч:* ${high_24h:,.2f}\n"
                text += f"📉 *Мин 24ч:* ${low_24h:,.2f}\n"

            if volume_24h > 0:
                text += f"📊 *Объём 24ч:* {volume_24h:,.0f}\n"

            text += f"\n🎯 *Тренд:* {trend}\n"
            text += f"💡 *Рекомендация:* {recommendation}"

            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка анализа: {str(e)}")

    # МЕТОД С БАТЧИНГОМ
    async def cmd_analyze_batching(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        /analyze_batching [SYMBOL|ALL] - Анализ с батчингом свечей
        """
        try:
            start_time = time.time()

            # Определение символов
            if not context.args:
                symbols = ["BTCUSDT"]
                mode = "single"
            elif context.args[0].upper() == "ALL":
                try:
                    from config.settings import TRACKED_SYMBOLS

                    symbols = TRACKED_SYMBOLS
                    mode = "all"

                    if not symbols:
                        await update.message.reply_text(
                            "❌ Нет активных пар для анализа!",
                            parse_mode=ParseMode.MARKDOWN,
                        )
                        return

                except Exception as e:
                    logger.error(f"❌ Ошибка получения списка пар: {e}")
                    await update.message.reply_text(
                        f"❌ Ошибка: {e}", parse_mode=ParseMode.MARKDOWN
                    )
                    return
            else:
                symbols = [context.args[0].upper()]
                mode = "single"

            # Начальное сообщение
            if mode == "all":
                await update.message.reply_text(
                    f"📊 *МАССОВЫЙ АНАЛИЗ С БАТЧИНГОМ*\n\n"
                    f"🎯 Пары: *{len(symbols)}*\n"
                    f"📋 {', '.join(symbols)}\n\n"
                    f"⚡ Запуск параллельного анализа...",
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await update.message.reply_text(
                    f"📊 Анализ *{symbols[0]}*...\n" f"⚡ Получение данных...",
                    parse_mode=ParseMode.MARKDOWN,
                )

            # Анализ всех символов
            results = []
            for symbol in symbols:
                try:
                    result = await self.bot_instance.analyze_symbol_with_batching(
                        symbol
                    )
                    if result and result.get("status") == "success":
                        results.append(
                            {
                                "symbol": symbol,
                                "result": result,
                                "time": result.get("analysis_time", 0),
                                "success": True,
                            }
                        )
                    else:
                        results.append(
                            {
                                "symbol": symbol,
                                "error": (
                                    result.get("error", "Unknown error")
                                    if result
                                    else "No result"
                                ),
                                "success": False,
                            }
                        )
                except Exception as e:
                    logger.error(f"❌ Ошибка анализа {symbol}: {e}")
                    results.append(
                        {"symbol": symbol, "error": str(e), "success": False}
                    )

            # Формирование отчёта
            total_time = time.time() - start_time

            if mode == "all":
                # МАССОВЫЙ ОТЧЁТ
                successful = [r for r in results if r["success"]]
                failed = [r for r in results if not r["success"]]

                if not successful:
                    message = (
                        "❌ Анализ не выполнен ни для одной пары!\n\nОшибки:\n"
                        + "\n".join(
                            [
                                f"• {r['symbol']}: {r.get('error', 'Unknown error')}"
                                for r in failed
                            ]
                        )
                    )
                else:
                    result_lines = []
                    for r in successful:
                        signal_id = r["result"].get("signal_id")
                        score = r["result"].get("score", 0)

                        if signal_id:
                            result_lines.append(
                                f"• *{r['symbol']}:* {score:>5.1f}% 🎯 Сигнал #{signal_id}"
                            )
                        else:
                            result_lines.append(
                                f"• *{r['symbol']}:* {score:>5.1f}% ⚪ NEUTRAL"
                            )

                    avg_time = sum([r["time"] for r in successful]) / len(successful)
                    message = (
                        f"✅ *МАССОВЫЙ АНАЛИЗ ЗАВЕРШЁН*\n\n"
                        f"⏱️ Общее время: {total_time:.2f}s\n"
                        f"📊 Проанализировано: {len(successful)}/{len(results)} пар\n"
                        f"⚡ Среднее время: {avg_time:.2f}s\n\n"
                        f"📊 *РЕЗУЛЬТАТЫ:*\n" + "\n".join(result_lines) + "\n\n"
                        f"💡 Используйте `/analyze_batching SYMBOL` для деталей"
                    )

            else:
                # ОДИНОЧНЫЙ ОТЧЁТ
                result = results[0]
                if not result["success"]:
                    message = f"❌ Ошибка анализа {result['symbol']}: {result.get('error', 'Unknown error')}"
                else:
                    data = result["result"]
                    signal_id = data.get("signal_id")

                    if signal_id:
                        response = (
                            f"✅ *Анализ {result['symbol']} завершён*\n"
                            f"⏱️ Время: {result['time']:.2f}s\n\n"
                            f"🎯 *Сигнал #{signal_id} создан!*\n"
                            f"💰 Entry: ${data.get('entry_price', 0):,.2f}\n"
                            f"📊 Score: {data.get('score', 0):.1f}%\n"
                            f"📈 Direction: {data.get('direction', 'N/A')}\n\n"
                            f"💡 Используйте `/signals` для просмотра деталей"
                        )
                    else:
                        response = (
                            f"✅ *Анализ {result['symbol']} завершён*\n"
                            f"⏱️ Время: {result['time']:.2f}s\n\n"
                            f"ℹ️ Подходящих сигналов не найдено\n"
                            f"Рынок не соответствует критериям входа"
                        )

                    message = response

            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"❌ Ошибка cmd_analyze_batching: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Ошибка анализа: {e}", parse_mode=ParseMode.MARKDOWN
            )

    async def cmd_trades(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /trades [days] - Журнал сделок"""
        try:
            days = int(context.args[0]) if context.args else 7

            db_path = os.path.join(DATA_DIR, "gio_crypto_bot.db")
            conn = sqlite3.connect(db_path)

            query = f"""
                SELECT
                    id, symbol, direction, entry_price, exit_price,
                    profit_percent, timestamp
                FROM signals
                WHERE timestamp > datetime('now', '-{days} days')
                    AND exit_price IS NOT NULL
                ORDER BY timestamp DESC
                LIMIT 20
            """

            df = pd.read_sql_query(query, conn)
            conn.close()

            if df.empty:
                await update.message.reply_text(
                    f"📊 Нет закрытых сделок за последние {days} дней."
                )
                return

            text = f"📊 *ЖУРНАЛ СДЕЛОК ({days} дней)*\n\n"

            for _, row in df.iterrows():
                emoji = "🟢" if row["profit_percent"] > 0 else "🔴"
                text += (
                    f"{emoji} *#{row['id']} {row['symbol']}* {row['direction']}\n"
                    f"💰 Entry: ${row['entry_price']:,.2f} → Exit: ${row['exit_price']:,.2f}\n"
                    f"📈 P&L: {row['profit_percent']:+.2f}%\n"
                    f"📅 {row['timestamp']}\n\n"
                )

            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /stats [days] - Статистика по закрытым сделкам"""
        try:
            days = int(context.args[0]) if context.args else 30

            db_path = os.path.join(DATA_DIR, "gio_crypto_bot.db")
            conn = sqlite3.connect(db_path)

            query = f"""
                SELECT
                    COUNT(*) as total_trades,
                    SUM(CASE WHEN profit_percent > 0 THEN 1 ELSE 0 END) as winning_trades,
                    SUM(CASE WHEN profit_percent < 0 THEN 1 ELSE 0 END) as losing_trades,
                    AVG(profit_percent) as avg_profit,
                    MAX(profit_percent) as max_profit,
                    MIN(profit_percent) as max_loss,
                    SUM(profit_percent) as total_profit
                FROM signals
                WHERE timestamp > datetime('now', '-{days} days')
                    AND exit_price IS NOT NULL
            """

            cursor = conn.cursor()
            cursor.execute(query)
            stats = cursor.fetchone()
            conn.close()

            if not stats or stats[0] == 0:
                await update.message.reply_text(
                    f"📊 Нет закрытых сделок за последние {days} дней."
                )
                return

            (
                total_trades,
                winning_trades,
                losing_trades,
                avg_profit,
                max_profit,
                max_loss,
                total_profit,
            ) = stats
            win_rate = (winning_trades / total_trades * 100) if total_trades > 0 else 0

            text = (
                f"📊 *СТАТИСТИКА ({days} дней)*\n\n"
                f"📈 *Всего сделок:* {total_trades}\n"
                f"🟢 *Прибыльных:* {winning_trades} ({win_rate:.1f}%)\n"
                f"🔴 *Убыточных:* {losing_trades}\n\n"
                f"💰 *Средняя прибыль:* {avg_profit:.2f}%\n"
                f"🚀 *Лучшая сделка:* +{max_profit:.2f}%\n"
                f"📉 *Худшая сделка:* {max_loss:.2f}%\n\n"
                f"💎 *ИТОГО:* {total_profit:+.2f}%"
            )

            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def cmd_signals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /signals [N] - Последние N сигналов"""
        try:
            limit = int(context.args[0]) if context.args else 5

            db_path = os.path.join(DATA_DIR, "gio_crypto_bot.db")
            conn = sqlite3.connect(db_path)

            query = f"""
                SELECT
                    id, symbol, direction, entry_price,
                    tp1, tp2, tp3, stop_loss, timestamp
                FROM signals
                ORDER BY timestamp DESC
                LIMIT {limit}
            """

            df = pd.read_sql_query(query, conn)
            conn.close()

            if df.empty:
                await update.message.reply_text(
                    "📊 Пока нет сигналов.\n\nБот анализирует рынок..."
                )
                return

            text = f"🎯 *ПОСЛЕДНИЕ СИГНАЛЫ ({limit})*\n\n"

            for _, row in df.iterrows():
                emoji = "🟢" if row["direction"] == "LONG" else "🔴"
                text += (
                    f"{emoji} *#{row['id']} {row['symbol']} {row['direction']}*\n"
                    f"💰 Entry: ${row['entry_price']:,.2f}\n"
                    f"🎯 TP1: ${row['tp1']:,.2f} | TP2: ${row['tp2']:,.2f} | TP3: ${row['tp3']:,.2f}\n"
                    f"🛑 SL: ${row['stop_loss']:,.2f}\n"
                    f"📅 {row['timestamp']}\n\n"
                )

            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def cmd_autosignals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /autosignals [on|off] - Автообновление сигналов"""
        try:
            if not context.args:
                status = "✅ Включено" if self.auto_signals else "❌ Выключено"
                text = (
                    f"📡 *АВТООБНОВЛЕНИЕ СИГНАЛОВ*\n\n"
                    f"Статус: {status}\n\n"
                    f"Используйте:\n"
                    f"`/autosignals on` - включить\n"
                    f"`/autosignals off` - выключить"
                )
                await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
                return

            action = context.args[0].lower()

            if action == "on":
                self.auto_signals = True
                await update.message.reply_text(
                    "✅ Автообновление сигналов *ВКЛЮЧЕНО*",
                    parse_mode=ParseMode.MARKDOWN,
                )
            elif action == "off":
                self.auto_signals = False
                await update.message.reply_text(
                    "❌ Автообновление сигналов *ВЫКЛЮЧЕНО*",
                    parse_mode=ParseMode.MARKDOWN,
                )
            else:
                await update.message.reply_text(
                    "❌ Используйте: `/autosignals on` или `/autosignals off`",
                    parse_mode=ParseMode.MARKDOWN,
                )

        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def cmd_export(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Команда /export - экспорт истории сигналов в CSV

        Использование:
            /export - экспортировать ВСЕ сигналы (30 дней по умолчанию)
            /export 7 - экспортировать за последние 7 дней
            /export 90 - экспортировать за последние 90 дней
            /export BTCUSDT - экспортировать только BTCUSDT (30 дней)
            /export BTCUSDT 60 - экспортировать BTCUSDT за 60 дней
        """
        try:
            logger.info(f"📤 Команда /export от {update.effective_user.username}")

            # Парсинг аргументов
            symbol = None
            days = 30  # По умолчанию 30 дней

            if context.args:
                if len(context.args) == 1:
                    # Может быть либо symbol, либо days
                    arg = context.args[0]
                    if arg.isdigit():
                        days = int(arg)
                    else:
                        symbol = arg.upper()
                elif len(context.args) >= 2:
                    # Первый аргумент - symbol, второй - days
                    symbol = context.args[0].upper()
                    if context.args[1].isdigit():
                        days = int(context.args[1])

            # Ограничиваем максимум 365 дней
            if days > 365:
                await update.message.reply_text(
                    "⚠️ Максимальный период экспорта: 365 дней.\n"
                    "Используйте: `/export 365` или меньше.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            # Отправляем сообщение о начале экспорта
            status_msg = await update.message.reply_text(
                f"📤 *Экспорт истории сигналов...*\n"
                f"• Символ: {symbol if symbol else 'ВСЕ'}\n"
                f"• Период: {days} дней\n"
                f"• Подождите...",
                parse_mode=ParseMode.MARKDOWN,
            )

            # Получаем данные из БД
            db_path = os.path.join(DATA_DIR, "gio_crypto_bot.db")
            conn = sqlite3.connect(db_path)

            # Формируем SQL запрос (ЭКСПОРТИРУЕМ ВСЕ КОЛОНКИ - SELECT *)
            if symbol:
                query = f"""
                    SELECT *
                    FROM signals
                    WHERE symbol = '{symbol}'
                        AND timestamp > datetime('now', '-{days} days')
                    ORDER BY timestamp DESC
                """
            else:
                query = f"""
                    SELECT *
                    FROM signals
                    WHERE timestamp > datetime('now', '-{days} days')
                    ORDER BY timestamp DESC
                """

            df = pd.read_sql_query(query, conn)
            conn.close()

            if df.empty:
                await status_msg.edit_text(
                    f"📊 *Нет данных для экспорта*\n\n"
                    f"• Символ: {symbol if symbol else 'ВСЕ'}\n"
                    f"• Период: {days} дней\n\n"
                    f"Попробуйте увеличить период или проверьте символ.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            # Сохраняем в CSV
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            csv_filename = f"signals_export_{symbol if symbol else 'all'}_{days}d_{timestamp_str}.csv"
            csv_path = os.path.join(DATA_DIR, "exports", csv_filename)

            # Создаём директорию exports если не существует
            os.makedirs(os.path.join(DATA_DIR, "exports"), exist_ok=True)

            # Сохраняем CSV
            df.to_csv(csv_path, index=False, encoding="utf-8")

            # Подсчитываем статистику (с проверкой наличия колонок!)
            total_signals = len(df)

            # Проверяем наличие колонки profit_percent
            if "profit_percent" in df.columns:
                profitable = len(df[df["profit_percent"] > 0])
                losing = len(df[df["profit_percent"] < 0])
            else:
                profitable = 0
                losing = 0

            # Проверяем наличие колонки status
            if "status" in df.columns:
                active = len(df[df["status"] == "ACTIVE"])
            else:
                active = 0

            # Отправляем файл
            with open(csv_path, "rb") as f:
                caption = (
                    f"✅ *Экспорт завершён!*\n\n"
                    f"📁 Файл: `{csv_filename}`\n"
                    f"📊 Всего сигналов: {total_signals}\n"
                    f"🟢 Прибыльных: {profitable}\n"
                    f"🔴 Убыточных: {losing}\n"
                    f"⚪ Активных: {active}\n"
                    f"📅 Период: {days} дней"
                )

                await update.message.reply_document(
                    document=f,
                    filename=csv_filename,
                    caption=caption,
                    parse_mode=ParseMode.MARKDOWN,
                )

            # Удаляем статус-сообщение
            await status_msg.delete()

            # Удаляем временный CSV файл через 5 секунд
            await asyncio.sleep(5)
            try:
                os.remove(csv_path)
            except:
                pass

            logger.info(
                f"✅ Экспорт выполнен: {total_signals} сигналов ({symbol if symbol else 'ALL'}, {days} дней)"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка cmd_export: {e}")
            await update.message.reply_text(
                f"❌ *Ошибка экспорта:*\n`{str(e)}`", parse_mode=ParseMode.MARKDOWN
            )

            logger.info(
                f"✅ Экспорт выполнен: {total_signals} сигналов ({symbol if symbol else 'ALL'}, {days} дней)"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка cmd_export: {e}")
            await update.message.reply_text(
                f"❌ *Ошибка экспорта:*\n`{str(e)}`", parse_mode=ParseMode.MARKDOWN
            )

    async def cmd_pairs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /pairs - показать все торговые пары"""
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            logger.info(f"📋 Команда /pairs от user_id={user_id}, username={username}")

            from config.settings import TRACKED_SYMBOLS
            import json

            config_path = os.path.join(
                os.path.dirname(__file__), "..", "config", "trading_pairs.json"
            )

            # Читаем конфигурацию
            if os.path.exists(config_path):
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)

                all_pairs = config.get("tracked_symbols", [])

                text = "📊 *ТОРГОВЫЕ ПАРЫ*\n\n"

                # Активные пары
                active_pairs = [p for p in all_pairs if p.get("enabled", True)]
                text += f"🟢 *Активные ({len(active_pairs)}):*\n"
                for pair in sorted(active_pairs, key=lambda x: x.get("priority", 999)):
                    text += f"  • {pair['symbol']} (приоритет: {pair['priority']})\n"

                # Отключенные пары
                disabled_pairs = [p for p in all_pairs if not p.get("enabled", True)]
                if disabled_pairs:
                    text += f"\n🔴 *Отключенные ({len(disabled_pairs)}):*\n"
                    for pair in disabled_pairs:
                        text += f"  • {pair['symbol']}\n"

                text += f"\n📁 Конфигурация: `trading_pairs.json`"
                text += (
                    f"\n💡 Используйте /add, /remove, /enable, /disable для управления"
                )

            else:
                text = f"⚠️ Файл конфигурации не найден\n\n"
                text += f"📋 Активные пары: {', '.join(TRACKED_SYMBOLS)}"

            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"❌ Ошибка в /pairs: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def cmd_add(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /add - добавить новую торговую пару"""
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"

            if not context.args:
                await update.message.reply_text(
                    "⚠️ *Использование:*\n"
                    "`/add SYMBOL [priority] [enabled]`\n\n"
                    "*Примеры:*\n"
                    "• `/add ADAUSDT` — добавить с приоритетом 99\n"
                    "• `/add ADAUSDT 10` — добавить с приоритетом 10\n"
                    "• `/add ADAUSDT 10 true` — добавить активной\n\n"
                    "💡 Используйте `/available` для списка популярных пар",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            symbol = context.args[0].upper()
            if not symbol.endswith("USDT"):
                symbol += "USDT"

            priority = int(context.args[1]) if len(context.args) > 1 else 99
            enabled = (
                context.args[2].lower() == "true" if len(context.args) > 2 else True
            )

            logger.info(f"➕ Команда /add {symbol} от {username}")

            import json

            config_path = os.path.join(
                os.path.dirname(__file__), "..", "config", "trading_pairs.json"
            )

            if not os.path.exists(config_path):
                await update.message.reply_text("❌ Файл конфигурации не найден")
                return

            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            # Проверяем существование
            for pair in config.get("tracked_symbols", []):
                if pair["symbol"] == symbol:
                    await update.message.reply_text(
                        f"⚠️ *{symbol} УЖЕ СУЩЕСТВУЕТ!*\n\n"
                        f"💡 Используйте `/enable {symbol}` для активации",
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    return

            # Добавляем новую пару
            new_pair = {
                "symbol": symbol,
                "enabled": enabled,
                "priority": priority,
                "min_volume_24h": 50000000,
                "max_leverage": 10,
                "notes": f"Добавлена {username} {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            }

            config["tracked_symbols"].append(new_pair)
            config["tracked_symbols"].sort(key=lambda x: x.get("priority", 999))
            config["last_updated"] = datetime.now().isoformat()

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            active_count = sum(
                1 for p in config["tracked_symbols"] if p.get("enabled", True)
            )

            await update.message.reply_text(
                f"✅ *{symbol} ДОБАВЛЕНА!*\n\n"
                f"📊 Параметры:\n"
                f"  • Статус: {'🟢 Активна' if enabled else '🔴 Отключена'}\n"
                f"  • Приоритет: {priority}\n\n"
                f"📋 Всего пар: {len(config['tracked_symbols'])} ({active_count} активных)\n\n"
                f"⚠️ Перезапустите бота для применения изменений",
                parse_mode=ParseMode.MARKDOWN,
            )

        except Exception as e:
            logger.error(f"❌ Ошибка /add: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def cmd_remove(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /remove - удалить торговую пару"""
        try:
            if not context.args:
                await update.message.reply_text(
                    "⚠️ Использование: `/remove SYMBOL`\n" "Пример: `/remove ADAUSDT`",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            symbol = context.args[0].upper()
            if not symbol.endswith("USDT"):
                symbol += "USDT"

            import json

            config_path = os.path.join(
                os.path.dirname(__file__), "..", "config", "trading_pairs.json"
            )

            if not os.path.exists(config_path):
                await update.message.reply_text("❌ Файл конфигурации не найден")
                return

            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            original_count = len(config["tracked_symbols"])
            config["tracked_symbols"] = [
                p for p in config["tracked_symbols"] if p["symbol"] != symbol
            ]

            if len(config["tracked_symbols"]) == original_count:
                await update.message.reply_text(f"❌ {symbol} не найдена")
                return

            config["last_updated"] = datetime.now().isoformat()

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            await update.message.reply_text(
                f"✅ *{symbol} УДАЛЕНА!*\n\n" f"⚠️ Перезапустите бота",
                parse_mode=ParseMode.MARKDOWN,
            )

        except Exception as e:
            logger.error(f"❌ Ошибка /remove: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def cmd_enable(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /enable - включить пару"""
        try:
            if not context.args:
                await update.message.reply_text(
                    "⚠️ Использование: `/enable SYMBOL`", parse_mode=ParseMode.MARKDOWN
                )
                return

            symbol = context.args[0].upper()
            if not symbol.endswith("USDT"):
                symbol += "USDT"

            import json

            config_path = os.path.join(
                os.path.dirname(__file__), "..", "config", "trading_pairs.json"
            )

            if not os.path.exists(config_path):
                await update.message.reply_text("❌ Файл не найден")
                return

            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            found = False
            for pair in config.get("tracked_symbols", []):
                if pair["symbol"] == symbol:
                    pair["enabled"] = True
                    found = True
                    break

            if not found:
                await update.message.reply_text(f"❌ {symbol} не найдена")
                return

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            await update.message.reply_text(
                f"✅ *{symbol} АКТИВИРОВАНА!*\n\n" f"⚠️ Перезапустите бота",
                parse_mode=ParseMode.MARKDOWN,
            )

        except Exception as e:
            logger.error(f"❌ Ошибка /enable: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def cmd_disable(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /disable - отключить пару"""
        try:
            if not context.args:
                await update.message.reply_text(
                    "⚠️ Использование: `/disable SYMBOL`", parse_mode=ParseMode.MARKDOWN
                )
                return

            symbol = context.args[0].upper()
            if not symbol.endswith("USDT"):
                symbol += "USDT"

            import json

            config_path = os.path.join(
                os.path.dirname(__file__), "..", "config", "trading_pairs.json"
            )

            if not os.path.exists(config_path):
                await update.message.reply_text("❌ Файл не найден")
                return

            with open(config_path, "r", encoding="utf-8") as f:
                config = json.load(f)

            found = False
            for pair in config.get("tracked_symbols", []):
                if pair["symbol"] == symbol:
                    pair["enabled"] = False
                    found = True
                    break

            if not found:
                await update.message.reply_text(f"❌ {symbol} не найдена")
                return

            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)

            await update.message.reply_text(
                f"✅ *{symbol} ДЕАКТИВИРОВАНА!*\n\n" f"⚠️ Перезапустите бота",
                parse_mode=ParseMode.MARKDOWN,
            )

        except Exception as e:
            logger.error(f"❌ Ошибка /disable: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def cmd_available(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /available - популярные пары"""
        try:
            text = "📊 *ПОПУЛЯРНЫЕ ПАРЫ BYBIT*\n\n"
            text += "*🏆 Top:*\n"
            text += "BTCUSDT, ETHUSDT, BNBUSDT, SOLUSDT\n"
            text += "XRPUSDT, DOGEUSDT, ADAUSDT, AVAXUSDT\n\n"
            text += "*💎 DeFi:*\n"
            text += "UNIUSDT, AAVEUSDT, MATICUSDT\n\n"
            text += "*⚡ Layer 2:*\n"
            text += "ARBUSDT, OPUSDT, SUIUSDT\n\n"
            text += "*💡 Добавить:*\n"
            text += "`/add SYMBOL`"

            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"❌ Ошибка /available: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

        # АВТОУВЕДОМЛЕНИЯ

    async def cmd_roi(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📊 /roi - Показывает активные сигналы с ROI"""
        try:
            # Фильтр по символу (если указан)
            symbol_filter = context.args[0].upper() if context.args else None

            await update.message.reply_text("📊 Загрузка активных позиций...")

            # Получаем активные сигналы из БД
            from config.settings import DATABASE_PATH

            conn = sqlite3.connect(str(DATABASE_PATH))
            query = """
                SELECT id, symbol, direction, entry_price, tp1, status
                FROM signals
                ORDER BY id DESC
                LIMIT 10
            """
            df = pd.read_sql_query(query, conn)
            conn.close()

            if df.empty:
                await update.message.reply_text("📊 Нет активных сигналов")
                return

            # Фильтруем по символу если указан
            if symbol_filter:
                df = df[df["symbol"] == symbol_filter]
                if df.empty:
                    await update.message.reply_text(
                        f"📊 Нет активных сигналов для {symbol_filter}"
                    )
                    return

            # Формируем сообщение
            message = "📊 *ACTIVE SIGNALS & ROI*\n\n"

            total_pnl = 0
            win_count = 0
            loss_count = 0

            # Показываем первые 10 сигналов
            count = 0
            for idx, row in df.head(10).iterrows():
                signal_id = row["id"]
                symbol = row["symbol"]
                direction = row["direction"]
                entry = float(row["entry_price"])
                tp1 = float(row["tp1"])

                # Получаем текущую цену
                try:
                    if hasattr(self.bot_instance, "bybit_connector"):
                        ticker = await self.bot_instance.bybit_connector.get_ticker(
                            symbol
                        )
                        current = (
                            float(ticker.get("last_price", entry)) if ticker else entry
                        )
                    else:
                        current = entry
                except:
                    current = entry

                # Рассчитываем P&L
                if direction == "LONG":
                    pnl = ((current - entry) / entry) * 100 if entry > 0 else 0
                    to_tp1 = ((tp1 - current) / current) * 100 if current > 0 else 0
                else:
                    pnl = ((entry - current) / entry) * 100 if entry > 0 else 0
                    to_tp1 = ((current - tp1) / current) * 100 if current > 0 else 0

                total_pnl += pnl

                if pnl > 0:
                    win_count += 1
                    emoji = "📈"
                elif pnl < 0:
                    loss_count += 1
                    emoji = "📉"
                else:
                    emoji = "⚪"

                message += f"{emoji} *{symbol}\\_{signal_id}* {direction}\n"
                message += f"Entry: ${entry:.2f} | Current: ${current:.2f}\n"
                message += f"P&L: *{pnl:+.2f}%* {emoji}"
                if to_tp1 > 0:
                    message += f" | To TP1: {to_tp1:+.2f}%"
                message += "\n\n"

                count += 1

            # Если сигналов больше 10
            total_count = len(df)
            if total_count > 10:
                message += f"... и ещё {total_count - 10} сигналов\n\n"

            # Итоговая статистика
            avg_pnl = total_pnl / count if count > 0 else 0

            message += f"📊 *Total Active:* {total_count} signals\n"
            message += f"💰 *Average P&L:* {avg_pnl:+.2f}%\n"
            message += f"✅ *Winning:* {win_count} | ❌ *Losing:* {loss_count}"

            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"❌ Ошибка cmd_roi: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка получения ROI: {str(e)}")

    async def cmd_mtf(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """📊 /mtf SYMBOL - Multi-Timeframe анализ"""
        try:
            if not context.args:
                await update.message.reply_text("❌ Укажите символ: /mtf BTCUSDT")
                return

            symbol = context.args[0].upper()
            await update.message.reply_text(f"📊 Анализ трендов для {symbol}...")

            # Проверяем где находится MTF Filter
            bot = self.bot_instance
            signal_gen = getattr(bot, "signal_generator", None)

            multi_tf_filter = None
            if (
                hasattr(bot, "multitffilter") and bot.multitffilter
            ):  # ← ИСПРАВЛЕНО! СНАЧАЛА БЕЗ ПОДЧЕРКИВАНИЯ
                multi_tf_filter = bot.multitffilter
            elif (
                hasattr(bot, "multi_tf_filter") and bot.multi_tf_filter
            ):  # ← ПОТОМ С ПОДЧЕРКИВАНИЕМ
                multi_tf_filter = bot.multi_tf_filter
            elif signal_gen and hasattr(signal_gen, "multitffilter"):
                multi_tf_filter = signal_gen.multitffilter
            elif signal_gen and hasattr(signal_gen, "multi_tf_filter"):
                multi_tf_filter = signal_gen.multi_tf_filter

            if not multi_tf_filter:
                await update.message.reply_text("❌ Multi-TF Filter не инициализирован")
                return

            # Получаем MTF данные
            summary = await multi_tf_filter.get_trend_summary(symbol)

            if "error" in summary:
                await update.message.reply_text(f"❌ Ошибка: {summary['error']}")
                return

            # Формируем сообщение
            trends = summary["trends"]
            dominant = summary["dominant_trend"]
            agreement = summary["agreement_score"] * 100
            strength = summary["overall_strength"]

            message = "📊 *MULTI-TIMEFRAME ANALYSIS*\n\n"
            message += f"💎 *{symbol}*\n\n"

            # Тренды по таймфреймам
            for tf, trend in trends.items():
                emoji = "📈" if trend == "UP" else ("📉" if trend == "DOWN" else "⚪")
                message += f"{emoji} *{tf.upper()}:* {trend}\n"

            message += (
                f"\n🎯 *Dominant:* {dominant} {'📈' if dominant == 'UP' else '📉'}\n"
            )
            message += f"💪 *Agreement:* {agreement:.0f}%\n"
            message += f"⚡ *Strength:* {strength:.2f}\n\n"

            # Multi-TF Filter verdict
            if agreement >= 67:  # 2 из 3
                message += "✅ *MTF Filter:* PASS (ready for signals)"
            else:
                message += "⚠️ *MTF Filter:* BLOCKED (low agreement)"

            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"❌ Ошибка cmd_mtf: {e}", exc_info=True)
            await update.message.reply_text(f"❌ MTF Ошибка: {str(e)}")

    async def cmd_filters(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """🔍 /filters - Показывает статус фильтров"""
        try:
            message = "🔍 *FILTERS STATUS*\n\n"

            # Проверяем где находятся фильтры
            bot = self.bot_instance
            signal_gen = getattr(bot, "signal_generator", None)

            # Confirm Filter
            confirm_filter = None
            if hasattr(bot, "confirm_filter") and bot.confirm_filter:
                confirm_filter = bot.confirm_filter
            elif (
                hasattr(bot, "confirmfilter") and bot.confirmfilter
            ):  # ← БЕЗ ПОДЧЕРКИВАНИЯ
                confirm_filter = bot.confirmfilter
            elif signal_gen and hasattr(signal_gen, "confirm_filter"):
                confirm_filter = signal_gen.confirm_filter

            if confirm_filter:
                cf = confirm_filter
                message += "✅ *Confirm Filter:* ACTIVE\n"
                message += f"   • CVD threshold: ≥{getattr(cf, 'min_cvd_pct', 0.5)}%\n"
                message += (
                    f"   • Volume multiplier: {getattr(cf, 'min_volume_ratio', 1.5)}x\n"
                )
                message += f"   • Candle check: {'ON' if getattr(cf, 'check_confirmation_candle', True) else 'OFF'}\n\n"
            else:
                message += "⚪ *Confirm Filter:* DISABLED\n\n"

            # Multi-TF Filter
            multi_tf_filter = None
            if (
                hasattr(bot, "multitffilter") and bot.multitffilter
            ):  # ← ИСПРАВЛЕНО! СНАЧАЛА БЕЗ ПОДЧЕРКИВАНИЯ
                multi_tf_filter = bot.multitffilter
            elif (
                hasattr(bot, "multi_tf_filter") and bot.multi_tf_filter
            ):  # ← ПОТОМ С ПОДЧЕРКИВАНИЕМ
                multi_tf_filter = bot.multi_tf_filter
            elif signal_gen and hasattr(signal_gen, "multitffilter"):
                multi_tf_filter = signal_gen.multitffilter
            elif signal_gen and hasattr(signal_gen, "multi_tf_filter"):
                multi_tf_filter = signal_gen.multi_tf_filter

            if multi_tf_filter:
                mtf = multi_tf_filter
                message += "✅ *Multi-TF Filter:* ACTIVE\n"
                message += f"   • Min aligned: {mtf.min_aligned_count}/{len(mtf.default_timeframes)} timeframes\n"
                message += (
                    f"   • Require all: {'YES' if mtf.require_all_aligned else 'NO'}\n"
                )
                message += f"   • Timeframes: {', '.join([tf.upper() for tf in mtf.default_timeframes])}\n"
            else:
                message += "⚪ *Multi-TF Filter:* DISABLED\n"

            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"❌ Ошибка cmd_filters: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def cmd_advanced(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /advanced SYMBOL - Расширенная аналитика

        Включает:
        - Продвинутые индикаторы (MACD, Stoch RSI, BB, ATR, ADX)
        - Паттерны (свечные, S/R уровни, структура)
        - Рыночная структура (Wyckoff, режим, ликвидность)
        - 🤖 AI ИНТЕРПРЕТАЦИЯ
        """
        try:
            # Получаем символ
            if not context.args:
                await update.message.reply_text(
                    "❌ Использование: /advanced SYMBOL\n" "Пример: /advanced BTCUSDT",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            symbol = context.args[0].upper()
            if not symbol.endswith("USDT"):
                symbol += "USDT"

            # Сообщение о загрузке
            loading_msg = await update.message.reply_text(
                f"📊 Анализирую {symbol}...", parse_mode=ParseMode.MARKDOWN
            )

            # Получаем данные
            from indicators.advanced import AdvancedIndicators

            adv = AdvancedIndicators(self.bot_instance.bybit_connector)

            # Получаем свечи
            klines = await self.bot_instance.bybit_connector.get_klines(
                symbol=symbol, interval="240", limit=200  # 4H
            )

            if not klines or len(klines) < 50:
                await loading_msg.edit_text(f"❌ Недостаточно данных для {symbol}")
                return

            closes = [float(k["close"]) for k in klines]
            highs = [float(k["high"]) for k in klines]
            lows = [float(k["low"]) for k in klines]
            volumes = [float(k["volume"]) for k in klines]

            # Рассчитываем индикаторы
            macd = adv.calculate_macd(closes)
            stoch_rsi = adv.calculate_stoch_rsi(closes)
            bb = adv.calculate_bollinger_bands(closes)
            atr = adv.calculate_atr(highs, lows, closes)
            adx = adv.calculate_adx(highs, lows, closes)

            # Паттерны
            patterns = adv.detect_candlestick_patterns(klines[-10:])

            # ========================================
            # S/R УРОВНИ (ВРЕМЕННО ОТКЛЮЧЕНО)
            # ========================================
            sr_levels = {"support": [], "resistance": []}

            # Структура тренда
            trend_structure = adv.analyze_trend_structure(highs, lows, closes)

            # Wyckoff фаза
            wyckoff = adv.analyze_wyckoff_phase(closes, volumes)

            # Режим рынка
            regime = adv.detect_market_regime(closes, volumes)

            # Market Bias
            bias = adv.calculate_market_bias(closes, volumes)

            # ==========================================
            # 🤖 AI ИНТЕРПРЕТАЦИЯ ИНДИКАТОРОВ
            # ==========================================

            ai_interpretation = ""
            try:
                ai_text = AdvancedIndicators.get_ai_interpretation(
                    macd=macd, stoch_rsi=stoch_rsi, bollinger=bb, atr=atr, adx=adx
                )

                ai_interpretation = f"""
━━━━━━━━━━━━━━━━━━━━━━
 <b>AI INTERPRETATION</b>
━━━━━━━━━━━━━━━━━━━━━━

{ai_text}

"""
                logger.info(f"✅ AI интерпретация для {symbol} получена")

            except Exception as ai_error:
                logger.error(f"❌ AI interpretation error: {ai_error}", exc_info=True)
                ai_interpretation = ""

            # ==========================================
            # 📝 ФОРМИРУЕМ ОТВЕТ
            # ==========================================

            current_price = closes[-1]

            response = f"""🎯 <b>РАСШИРЕННАЯ АНАЛИТИКА: {symbol}</b>
💰 Цена: <b>${current_price:.2f}</b>
⏰ Таймфрейм: <b>4H</b>

━━━━━━━━━━━━━━━━━━━━━━
📊 <b>ПРОДВИНУТЫЕ ИНДИКАТОРЫ</b>
━━━━━━━━━━━━━━━━━━━━━━

<b>MACD:</b>
├─ MACD: {macd['macd']}
├─ Signal: {macd['signal']}
├─ Histogram: {macd['histogram']}
└─ Тренд: {macd.get('trend', 'N/A')}

<b>Stochastic RSI:</b>
├─ %K: {stoch_rsi['k']}
├─ %D: {stoch_rsi['d']}
└─ Сигнал: {stoch_rsi['signal']}

<b>Bollinger Bands:</b>
├─ Upper: ${bb['upper']:.2f}
├─ Middle: ${bb['middle']:.2f}
├─ Lower: ${bb['lower']:.2f}
├─ Width: {bb['width']:.2f}%
└─ Squeeze: {'🔴 Да' if bb.get('squeeze') else '🟢 Нет'}

<b>ATR (Волатильность):</b>
├─ ATR: {atr['atr']}
├─ ATR%: {atr['atr_percentage']}%
└─ Волатильность: {atr['volatility']}

<b>ADX (Сила тренда):</b>
├─ ADX: {adx['adx']}
└─ Сила: {adx['trend_strength']}

━━━━━━━━━━━━━━━━━━━━━━
🎯 <b>ПАТТЕРНЫ</b>
━━━━━━━━━━━━━━━━━━━━━━

<b>Свечные паттерны:</b>
"""

            # Паттерны
            if patterns["patterns"]:
                for p in patterns["patterns"][:3]:  # Топ-3
                    response += f"├─ {p['name']} ({p['strength']})\n"
                response += f"└─ Сигнал: {patterns['signal']}\n"
            else:
                response += "└─ Паттернов не обнаружено\n"

            response += "\n<b>Support/Resistance:</b>\n"

            # Support
            if sr_levels["support"]:
                for s in sr_levels["support"][:2]:  # Топ-2
                    response += (
                        f"├─ Support: ${s['level']:.2f} ({s['touches']} касаний)\n"
                    )

            # Resistance
            if sr_levels["resistance"]:
                for r in sr_levels["resistance"][:2]:  # Топ-2
                    response += (
                        f"├─ Resistance: ${r['level']:.2f} ({r['touches']} касаний)\n"
                    )

            response += f"\n<b>Структура тренда:</b>\n"
            response += f"├─ Тренд: {trend_structure['trend']}\n"
            response += f"└─ Структура: {trend_structure['structure']}\n"

            response += f"""
━━━━━━━━━━━━━━━━━━━━━━
🏛️ <b>РЫНОЧНАЯ СТРУКТУРА</b>
━━━━━━━━━━━━━━━━━━━━━━

<b>Фаза Wyckoff:</b>
├─ Фаза: {wyckoff['phase']}
├─ Уверенность: {wyckoff['confidence']}
└─ Описание: {wyckoff.get('description', 'N/A')}

<b>Режим рынка:</b>
├─ Режим: {regime['regime']}
├─ Сила: {regime['strength']}
└─ Волатильность: {regime.get('volatility_pct', 0):.2f}%

<b>Market Bias:</b>
├─ Направление: {bias['bias']}
├─ Сила: {bias['strength']}
└─ Momentum: {bias.get('momentum_pct', 0):.2f}%

{ai_interpretation}
━━━━━━━━━━━━━━━━━━━━━━
"""

            # Отправляем результат
            await loading_msg.delete()
            await update.message.reply_text(response, parse_mode=ParseMode.HTML)

            logger.info(f"✅ Расширенная аналитика для {symbol} отправлена")

        except Exception as e:
            logger.error(f"❌ Ошибка в /advanced: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Ошибка при анализе: {str(e)}", parse_mode=ParseMode.MARKDOWN
            )

    async def cmd_market(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """market SYMBOL - Market Intelligence (НОВАЯ ВЕРСИЯ С KEY LEVELS)"""
        try:
            if not context.args:
                await update.message.reply_text(
                    "❌ Использование: /market SYMBOL\n" "Пример: /market BTCUSDT",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            symbol = context.args[0].upper()

            # ✅ ИСПРАВЛЕНИЕ: правильная обработка символа
            if not symbol.endswith("USDT"):
                # Убираем USD если есть, затем добавляем USDT
                if symbol.endswith("USD"):
                    symbol = symbol[:-3] + "USDT"
                else:
                    symbol = f"{symbol}USDT"

            # Отправить сообщение о загрузке
            loading_msg = await update.message.reply_text(
                f"⏳ Анализирую {symbol}...", parse_mode=ParseMode.MARKDOWN
            )

            # ✅ ИСПОЛЬЗУЕМ НОВЫЙ MarketDashboard (если доступен)
            if (
                hasattr(self.bot_instance, "market_dashboard")
                and self.bot_instance.market_dashboard
            ):
                try:
                    # ✅ WYCKOFF ANALYSIS (ДОБАВЛЕНО!)
                    wyckoff_text = ""
                    try:
                        logger.info(f"🔍 [WYCKOFF] Анализирую {symbol}...")

                        if hasattr(self.bot_instance, "wyckoff_analyzer"):
                            wyckoff_phase = (
                                await self.bot_instance.wyckoff_analyzer.analyze_phase(
                                    symbol, timeframe="60"
                                )
                            )

                            if wyckoff_phase.phase != "Unknown":
                                wyckoff_text = f"📊 **Wyckoff Phase:** {wyckoff_phase.phase} ({wyckoff_phase.confidence:.0f}%)\n"
                                wyckoff_text += f"└─ {wyckoff_phase.sub_phase or wyckoff_phase.description}\n"

                                if wyckoff_phase.signals:
                                    wyckoff_text += "\n🔍 **Signals:**\n"
                                    for signal in wyckoff_phase.signals[:2]:
                                        wyckoff_text += f"├─ {signal}\n"

                                wyckoff_text += (
                                    f"\n💡 **Action:** {wyckoff_phase.action}\n"
                                )
                            else:
                                wyckoff_text = f"📊 **Wyckoff Phase:** Unknown\n"

                            logger.info(
                                f"✅ [WYCKOFF] {symbol} = {wyckoff_phase.phase} ({wyckoff_phase.confidence:.0f}%)"
                            )
                        else:
                            logger.warning("⚠️ [WYCKOFF] wyckoff_analyzer не найден!")
                            wyckoff_text = "📊 **Wyckoff Phase:** Unknown\n"

                    except Exception as e:
                        logger.error(f"❌ [WYCKOFF] Ошибка: {e}", exc_info=True)
                        wyckoff_text = f"📊 **Wyckoff Phase:** Error\n"

                    # Генерируем dashboard
                    message = (
                        await self.bot_instance.market_dashboard.generate_dashboard(
                            symbol
                        )
                    )

                    # ✅ ЗАМЕНЯЕМ строку "Wyckoff Phase: Unknown" на wyckoff_text
                    message = message.replace(
                        "📊 **Wyckoff Phase:** Unknown", wyckoff_text.strip()
                    )

                    # Отправить результат
                    await loading_msg.edit_text(
                        message, parse_mode=None, disable_web_page_preview=True
                    )

                    logger.info(f"✅ /market {symbol} отправлен (НОВЫЙ ФОРМАТ)")
                    return

                except Exception as e:
                    logger.error(f"❌ Ошибка MarketDashboard: {e}", exc_info=True)
                    # Fallback на старый формат

            # ⚠️ FALLBACK: СТАРЫЙ ФОРМАТ (если MarketDashboard недоступен)
            logger.warning(f"⚠️ MarketDashboard недоступен, использую старый формат")

            market_data = await self.bot_instance.get_market_data(symbol)
            if not market_data:
                await loading_msg.edit_text(
                    f"❌ Не удалось получить данные для {symbol}"
                )
                return

            scenarios = await self.bot_instance.get_matching_scenarios(symbol, limit=3)

            # Старый формат
            message = self._format_full_market_analysis(
                symbol, market_data, scenarios, None
            )

            await loading_msg.edit_text(
                message, parse_mode=None, disable_web_page_preview=True
            )

            logger.info(f"✅ /market {symbol} отправлен (СТАРЫЙ ФОРМАТ)")

        except Exception as e:
            logger.error(f"❌ cmd_market: {e}", exc_info=True)
            try:
                await update.message.reply_text(
                    f"❌ Ошибка: {str(e)}", parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass

    async def cmd_overview(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /overview - Multi-Symbol Overview"""
        try:
            await update.message.reply_text("📊 Загрузка обзора рынка...")

            # Список символов для анализа
            symbols = [
                "BTCUSDT",
                "ETHUSDT",
                "SOLUSDT",
                "XRPUSDT",
                "BNBUSDT",
                "DOGEUSDT",
                "ADAUSDT",
                "AVAXUSDT",
            ]

            message = "📊 *MULTI-SYMBOL OVERVIEW*\n\n"
            message += "━━━━━━━━━━━━━━━━━━━━━━\n"
            message += "💰 *ЦЕНЫ И ИЗМЕНЕНИЯ*\n"
            message += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

            total_volume = 0

            # Собираем данные по всем символам
            for symbol in symbols:
                try:
                    data = await self.bot_instance.get_market_data(symbol)
                    if data:
                        price = data.get("price", 0)
                        change = data.get("change_24h", 0)
                        volume = data.get("volume_24h", 0)

                        emoji = "🟢" if change >= 0 else "🔴"

                        message += (
                            f"{emoji} *{symbol.replace('USDT', '')}:* ${price:,.2f} "
                        )
                        message += f"({change:+.2f}%)\n"

                        total_volume += volume
                except Exception as e:
                    logger.error(f"Error getting data for {symbol}: {e}")

            message += f"\n💎 *Общий объём:* ${total_volume:,.0f}\n\n"

            message += "━━━━━━━━━━━━━━━━━━━━━━\n"
            message += "📈 *MARKET SENTIMENT*\n"
            message += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

            # Анализ настроений рынка
            if hasattr(self.bot_instance, "market_sentiment"):
                sentiment = (
                    await self.bot_instance.market_sentiment.get_overall_sentiment()
                )
                message += f"Настроение: {sentiment.get('overall', 'Neutral')}\n"
                message += (
                    f"Индекс страха/жадности: {sentiment.get('fear_greed', 50)}\n"
                )
            else:
                message += "⚠️ Анализ настроений недоступен\n"

            message += "\n━━━━━━━━━━━━━━━━━━━━━━\n"
            message += "🔗 *КОРРЕЛЯЦИИ*\n"
            message += "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            message += "BTC-ETH: 0.87 (высокая)\n"
            message += "BTC-SOL: 0.73 (средняя)\n"
            message += "ETH-SOL: 0.82 (высокая)\n"

            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

        except Exception as e:
            logger.error(f"Error in cmd_overview: {e}")
            await update.message.reply_text(f"❌ Ошибка получения обзора: {str(e)}")

    # ==================== WEBHOOK SUPPORT ====================

    async def set_webhook(self, webhook_url: str):
        """Установка webhook для Telegram"""
        try:
            if not self.application or not self.application.bot:
                logger.error("❌ Application or bot not initialized!")
                return False

            await self.application.bot.set_webhook(webhook_url)
            logger.info(f"✅ Webhook set: {webhook_url}")
            return True
        except Exception as e:
            logger.error(f"❌ Webhook setup error: {e}", exc_info=True)
            return False

    async def delete_webhook(self):
        """Удаление webhook"""
        try:
            if not self.application or not self.application.bot:
                logger.error("❌ Application or bot not initialized!")
                return False

            await self.application.bot.delete_webhook()
            logger.info("✅ Webhook deleted")
            return True
        except Exception as e:
            logger.error(f"❌ Delete webhook error: {e}", exc_info=True)
            return False

    async def process_webhook_update(self, update_data: dict):
        """Обработка webhook update от Telegram"""
        try:
            from telegram import Update

            if not self.application:
                logger.error("❌ Application not initialized!")
                return

            # Конвертируем dict в Telegram Update object
            update = Update.de_json(update_data, self.application.bot)

            # Обрабатываем update через application
            await self.application.process_update(update)

            logger.debug(f"✅ Webhook update processed: {update.update_id}")
        except Exception as e:
            logger.error(f"❌ Process webhook update error: {e}", exc_info=True)

    def _format_full_market_analysis(
        self, symbol: str, data: Dict, scenarios: List[Dict], sr_levels: Dict = None
    ) -> str:
        try:
            lines = [f"📊 ПОЛНЫЙ АНАЛИЗ РЫНКА: {symbol}", "═" * 63, ""]

            # 1. ЦЕНА И ОБЪЁМ
            lines.extend(self._format_price_section(data))

            # 2. ТЕХНИЧЕСКИЕ ИНДИКАТОРЫ
            lines.extend(self._format_indicators_section(data))

            # 3. WHALE ACTIVITY
            if "whale_activity" in data:
                lines.extend(self._format_whale_section(data))

            # 4. ORDERBOOK PRESSURE
            if "orderbook" in data:
                lines.extend(self._format_orderbook_section(data))

            # 5. CVD
            if "cvd" in data:
                lines.extend(self._format_cvd_section(data))

            # 6. LIQUIDATIONS (24H)
            if "liquidations" in data and data["liquidations"]:
                lines.extend(self._format_liquidations_section(data))

            # ✅ 7. ИТОГИ И ВЫВОДЫ
            lines.extend(self._format_conclusions_section(symbol, data, scenarios))

            # Разделитель и время
            lines.append("═" * 63)
            lines.append(
                f"⏰ Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} EEST"
            )

            # ✅ SUPPORT & RESISTANCE LEVELS
            if sr_levels and sr_levels.get("support_levels"):
                lines.append("")
                lines.append("═" * 63)
                lines.append("")
                lines.append("🎯 *SUPPORT & RESISTANCE LEVELS*")
                lines.append("")

                # Key Levels
                key_support = sr_levels.get("key_support", {})
                key_resistance = sr_levels.get("key_resistance", {})

                if key_support:
                    lines.append(
                        f"🟢 *Key Support:* ${key_support.get('price', 0):,.2f} [{key_support.get('strength', 'N/A').upper()}]"
                    )
                if key_resistance:
                    lines.append(
                        f"🔴 *Key Resistance:* ${key_resistance.get('price', 0):,.2f} [{key_resistance.get('strength', 'N/A').upper()}]"
                    )
                lines.append("")

                # Support Levels
                lines.append("🟢 *Support Levels:*")
                for level in sr_levels.get("support_levels", [])[:3]:
                    lines.append(
                        f"   ${level.get('price', 0):,.2f} - {level.get('strength', 'N/A')} ({level.get('source', 'N/A')})"
                    )

                # Resistance Levels
                lines.append("")
                lines.append("🔴 *Resistance Levels:*")
                for level in sr_levels.get("resistance_levels", [])[:3]:
                    lines.append(
                        f"   ${level.get('price', 0):,.2f} - {level.get('strength', 'N/A')} ({level.get('source', 'N/A')})"
                    )

                # Summary
                lines.append("")
                lines.append(f"📊 *Summary:* {sr_levels.get('summary', 'N/A')}")
                lines.append("")

            return "\n".join(lines)
        except Exception as e:
            logger.error(f"_format_full_market_analysis error: {e}", exc_info=True)
            return f"❌ Ошибка анализа рынка: {symbol}"

    def _calculate_volume_profile(self, symbol: str) -> Dict:
        """Упрощённый Volume Profile на основе последних 100 трейдов из whale_trades"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # ИСПРАВЛЕНО: используем таблицу whale_trades вместо market_data
            query = """
            SELECT price, size FROM whale_trades
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT 100
            """
            cursor.execute(query, (symbol,))
            rows = cursor.fetchall()
            conn.close()

            if not rows or len(rows) < 10:
                logger.warning(f"Volume Profile: недостаточно данных для {symbol}")
                return {"poc": 0, "vah": 0, "val": 0}

            prices = [row[0] for row in rows if row[0] > 0]
            volumes = [row[1] for row in rows if row[1] > 0]  # size вместо volume

            if not prices or not volumes:
                return {"poc": 0, "vah": 0, "val": 0}

            # POC = цена с максимальным объёмом
            max_vol_idx = volumes.index(max(volumes))
            poc = prices[max_vol_idx]

            # VAH/VAL = топ 30% и низ 30% по объёму
            sorted_data = sorted(zip(prices, volumes), key=lambda x: x[1], reverse=True)
            top_30_count = max(1, len(sorted_data) // 3)
            top_30 = sorted_data[:top_30_count]

            if top_30:
                vah = max([p for p, v in top_30])
                val = min([p for p, v in top_30])
            else:
                vah = max(prices)
                val = min(prices)

            logger.info(
                f"Volume Profile для {symbol}: POC={poc:.2f}, VAH={vah:.2f}, VAL={val:.2f}"
            )
            return {"poc": poc, "vah": vah, "val": val}

        except Exception as e:
            logger.error(f"Volume Profile calculation error: {e}", exc_info=True)
            return {"poc": 0, "vah": 0, "val": 0}

    def _format_price_section(self, data: Dict) -> List[str]:
        """Секция ЦЕНА И ОБЪЁМ"""
        try:
            change_24h = data.get("change_24h", 0)
            change_emoji = "📈" if change_24h > 0 else "📉" if change_24h < 0 else "➡️"

            return [
                "💰 *ЦЕНА И ОБЪЁМ*",
                f"├─ Цена: ${data['price']:,.2f}  ({change_emoji} {change_24h:+.2f}% за 24ч)",
                f"├─ Макс 24ч: ${data.get('high_24h', 0):,.2f}",
                f"├─ Мин 24ч: ${data.get('low_24h', 0):,.2f}",
                f"└─ Объём 24ч: ${data.get('volume_24h', 0)/1e9:.2f}B",
                "",
            ]
        except Exception as e:
            logger.error(f"❌ _format_price_section: {e}")
            return ["💰 *ЦЕНА И ОБЪЁМ*", "└─ Данные недоступны", ""]

    def _format_indicators_section(self, data: Dict) -> List[str]:
        """Секция ТЕХНИЧЕСКИЕ ИНДИКАТОРЫ"""
        try:
            rsi = data.get("rsi", 50)
            rsi_status = (
                "OVERBOUGHT" if rsi > 70 else "OVERSOLD" if rsi < 30 else "NEUTRAL"
            )

            macd = data.get("macd", 0)
            macd_signal = data.get("macd_signal", 0)
            macd_status = "BULLISH ↗" if macd > macd_signal else "BEARISH ↘"

            ema_status = (
                "ABOVE - BULLISH"
                if data["price"] > data.get("ema_20", 0)
                else "BELOW - BEARISH"
            )

            return [
                "📈 *ТЕХНИЧЕСКИЕ ИНДИКАТОРЫ*",
                f"├─ RSI(14): {rsi:.1f}  [{rsi_status}]",
                f"├─ MACD: {macd:.1f} (Signal: {macd_signal:.1f})  [{macd_status}]",
                f"├─ EMA(20): ${data.get('ema_20', 0):,.2f}  [{ema_status}]",
                "└─ BB: Средний диапазон",
                "",
            ]
        except Exception as e:
            logger.error(f"❌ _format_indicators_section: {e}")
            return ["📈 *ТЕХНИЧЕСКИЕ ИНДИКАТОРЫ*", "└─ Данные недоступны", ""]

    def _format_whale_section(self, data: Dict) -> List[str]:
        """Секция WHALE ACTIVITY"""
        try:
            wa = data["whale_activity"]
            net = wa.get("net_volume", 0)
            net_emoji = "🟢" if net > 0 else "🔴" if net < 0 else "⚪"

            sentiment_emojis = {
                "BULLISH": "🚀",
                "SLIGHTLY_BULLISH": "🟢",
                "NEUTRAL": "⚪",
                "SLIGHTLY_BEARISH": "🔴",
                "BEARISH": "💀",
            }
            sentiment_emoji = sentiment_emojis.get(wa.get("sentiment", "NEUTRAL"), "⚪")

            return [
                "🐋 *WHALE ACTIVITY (15 мин)*",
                f"├─ Крупных трейдов: {wa.get('count', 0)}  (🟢{wa.get('buy_count', 0)} BUY / 🔴{wa.get('sell_count', 0)} SELL)",
                f"├─ Buy Volume: ${wa.get('buy_volume', 0)/1e6:.1f}M",
                f"├─ Sell Volume: ${wa.get('sell_volume', 0)/1e6:.1f}M",
                f"├─ Net Volume: {net_emoji} ${abs(net)/1e6:.1f}M",
                f"└─ Sentiment: {sentiment_emoji} {wa.get('sentiment', 'NEUTRAL')}",
                "",
            ]
        except Exception as e:
            logger.error(f"❌ _format_whale_section: {e}")
            return ["🐋 *WHALE ACTIVITY*", "└─ Данные недоступны", ""]

    def _format_orderbook_section(self, data: Dict) -> List[str]:
        """Секция ORDERBOOK PRESSURE"""
        try:
            ob = data["orderbook"]
            pressure = ob.get("bid_pressure", 0)
            pressure_emoji = (
                "🟢 STRONG BUY"
                if pressure > 30
                else "🔴 STRONG SELL" if pressure < -30 else "⚪ NEUTRAL"
            )

            return [
                "📊 *ORDERBOOK PRESSURE*",
                f"├─ Bid/Ask Ratio: {ob.get('bid_ask_ratio', 1):.2f}  [{pressure_emoji}]",
                f"├─ Bid Pressure: {pressure:+.1f}%",
                f"├─ Spread: ${ob.get('spread', 0):.2f} ({ob.get('spread_pct', 0):.3f}%)",
                f"└─ Imbalance: {pressure_emoji} SIDE",
                "",
            ]
        except Exception as e:
            logger.error(f"❌ _format_orderbook_section: {e}")
            return ["📊 *ORDERBOOK PRESSURE*", "└─ Данные недоступны", ""]

    def _format_cvd_section(self, data: Dict) -> List[str]:
        """Секция CVD"""
        try:
            cvd = data["cvd"]
            cvd_5m = cvd.get("cvd_5m", 0)
            cvd_15m = cvd.get("cvd_15m", 0)

            cvd_5m_status = "BULLISH 📈" if cvd_5m > 0 else "BEARISH 📉"
            cvd_15m_status = (
                "STRONG BULLISH 🚀"
                if cvd_15m > 1e7
                else "BULLISH 📈" if cvd_15m > 0 else "BEARISH 📉"
            )

            trend_emojis = {"INCREASING": "📈", "DECREASING": "📉", "STABLE": "➡️"}
            trend_emoji = trend_emojis.get(cvd.get("trend", "STABLE"), "➡️")

            return [
                "📉 *CVD (Cumulative Volume Delta)*",
                f"├─ CVD 5м: ${abs(cvd_5m)/1e6:.1f}M  [{cvd_5m_status}]",
                f"├─ CVD 15м: ${abs(cvd_15m)/1e6:.1f}M  [{cvd_15m_status}]",
                f"├─ CVD %: {cvd.get('cvd_pct', 0):+.1f}%",
                f"└─ Trend: {trend_emoji} {cvd.get('trend', 'STABLE')}",
                "",
            ]
        except Exception as e:
            logger.error(f"❌ _format_cvd_section: {e}")
            return ["📉 *CVD*", "└─ Данные недоступны", ""]

    def _format_liquidations_section(self, data: Dict) -> List[str]:
        """Форматирование секции LIQUIDATIONS (24H)"""
        try:
            if "liquidations" not in data or not data["liquidations"]:
                return []  # Не показываем секцию, если данных нет

            liq = data["liquidations"]
            total = liq.get("total", 0)
            total_long = liq.get("total_long", 0)
            total_short = liq.get("total_short", 0)
            long_pct = liq.get("long_pct", 0)
            short_pct = liq.get("short_pct", 0)
            count = liq.get("count", 0)

            # Форматирование в миллионы
            total_m = total / 1_000_000
            long_m = total_long / 1_000_000
            short_m = total_short / 1_000_000

            # Определяем давление и риск
            if long_pct > 65:
                pressure = "🔴 LONG SQUEEZE"
                risk = "⚠️ High risk for longs"
            elif short_pct > 65:
                pressure = "🟢 SHORT SQUEEZE"
                risk = "⚠️ High risk for shorts"
            elif abs(long_pct - short_pct) < 10:
                pressure = "⚖️ BALANCED"
                risk = "✅ Normal conditions"
            else:
                pressure = "⚠️ MODERATE"
                risk = "⚡ Monitor closely"

            return [
                "",
                "💥 *LIQUIDATIONS (24H)*",
                f"├─ Total: ${total_m:.2f}M ({count} events)",
                f"├─ 🟢 Longs: ${long_m:.2f}M ({long_pct:.1f}%)",
                f"├─ 🔴 Shorts: ${short_m:.2f}M ({short_pct:.1f}%)",
                f"├─ Pressure: {pressure}",
                f"└─ Risk: {risk}",
            ]

        except Exception as e:
            logger.error(f"❌ _format_liquidations_section error: {e}", exc_info=True)
            return []

    def _format_conclusions_section(
        self, symbol: str, data: Dict, scenarios: List[Dict]
    ) -> List[str]:
        """Форматирование секции ИТОГИ И ВЫВОДЫ"""
        try:
            lines = ["═" * 63, "", "📋 *ИТОГИ И ВЫВОДЫ*", "═" * 63, ""]

            # Определяем общее настроение рынка
            sentiment_score = 0
            sentiment_reasons = []

            # Whale activity
            if "whale_activity" in data:
                whale = data["whale_activity"]
                net_volume = whale.get("net_volume", 0)
                if net_volume > 1_000_000:  # > $1M
                    sentiment_score += 2
                    sentiment_reasons.append("✅ Киты покупают")
                elif net_volume < -1_000_000:  # < -$1M
                    sentiment_score -= 2
                    sentiment_reasons.append("⚠️ Киты продают")

            # Orderbook pressure
            if "orderbook" in data:
                ob = data["orderbook"]
                bid_pressure = ob.get("bid_pressure", 0)
                if bid_pressure > 30:
                    sentiment_score += 1
                    sentiment_reasons.append("✅ Сильное давление покупателей")
                elif bid_pressure < -30:
                    sentiment_score -= 1
                    sentiment_reasons.append("⚠️ Сильное давление продавцов")

            # CVD
            if "cvd" in data:
                cvd = data["cvd"]
                cvd_pct = cvd.get("cvd_pct", 0)
                if cvd_pct > 10:
                    sentiment_score += 1
                    sentiment_reasons.append(
                        "✅ CVD положительный (покупатели активнее)"
                    )
                elif cvd_pct < -10:
                    sentiment_score -= 1
                    sentiment_reasons.append("⚠️ CVD отрицательный (продавцы активнее)")

            # Liquidations
            if "liquidations" in data and data["liquidations"]:
                liq = data["liquidations"]
                short_pct = liq.get("short_pct", 50)
                if short_pct > 65:
                    sentiment_score += 1
                    sentiment_reasons.append("✅ Short squeeze (шорты ликвидируются)")
                elif short_pct < 35:
                    sentiment_score -= 1
                    sentiment_reasons.append("⚠️ Long squeeze (лонги ликвидируются)")

            # RSI
            rsi = data.get("rsi", 50)
            if rsi > 70:
                sentiment_score -= 1
                sentiment_reasons.append("⚠️ RSI перекуплен")
            elif rsi < 30:
                sentiment_score += 1
                sentiment_reasons.append("✅ RSI перепродан")

            # MACD
            macd = data.get("macd", 0)
            macd_signal = data.get("macd_signal", 0)
            if macd > macd_signal:
                sentiment_score += 1
                sentiment_reasons.append("✅ MACD бычий")
            elif macd < macd_signal:
                sentiment_score -= 1
                sentiment_reasons.append("⚠️ MACD медвежий")

            # Определяем общий тренд
            if sentiment_score >= 3:
                market_mood = "🟢 БЫЧИЙ"
                market_strength = f"{min(sentiment_score * 15, 100)}/100"
                trend = "📈 ВОСХОДЯЩИЙ"
                momentum = "⬆️ СИЛЬНЫЙ"
            elif sentiment_score <= -3:
                market_mood = "🔴 МЕДВЕЖИЙ"
                market_strength = f"{min(abs(sentiment_score) * 15, 100)}/100"
                trend = "📉 НИСХОДЯЩИЙ"
                momentum = "⬇️ СЛАБЫЙ"
            else:
                market_mood = "🟡 НЕЙТРАЛЬНЫЙ"
                market_strength = f"50/100"
                trend = "➡️ БОКОВОЙ"
                momentum = "➡️ СТАБИЛЬНЫЙ"

            # Выводы
            lines.append("🎯 *ОБЩАЯ ОЦЕНКА:*")
            lines.append(f"   Рынок: {market_mood} (сила: {market_strength})")
            lines.append(f"   Тренд: {trend}")
            lines.append(f"   Momentum: {momentum}")
            lines.append("")

            # Ключевые факторы
            lines.append("💡 *КЛЮЧЕВЫЕ ФАКТОРЫ:*")
            for reason in sentiment_reasons[:5]:  # Максимум 5 причин
                lines.append(f"   {reason}")
            if not sentiment_reasons:
                lines.append("   Недостаточно данных для анализа")
            lines.append("")

            # Рекомендация
            lines.append("🎯 *РЕКОМЕНДАЦИЯ:*")
            price = data.get("price", 0)

            if price == 0:
                lines.append("   └─ Нет данных о цене")
                lines.append("")
                return lines

            if sentiment_score >= 3:
                action = "🟢 LONG (покупка)"
                entry_low = price * 0.995
                entry_high = price * 1.005
                tp1 = price * 1.018
                tp2 = price * 1.033
                sl = price * 0.99
            elif sentiment_score <= -3:
                action = "🔴 SHORT (продажа)"
                entry_low = price * 0.995
                entry_high = price * 1.005
                tp1 = price * 0.982
                tp2 = price * 0.967
                sl = price * 1.01
            else:
                action = "⚪ WAIT (ожидание)"
                lines.append(f"   └─ Действие: {action}")
                lines.append(f"   └─ Рынок в консолидации, ждите чёткого сигнала")
                lines.append("")
                return lines

            rr_ratio = abs((tp1 - price) / (sl - price)) if (sl - price) != 0 else 0

            lines.append(f"   └─ Действие: {action}")
            lines.append(f"   └─ Вход: ${entry_low:,.2f} - ${entry_high:,.2f}")
            lines.append(
                f"   └─ Цель 1: ${tp1:,.2f} ({((tp1 / price - 1) * 100):+.1f}%)"
            )
            lines.append(
                f"   └─ Цель 2: ${tp2:,.2f} ({((tp2 / price - 1) * 100):+.1f}%)"
            )
            lines.append(f"   └─ Стоп: ${sl:,.2f} ({((sl / price - 1) * 100):+.1f}%)")
            lines.append(
                f"   └─ R/R: {rr_ratio:.1f}:1 {'(отлично)' if rr_ratio > 2 else '(хорошо)' if rr_ratio > 1.5 else '(осторожно)'}"
            )
            lines.append(f"   └─ Таймфрейм: 1-4 часа")
            lines.append("")

            # Вероятные сценарии
            lines.append("🎲 *ВЕРОЯТНЫЕ СЦЕНАРИИ:*")
            if sentiment_score >= 3:
                lines.append(f"   1. 📈 Пробой вверх → ${price * 1.02:,.0f}   [60%]")
                lines.append(
                    f"   2. 🔄 Консолидация → ${price * 0.995:,.0f}-{price * 1.005:,.0f}   [25%]"
                )
                lines.append(f"   3. 📉 Откат → ${price * 0.98:,.0f}   [15%]")
            elif sentiment_score <= -3:
                lines.append(f"   1. 📉 Пробой вниз → ${price * 0.98:,.0f}   [60%]")
                lines.append(
                    f"   2. 🔄 Консолидация → ${price * 0.995:,.0f}-{price * 1.005:,.0f}   [25%]"
                )
                lines.append(f"   3. 📈 Отскок → ${price * 1.02:,.0f}   [15%]")
            else:
                lines.append(
                    f"   1. 🔄 Консолидация → ${price * 0.995:,.0f}-{price * 1.005:,.0f}   [50%]"
                )
                lines.append(f"   2. 📈 Пробой вверх → ${price * 1.02:,.0f}   [25%]")
                lines.append(f"   3. 📉 Пробой вниз → ${price * 0.98:,.0f}   [25%]")
            lines.append("")

            # Тэги
            tags = []
            if sentiment_score >= 3:
                tags.append("#bullish")
            elif sentiment_score <= -3:
                tags.append("#bearish")
            else:
                tags.append("#neutral")

            if "whale_activity" in data:
                net = data["whale_activity"].get("net_volume", 0)
                if net < -1_000_000:
                    tags.append("#whale_distribution")
                elif net > 1_000_000:
                    tags.append("#whale_accumulation")

            if tags:
                lines.append(f"🏷️ *ТЭГИ:* {' '.join(tags)}")
                lines.append("")

            return lines

        except Exception as e:
            logger.error(f"❌ _format_conclusions_section error: {e}", exc_info=True)
            return ["", "❌ Ошибка формирования выводов", ""]

    def _format_summary_section(
        self, symbol: str, data: Dict, scenarios: List[Dict]
    ) -> List[str]:
        """Секция ИТОГИ И ВЫВОДЫ"""
        try:
            lines = [
                "═══════════════════════════════════════════════════════════════",
                "📋 ИТОГИ И ВЫВОДЫ",
                "═══════════════════════════════════════════════════════════════",
                "",
            ]

            # 1. ОБЩАЯ ОЦЕНКА
            market_state = self._get_market_state(data)
            lines.extend(
                [
                    "🎯 ОБЩАЯ ОЦЕНКА:",
                    f"   Рынок: {market_state['emoji']} {market_state['name']} (сила: {market_state['strength']}/10)",
                    f"   Тренд: {market_state['trend_emoji']} {market_state['trend']}",
                    f"   Momentum: {market_state['momentum_emoji']} {market_state['momentum']}",
                    "",
                ]
            )

            # 2. КЛЮЧЕВЫЕ ФАКТОРЫ
            key_factors = self._get_key_factors(data)
            lines.append("💡 КЛЮЧЕВЫЕ ФАКТОРЫ:")
            for factor in key_factors[:6]:
                emoji = "✅" if factor["positive"] else "⚠️"
                lines.append(f"   {emoji} {factor['text']}")
            lines.append("")

            # 3. СТАТИСТИКА
            signals = self._count_signals(data)
            lines.extend(
                [
                    "📊 СТАТИСТИКА:",
                    f"   • Бычьих сигналов: {signals['bullish']}/{signals['total']} ({signals['bullish_pct']:.0f}%)",
                    f"   • Медвежьих сигналов: {signals['bearish']}/{signals['total']} ({signals['bearish_pct']:.0f}%)",
                    f"   • Confidence: {signals['confidence_emoji']} {signals['confidence_text']} ({signals['confidence']:.0f}%)",
                    "",
                ]
            )

            # 4. РЕКОМЕНДАЦИЯ
            recommendation = self._generate_recommendation(data, signals)
            if recommendation["action"] != "WAIT":
                lines.extend(
                    [
                        "🎯 РЕКОМЕНДАЦИЯ:",
                        f"   └─ Действие: {recommendation['action_emoji']} {recommendation['action']}",
                        f"   └─ Вход: ${recommendation['entry_min']:,.2f} - ${recommendation['entry_max']:,.2f}",
                        f"   └─ Цель 1: ${recommendation['target1']:,.2f} ({recommendation['target1_pct']:+.1f}%)",
                        f"   └─ Цель 2: ${recommendation['target2']:,.2f} ({recommendation['target2_pct']:+.1f}%)",
                        f"   └─ Стоп: ${recommendation['stop']:,.2f} ({recommendation['stop_pct']:+.1f}%)",
                        f"   └─ R/R: {recommendation['rr']:.1f}:1 ({recommendation['rr_quality']})",
                        f"   └─ Таймфрейм: {recommendation['timeframe']}",
                        "",
                    ]
                )
            else:
                lines.extend(
                    [
                        "🎯 РЕКОМЕНДАЦИЯ:",
                        f"   └─ Действие: {recommendation['action_emoji']} {recommendation['action']}",
                        f"   └─ Причина: Нет чётких сигналов (confidence < 65%)",
                        "",
                    ]
                )

            # 5. РИСКИ
            risks = self._identify_risks(data)
            if risks:
                lines.append("⚠️ РИСКИ:")
                for risk in risks[:3]:
                    lines.append(f"   • {risk}")
                lines.append("")

            # 6. ВЕРОЯТНЫЕ СЦЕНАРИИ
            probable = self._get_probable_scenarios(data, signals)
            lines.append("🎲 ВЕРОЯТНЫЕ СЦЕНАРИИ:")
            for i, sc in enumerate(probable, 1):
                lines.append(
                    f"   {i}. {sc['emoji']} {sc['text']} → {sc['target']}   [{sc['probability']:.0f}%]"
                )
            lines.append("")

            # 7. ТЭГИ
            tags = self._generate_tags(data, signals)
            lines.append(f"🏷️ ТЭГИ: {' '.join(tags)}")

            return lines
        except Exception as e:
            logger.error(f"❌ _format_summary_section: {e}")
            return ["📋 ИТОГИ", "└─ Ошибка генерации итогов", ""]

    def _get_market_state(self, data: Dict) -> Dict:
        """Определить состояние рынка"""
        rsi = data.get("rsi", 50)
        macd_diff = data.get("macd", 0) - data.get("macd_signal", 0)
        cvd_pct = data.get("cvd", {}).get("cvd_pct", 0)
        whale_net = data.get("whale_activity", {}).get("net_volume", 0)

        bullish_score = 0
        if rsi > 50:
            bullish_score += 1
        if macd_diff > 0:
            bullish_score += 2
        if cvd_pct > 5:
            bullish_score += 2
        if whale_net > 0:
            bullish_score += 2
        if data.get("price", 0) > data.get("ema_20", 0):
            bullish_score += 1

        strength = int((bullish_score / 8) * 10)

        if bullish_score >= 6:
            return {
                "emoji": "🟢",
                "name": "БЫЧИЙ",
                "strength": strength,
                "trend_emoji": "📈",
                "trend": "ВОСХОДЯЩИЙ",
                "momentum_emoji": "🚀",
                "momentum": "СИЛЬНЫЙ",
            }
        elif bullish_score <= 2:
            return {
                "emoji": "🔴",
                "name": "МЕДВЕЖИЙ",
                "strength": 10 - strength,
                "trend_emoji": "📉",
                "trend": "НИСХОДЯЩИЙ",
                "momentum_emoji": "⬇️",
                "momentum": "СЛАБЫЙ",
            }
        else:
            return {
                "emoji": "⚪",
                "name": "НЕЙТРАЛЬНЫЙ",
                "strength": 5,
                "trend_emoji": "↔️",
                "trend": "БОКОВОЙ",
                "momentum_emoji": "🔄",
                "momentum": "СРЕДНИЙ",
            }

    def _get_key_factors(self, data: Dict) -> List[Dict]:
        """Ключевые факторы"""
        factors = []

        whale_net = data.get("whale_activity", {}).get("net_volume", 0)
        if abs(whale_net) > 1e6:
            factors.append(
                {
                    "positive": whale_net > 0,
                    "text": f"Киты активно {'покупают' if whale_net > 0 else 'продают'} (${abs(whale_net)/1e6:.1f}M)",
                }
            )

        cvd = data.get("cvd", {})
        cvd_pct = cvd.get("cvd_pct", 0)
        if abs(cvd_pct) > 5:
            factors.append(
                {
                    "positive": cvd_pct > 0,
                    "text": f"CVD {'растёт' if cvd_pct > 0 else 'падает'} ({cvd_pct:+.1f}%)",
                }
            )

        ob_pressure = data.get("orderbook", {}).get("bid_pressure", 0)
        if abs(ob_pressure) > 30:
            factors.append(
                {
                    "positive": ob_pressure > 0,
                    "text": f"Orderbook перекошен в {'покупки' if ob_pressure > 0 else 'продажи'} ({abs(ob_pressure):.0f}%)",
                }
            )

        macd_diff = data.get("macd", 0) - data.get("macd_signal", 0)
        if abs(macd_diff) > 50:
            factors.append(
                {
                    "positive": macd_diff > 0,
                    "text": f"MACD {'бычий' if macd_diff > 0 else 'медвежий'} кроссовер",
                }
            )

        rsi = data.get("rsi", 50)
        if rsi > 65:
            factors.append(
                {"positive": False, "text": f"RSI перекупленность ({rsi:.1f})"}
            )
        elif rsi < 35:
            factors.append(
                {"positive": False, "text": f"RSI перепроданность ({rsi:.1f})"}
            )

        return factors

    def _count_signals(self, data: Dict) -> Dict:
        """Подсчёт сигналов"""
        bullish = bearish = 0

        if data.get("rsi", 50) > 50:
            bullish += 1
        elif data.get("rsi", 50) < 50:
            bearish += 1

        macd_diff = data.get("macd", 0) - data.get("macd_signal", 0)
        if macd_diff > 0:
            bullish += 1
        elif macd_diff < 0:
            bearish += 1

        cvd_pct = data.get("cvd", {}).get("cvd_pct", 0)
        if cvd_pct > 0:
            bullish += 1
        elif cvd_pct < 0:
            bearish += 1

        whale_net = data.get("whale_activity", {}).get("net_volume", 0)
        if whale_net > 0:
            bullish += 1
        elif whale_net < 0:
            bearish += 1

        if data.get("price", 0) > data.get("ema_20", 0):
            bullish += 1
        elif data.get("price", 0) < data.get("ema_20", 0):
            bearish += 1

        total = bullish + bearish
        bullish_pct = (bullish / total * 100) if total > 0 else 0
        bearish_pct = (bearish / total * 100) if total > 0 else 0
        confidence = max(bullish_pct, bearish_pct)

        conf_emoji = "🟢" if confidence >= 70 else "🟡" if confidence >= 50 else "🔴"
        conf_text = (
            "ВЫСОКАЯ"
            if confidence >= 70
            else "СРЕДНЯЯ" if confidence >= 50 else "НИЗКАЯ"
        )

        return {
            "bullish": bullish,
            "bearish": bearish,
            "total": total,
            "bullish_pct": bullish_pct,
            "bearish_pct": bearish_pct,
            "confidence": confidence,
            "confidence_emoji": conf_emoji,
            "confidence_text": conf_text,
        }

    def _generate_recommendation(self, data: Dict, signals: Dict) -> Dict:
        """Генерация рекомендации"""
        price = data.get("price", 0)

        if signals["bullish_pct"] >= 65:
            entry_min, entry_max = price * 0.999, price * 1.002
            target1, target2 = price * 1.018, price * 1.033
            stop = price * 0.990
            return {
                "action_emoji": "🟢",
                "action": "LONG (покупка)",
                "entry_min": entry_min,
                "entry_max": entry_max,
                "target1": target1,
                "target1_pct": ((target1 - price) / price) * 100,
                "target2": target2,
                "target2_pct": ((target2 - price) / price) * 100,
                "stop": stop,
                "stop_pct": ((stop - price) / price) * 100,
                "rr": (target1 - price) / (price - stop),
                "rr_quality": (
                    "отлично" if (target1 - price) / (price - stop) >= 2 else "хорошо"
                ),
                "timeframe": "1-4 часа",
            }
        elif signals["bearish_pct"] >= 65:
            entry_min, entry_max = price * 0.998, price * 1.001
            target1, target2 = price * 0.982, price * 0.967
            stop = price * 1.010
            return {
                "action_emoji": "🔴",
                "action": "SHORT (продажа)",
                "entry_min": entry_min,
                "entry_max": entry_max,
                "target1": target1,
                "target1_pct": ((target1 - price) / price) * 100,
                "target2": target2,
                "target2_pct": ((target2 - price) / price) * 100,
                "stop": stop,
                "stop_pct": ((stop - price) / price) * 100,
                "rr": (price - target1) / (stop - price),
                "rr_quality": (
                    "отлично" if (price - target1) / (stop - price) >= 2 else "хорошо"
                ),
                "timeframe": "1-4 часа",
            }
        else:
            return {
                "action_emoji": "⚪",
                "action": "WAIT (ожидание)",
                "entry_min": 0,
                "entry_max": 0,
                "target1": 0,
                "target1_pct": 0,
                "target2": 0,
                "target2_pct": 0,
                "stop": 0,
                "stop_pct": 0,
                "rr": 0,
                "rr_quality": "н/д",
                "timeframe": "дождаться сигнала",
            }

    def _identify_risks(self, data: Dict) -> List[str]:
        """Определение рисков"""
        risks = []
        price = data.get("price", 0)
        high_24h = data.get("high_24h", 0)

        if price > high_24h * 0.98:
            risks.append(f"Сильное сопротивление на ${high_24h:,.0f}")

        rsi = data.get("rsi", 50)
        if rsi > 65:
            risks.append("RSI > 70 → вероятна коррекция")
        elif rsi < 35:
            risks.append("RSI < 30 → возможен отскок")

        if not data.get("volume_above_avg", True):
            risks.append("Снижение объёма может остановить движение")

        return risks

    def _get_probable_scenarios(self, data: Dict, signals: Dict) -> List[Dict]:
        """Вероятные сценарии"""
        price = data.get("price", 0)

        if signals["bullish_pct"] >= 60:
            return [
                {
                    "emoji": "📈",
                    "text": "Пробой вверх",
                    "target": f"${price * 1.025:,.0f}",
                    "probability": 60,
                },
                {
                    "emoji": "🔄",
                    "text": "Консолидация",
                    "target": f"${price * 0.995:,.0f}-{price * 1.005:,.0f}",
                    "probability": 25,
                },
                {
                    "emoji": "📉",
                    "text": "Откат",
                    "target": f"${price * 0.98:,.0f}",
                    "probability": 15,
                },
            ]
        elif signals["bearish_pct"] >= 60:
            return [
                {
                    "emoji": "📉",
                    "text": "Пробой вниз",
                    "target": f"${price * 0.975:,.0f}",
                    "probability": 60,
                },
                {
                    "emoji": "🔄",
                    "text": "Консолидация",
                    "target": f"${price * 0.995:,.0f}-{price * 1.005:,.0f}",
                    "probability": 25,
                },
                {
                    "emoji": "📈",
                    "text": "Отскок",
                    "target": f"${price * 1.02:,.0f}",
                    "probability": 15,
                },
            ]
        else:
            return [
                {
                    "emoji": "🔄",
                    "text": "Боковое движение",
                    "target": f"${price * 0.99:,.0f}-{price * 1.01:,.0f}",
                    "probability": 50,
                },
                {
                    "emoji": "📈",
                    "text": "Прорыв вверх",
                    "target": f"${price * 1.02:,.0f}",
                    "probability": 25,
                },
                {
                    "emoji": "📉",
                    "text": "Прорыв вниз",
                    "target": f"${price * 0.98:,.0f}",
                    "probability": 25,
                },
            ]

    def _calculate_volume_profile(self, symbol: str) -> Dict:
        """Упрощённый Volume Profile на основе последних 100 свечей"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = """
            SELECT price, volume FROM market_data
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT 100
            """
            cursor.execute(query, (symbol,))
            rows = cursor.fetchall()
            conn.close()

            if not rows or len(rows) < 10:
                logger.warning(f"Volume Profile: недостаточно данных для {symbol}")
                return {"poc": 0, "vah": 0, "val": 0}

            prices = [row[0] for row in rows if row[0] > 0]
            volumes = [row[1] for row in rows if row[1] > 0]

            if not prices or not volumes:
                return {"poc": 0, "vah": 0, "val": 0}

            # POC = цена с максимальным объёмом
            max_vol_idx = volumes.index(max(volumes))
            poc = prices[max_vol_idx]

            # VAH/VAL = топ 30% и низ 30% по объёму
            sorted_data = sorted(zip(prices, volumes), key=lambda x: x[1], reverse=True)
            top_30_count = max(1, len(sorted_data) // 3)
            top_30 = sorted_data[:top_30_count]

            if top_30:
                vah = max([p for p, v in top_30])
                val = min([p for p, v in top_30])
            else:
                vah = max(prices)
                val = min(prices)

            logger.info(
                f"Volume Profile для {symbol}: POC={poc:.2f}, VAH={vah:.2f}, VAL={val:.2f}"
            )
            return {"poc": poc, "vah": vah, "val": val}

        except Exception as e:
            logger.error(f"Volume Profile calculation error: {e}", exc_info=True)
            return {"poc": 0, "vah": 0, "val": 0}

    def _generate_tags(self, data: Dict, signals: Dict) -> List[str]:
        """Генерация тэгов"""
        tags = []

        if signals["bullish_pct"] >= 60:
            tags.append("#bullish")
        elif signals["bearish_pct"] >= 60:
            tags.append("#bearish")
        else:
            tags.append("#neutral")

        whale_net = data.get("whale_activity", {}).get("net_volume", 0)
        if whale_net > 1e6:
            tags.append("#whale_accumulation")
        elif whale_net < -1e6:
            tags.append("#whale_distribution")

        macd_diff = data.get("macd", 0) - data.get("macd_signal", 0)
        if abs(macd_diff) > 100:
            tags.append("#momentum")

        if data.get("price", 0) > data.get("high_24h", 0) * 0.99:
            tags.append("#breakout")

        rsi = data.get("rsi", 50)
        if rsi > 65:
            tags.append("#overbought")
        elif rsi < 35:
            tags.append("#oversold")

        return tags[:5]

    def _format_summary_section(
        self, symbol: str, data: Dict, scenarios: List[Dict]
    ) -> List[str]:
        """Секция ИТОГИ И ВЫВОДЫ"""
        try:
            lines = [
                "═══════════════════════════════════════════════════════════════",
                "📋 *ИТОГИ И ВЫВОДЫ*",
                "═══════════════════════════════════════════════════════════════",
                "",
            ]

            # 1. ОБЩАЯ ОЦЕНКА
            market_state = self._get_market_state(data)
            lines.extend(
                [
                    "🎯 *ОБЩАЯ ОЦЕНКА:*",
                    f"   Рынок: {market_state['emoji']} {market_state['name']} (сила: {market_state['strength']}/10)",
                    f"   Тренд: {market_state['trend_emoji']} {market_state['trend']}",
                    f"   Momentum: {market_state['momentum_emoji']} {market_state['momentum']}",
                    "",
                ]
            )

            # 2. КЛЮЧЕВЫЕ ФАКТОРЫ
            key_factors = self._get_key_factors(data)
            lines.append("💡 *КЛЮЧЕВЫЕ ФАКТОРЫ:*")
            for factor in key_factors[:6]:
                emoji = "✅" if factor["positive"] else "⚠️"
                lines.append(f"   {emoji} {factor['text']}")
            lines.append("")

            # 3. СТАТИСТИКА
            signals = self._count_signals(data)
            lines.extend(
                [
                    "📊 *СТАТИСТИКА:*",
                    f"   • Бычьих сигналов: {signals['bullish']}/{signals['total']} ({signals['bullish_pct']:.0f}%)",
                    f"   • Медвежьих сигналов: {signals['bearish']}/{signals['total']} ({signals['bearish_pct']:.0f}%)",
                    f"   • Confidence: {signals['confidence_emoji']} {signals['confidence_text']} ({signals['confidence']:.0f}%)",
                    "",
                ]
            )

            # 4. РЕКОМЕНДАЦИЯ
            recommendation = self._generate_recommendation(data, signals)
            if recommendation["action"] != "WAIT":
                lines.extend(
                    [
                        "🎯 *РЕКОМЕНДАЦИЯ:*",
                        f"   └─ Действие: {recommendation['action_emoji']} {recommendation['action']}",
                        f"   └─ Вход: ${recommendation['entry_min']:,.2f} - ${recommendation['entry_max']:,.2f}",
                        f"   └─ Цель 1: ${recommendation['target1']:,.2f} ({recommendation['target1_pct']:+.1f}%)",
                        f"   └─ Цель 2: ${recommendation['target2']:,.2f} ({recommendation['target2_pct']:+.1f}%)",
                        f"   └─ Стоп: ${recommendation['stop']:,.2f} ({recommendation['stop_pct']:+.1f}%)",
                        f"   └─ R/R: {recommendation['rr']:.1f}:1 ({recommendation['rr_quality']})",
                        f"   └─ Таймфрейм: {recommendation['timeframe']}",
                        "",
                    ]
                )
            else:
                lines.extend(
                    [
                        "🎯 *РЕКОМЕНДАЦИЯ:*",
                        f"   └─ Действие: {recommendation['action_emoji']} {recommendation['action']}",
                        f"   └─ Причина: Нет чётких сигналов (confidence < 65%)",
                        "",
                    ]
                )

            # 5. РИСКИ
            risks = self._identify_risks(data)
            if risks:
                lines.append("⚠️ *РИСКИ:*")
                for risk in risks[:3]:
                    lines.append(f"   • {risk}")
                lines.append("")

            # 6. ВЕРОЯТНЫЕ СЦЕНАРИИ
            probable = self._get_probable_scenarios(data, signals)
            lines.append("🎲 *ВЕРОЯТНЫЕ СЦЕНАРИИ:*")
            for i, sc in enumerate(probable, 1):
                lines.append(
                    f"   {i}. {sc['emoji']} {sc['text']} → {sc['target']}   [{sc['probability']:.0f}%]"
                )
            lines.append("")

            # 7. ТЭГИ
            tags = self._generate_tags(data, signals)
            lines.append(f"🏷️ *ТЭГИ:* {' '.join(tags)}")

            return lines
        except Exception as e:
            logger.error(f"❌ _format_summary_section: {e}")
            return ["📋 *ИТОГИ*", "└─ Ошибка генерации итогов", ""]

    def _get_market_state(self, data: Dict) -> Dict:
        """Определить состояние рынка"""
        rsi = data.get("rsi", 50)
        macd_diff = data.get("macd", 0) - data.get("macd_signal", 0)
        cvd_pct = data.get("cvd", {}).get("cvd_pct", 0)
        whale_net = data.get("whale_activity", {}).get("net_volume", 0)

        bullish_score = 0
        if rsi > 50:
            bullish_score += 1
        if macd_diff > 0:
            bullish_score += 2
        if cvd_pct > 5:
            bullish_score += 2
        if whale_net > 0:
            bullish_score += 2
        if data.get("price", 0) > data.get("ema_20", 0):
            bullish_score += 1

        strength = int((bullish_score / 8) * 10)

        if bullish_score >= 6:
            return {
                "emoji": "🟢",
                "name": "БЫЧИЙ",
                "strength": strength,
                "trend_emoji": "📈",
                "trend": "ВОСХОДЯЩИЙ",
                "momentum_emoji": "🚀",
                "momentum": "СИЛЬНЫЙ",
            }
        elif bullish_score <= 2:
            return {
                "emoji": "🔴",
                "name": "МЕДВЕЖИЙ",
                "strength": 10 - strength,
                "trend_emoji": "📉",
                "trend": "НИСХОДЯЩИЙ",
                "momentum_emoji": "⬇️",
                "momentum": "СЛАБЫЙ",
            }
        else:
            return {
                "emoji": "⚪",
                "name": "НЕЙТРАЛЬНЫЙ",
                "strength": 5,
                "trend_emoji": "↔️",
                "trend": "БОКОВОЙ",
                "momentum_emoji": "🔄",
                "momentum": "СРЕДНИЙ",
            }

    def _get_key_factors(self, data: Dict) -> List[Dict]:
        """Ключевые факторы"""
        factors = []

        whale_net = data.get("whale_activity", {}).get("net_volume", 0)
        if abs(whale_net) > 1e6:
            factors.append(
                {
                    "positive": whale_net > 0,
                    "text": f"Киты активно {'покупают' if whale_net > 0 else 'продают'} (${abs(whale_net)/1e6:.1f}M)",
                }
            )

        cvd = data.get("cvd", {})
        cvd_pct = cvd.get("cvd_pct", 0)
        if abs(cvd_pct) > 5:
            factors.append(
                {
                    "positive": cvd_pct > 0,
                    "text": f"CVD {'растёт' if cvd_pct > 0 else 'падает'} ({cvd_pct:+.1f}%)",
                }
            )

        ob_pressure = data.get("orderbook", {}).get("bid_pressure", 0)
        if abs(ob_pressure) > 30:
            factors.append(
                {
                    "positive": ob_pressure > 0,
                    "text": f"Orderbook перекошен в {'покупки' if ob_pressure > 0 else 'продажи'} ({abs(ob_pressure):.0f}%)",
                }
            )

        macd_diff = data.get("macd", 0) - data.get("macd_signal", 0)
        if abs(macd_diff) > 50:
            factors.append(
                {
                    "positive": macd_diff > 0,
                    "text": f"MACD {'бычий' if macd_diff > 0 else 'медвежий'} кроссовер",
                }
            )

        rsi = data.get("rsi", 50)
        if rsi > 65:
            factors.append(
                {"positive": False, "text": f"RSI перекупленность ({rsi:.1f})"}
            )
        elif rsi < 35:
            factors.append(
                {"positive": False, "text": f"RSI перепроданность ({rsi:.1f})"}
            )

        return factors

    def _count_signals(self, data: Dict) -> Dict:
        """Подсчёт сигналов"""
        bullish = bearish = 0

        if data.get("rsi", 50) > 50:
            bullish += 1
        elif data.get("rsi", 50) < 50:
            bearish += 1

        macd_diff = data.get("macd", 0) - data.get("macd_signal", 0)
        if macd_diff > 0:
            bullish += 1
        elif macd_diff < 0:
            bearish += 1

        cvd_pct = data.get("cvd", {}).get("cvd_pct", 0)
        if cvd_pct > 0:
            bullish += 1
        elif cvd_pct < 0:
            bearish += 1

        whale_net = data.get("whale_activity", {}).get("net_volume", 0)
        if whale_net > 0:
            bullish += 1
        elif whale_net < 0:
            bearish += 1

        if data.get("price", 0) > data.get("ema_20", 0):
            bullish += 1
        elif data.get("price", 0) < data.get("ema_20", 0):
            bearish += 1

        total = bullish + bearish
        bullish_pct = (bullish / total * 100) if total > 0 else 0
        bearish_pct = (bearish / total * 100) if total > 0 else 0
        confidence = max(bullish_pct, bearish_pct)

        conf_emoji = "🟢" if confidence >= 70 else "🟡" if confidence >= 50 else "🔴"
        conf_text = (
            "ВЫСОКАЯ"
            if confidence >= 70
            else "СРЕДНЯЯ" if confidence >= 50 else "НИЗКАЯ"
        )

        return {
            "bullish": bullish,
            "bearish": bearish,
            "total": total,
            "bullish_pct": bullish_pct,
            "bearish_pct": bearish_pct,
            "confidence": confidence,
            "confidence_emoji": conf_emoji,
            "confidence_text": conf_text,
        }

    def _generate_recommendation(self, data: Dict, signals: Dict) -> Dict:
        """Генерация рекомендации"""
        price = data.get("price", 0)

        if signals["bullish_pct"] >= 65:
            entry_min, entry_max = price * 0.999, price * 1.002
            target1, target2 = price * 1.018, price * 1.033
            stop = price * 0.990
            return {
                "action_emoji": "🟢",
                "action": "LONG (покупка)",
                "entry_min": entry_min,
                "entry_max": entry_max,
                "target1": target1,
                "target1_pct": ((target1 - price) / price) * 100,
                "target2": target2,
                "target2_pct": ((target2 - price) / price) * 100,
                "stop": stop,
                "stop_pct": ((stop - price) / price) * 100,
                "rr": (target1 - price) / (price - stop),
                "rr_quality": (
                    "отлично" if (target1 - price) / (price - stop) >= 2 else "хорошо"
                ),
                "timeframe": "1-4 часа",
            }
        elif signals["bearish_pct"] >= 65:
            entry_min, entry_max = price * 0.998, price * 1.001
            target1, target2 = price * 0.982, price * 0.967
            stop = price * 1.010
            return {
                "action_emoji": "🔴",
                "action": "SHORT (продажа)",
                "entry_min": entry_min,
                "entry_max": entry_max,
                "target1": target1,
                "target1_pct": ((target1 - price) / price) * 100,
                "target2": target2,
                "target2_pct": ((target2 - price) / price) * 100,
                "stop": stop,
                "stop_pct": ((stop - price) / price) * 100,
                "rr": (price - target1) / (stop - price),
                "rr_quality": (
                    "отлично" if (price - target1) / (stop - price) >= 2 else "хорошо"
                ),
                "timeframe": "1-4 часа",
            }
        else:
            return {
                "action_emoji": "⚪",
                "action": "WAIT (ожидание)",
                "entry_min": 0,
                "entry_max": 0,
                "target1": 0,
                "target1_pct": 0,
                "target2": 0,
                "target2_pct": 0,
                "stop": 0,
                "stop_pct": 0,
                "rr": 0,
                "rr_quality": "н/д",
                "timeframe": "дождаться сигнала",
            }

    def _identify_risks(self, data: Dict) -> List[str]:
        """Определение рисков"""
        risks = []
        price = data.get("price", 0)
        high_24h = data.get("high_24h", 0)

        if price > high_24h * 0.98:
            risks.append(f"Сильное сопротивление на ${high_24h:,.0f}")

        rsi = data.get("rsi", 50)
        if rsi > 65:
            risks.append("RSI > 70 → вероятна коррекция")
        elif rsi < 35:
            risks.append("RSI < 30 → возможен отскок")

        if not data.get("volume_above_avg", True):
            risks.append("Снижение объёма может остановить движение")

        return risks

    def _get_probable_scenarios(self, data: Dict, signals: Dict) -> List[Dict]:
        """Вероятные сценарии"""
        price = data.get("price", 0)

        if signals["bullish_pct"] >= 60:
            return [
                {
                    "emoji": "📈",
                    "text": "Пробой вверх",
                    "target": f"${price * 1.025:,.0f}",
                    "probability": 60,
                },
                {
                    "emoji": "🔄",
                    "text": "Консолидация",
                    "target": f"${price * 0.995:,.0f}-{price * 1.005:,.0f}",
                    "probability": 25,
                },
                {
                    "emoji": "📉",
                    "text": "Откат",
                    "target": f"${price * 0.98:,.0f}",
                    "probability": 15,
                },
            ]
        elif signals["bearish_pct"] >= 60:
            return [
                {
                    "emoji": "📉",
                    "text": "Пробой вниз",
                    "target": f"${price * 0.975:,.0f}",
                    "probability": 60,
                },
                {
                    "emoji": "🔄",
                    "text": "Консолидация",
                    "target": f"${price * 0.995:,.0f}-{price * 1.005:,.0f}",
                    "probability": 25,
                },
                {
                    "emoji": "📈",
                    "text": "Отскок",
                    "target": f"${price * 1.02:,.0f}",
                    "probability": 15,
                },
            ]
        else:
            return [
                {
                    "emoji": "🔄",
                    "text": "Боковое движение",
                    "target": f"${price * 0.99:,.0f}-{price * 1.01:,.0f}",
                    "probability": 50,
                },
                {
                    "emoji": "📈",
                    "text": "Прорыв вверх",
                    "target": f"${price * 1.02:,.0f}",
                    "probability": 25,
                },
                {
                    "emoji": "📉",
                    "text": "Прорыв вниз",
                    "target": f"${price * 0.98:,.0f}",
                    "probability": 25,
                },
            ]

    def _generate_tags(self, data: Dict, signals: Dict) -> List[str]:
        """Генерация тэгов"""
        tags = []

        if signals["bullish_pct"] >= 60:
            tags.append("#bullish")
        elif signals["bearish_pct"] >= 60:
            tags.append("#bearish")
        else:
            tags.append("#neutral")

        whale_net = data.get("whale_activity", {}).get("net_volume", 0)
        if whale_net > 1e6:
            tags.append("#whale_accumulation")
        elif whale_net < -1e6:
            tags.append("#whale_distribution")

        macd_diff = data.get("macd", 0) - data.get("macd_signal", 0)
        if abs(macd_diff) > 100:
            tags.append("#momentum")

        if data.get("price", 0) > data.get("high_24h", 0) * 0.99:
            tags.append("#breakout")

        rsi = data.get("rsi", 50)
        if rsi > 65:
            tags.append("#overbought")
        elif rsi < 35:
            tags.append("#oversold")

        return tags[:5]
