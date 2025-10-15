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
from telegram_handlers.gio_dashboard_handler import GIODashboardHandler
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ParseMode
from config.settings import logger, TELEGRAM_CONFIG, DATA_DIR
import pandas as pd
import sqlite3


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

        if not self.enabled:
            logger.warning("⚠️ Telegram bot disabled")
        else:
            logger.info("✅ TelegramBotHandler инициализирован")

    async def initialize(self):
        """Инициализация Telegram Application"""
        if not self.enabled:
            return False

        try:
            self.application = Application.builder().token(self.token).build()

            # Регистрируем все команды
            self.application.add_handler(CommandHandler("start", self.cmd_start))
            self.application.add_handler(CommandHandler("help", self.cmd_help))
            self.application.add_handler(CommandHandler("status", self.cmd_status))
            self.application.add_handler(
                CommandHandler("signal_stats", self.cmd_signal_stats)
            )
            self.application.add_handler(
                CommandHandler("signal_history", self.cmd_signal_history)
            )
            self.application.add_handler(CommandHandler("analyze", self.cmd_analyze))
            self.application.add_handler(CommandHandler("trades", self.cmd_trades))
            self.application.add_handler(CommandHandler("stats", self.cmd_stats))
            self.application.add_handler(CommandHandler("signals", self.cmd_signals))
            self.application.add_handler(
                CommandHandler("autosignals", self.cmd_autosignals)
            )
            self.application.add_handler(CommandHandler("export", self.cmd_export))
            self.application.add_handler(
                CommandHandler("analyze_batching", self.cmd_analyze_batching)
            )
            self.application.add_handler(
                CommandHandler("analyze_batching", self.cmd_analyze_batching)
            )
            self.application.add_handler(CommandHandler("pairs", self.cmd_pairs))
            self.application.add_handler(CommandHandler("add", self.cmd_add))
            self.application.add_handler(CommandHandler("remove", self.cmd_remove))
            self.application.add_handler(CommandHandler("enable", self.cmd_enable))
            self.application.add_handler(CommandHandler("disable", self.cmd_disable))
            self.application.add_handler(
                CommandHandler("available", self.cmd_available)
            )
            self.application.add_handler(CommandHandler("roi", self.cmd_roi))
            self.application.add_handler(CommandHandler("mtf", self.cmd_mtf))
            self.application.add_handler(CommandHandler("filters", self.cmd_filters))
            self.application.add_handler(CommandHandler("scenario", self.cmd_scenario))
            self.application.add_handler(CommandHandler("market", self.cmd_market))
            self.application.add_handler(CommandHandler("advanced", self.cmd_advanced))
            self.application.add_handler(CommandHandler("whale", self.cmd_whale))
            self.application.add_handler(
                CommandHandler("gio", self.gio_dashboard.cmd_gio)
            )

            from telegram_handlers.market_overview_handler import MarketOverviewHandler

            self.market_overview_handler = MarketOverviewHandler(self.bot_instance)
            self.application.add_handler(
                CommandHandler("overview", self.market_overview_handler.cmd_overview)
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
                "🚀 *GIO Crypto Bot v3.0 запущен!*\n\nИспользуйте /help для списка команд."
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
        """Отправить справку - все команды"""
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            logger.info(f"📋 cmd_help вызвана (user_id={user_id}, username={username})")

            text = """📋 GIO MARKET INTELLIGENCE — КОМАНДЫ

    🎯 Главные Дашборды:
    • /gio [SYMBOL] — Unified Market Intelligence Dashboard
    • /overview — Multi-Symbol Market Overview (8 активов)
    • /market [SYMBOL] — Главный дашборд рынка

    📊 Продвинутая Аналитика:
    • /advanced SYMBOL — Продвинутые индикаторы
    • /scenario SYMBOL — Текущий сценарий ММ и фаза Wyckoff
    • /filters — Статус фильтров (Confirm, Multi-TF)
    • /mtf SYMBOL — Multi-Timeframe тренды (1H/4H/1D)

    📈 Корреляция  и Sentiment:
    • /correlation — Матрица корреляций топ-5 активов
    • /corrpair SYMBOL1 SYMBOL2 — Корреляция между двумя активами

    💧 Ликвидность и Киты:
    • /liquidity [SYMBOL] — Анализ глубины ликвидности и whale walls

    📊 Производительность Сигналов:
    • /performance [days] — Статистика производительности сигналов
    • /bestsignals — Топ-10 лучших сигналов
    • /worstsignals — Топ-10 худших сигналов

    🔧 Системные:
    • /status — Статус системы
    • /pairs — Список отслеживаемых пар
    • /add SYMBOL — Добавить новую пару
    • /remove SYMBOL — Удалить пару

    ━━━━━━━━━━━━━━━━━━━━━━

💡 Примеры использования:
    /gio BTCUSDT
    /overview
    /market ETHUSDT
    /advanced SOLUSDT
    /performance 7

━━━━━━━━━━━━━━━━━━━━━━
    📖 О GIO:
GIO Market Intelligence - это аналитическая
платформа для трейдеров,  с AI-интерпретацией рыночных данных.
🎯 Фокус: Аналитика, Сигналы, Уведомления"""

            await update.message.reply_text(text)
            logger.info(f"✅ cmd_help успешно отправлена (username={username})")

        except Exception as e:
            logger.error(f"❌ Ошибка в cmd_help: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

    async def cmd_signal_history(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Показать историю сигналов"""
        try:
            user_id = update.effective_user.id
            username = update.effective_user.username or "Unknown"
            logger.info(
                f"📊 cmd_signal_history вызвана (user_id={user_id}, username={username})"
            )

            args = context.args
            days = int(args[0]) if args and args[0].isdigit() else 30

            # Получить завершённые сигналы из ROI Tracker
            if not hasattr(self.bot_instance, "roi_tracker"):
                await update.message.reply_text("❌ ROI Tracker не инициализирован")
                return

            completed_signals = self.bot_instance.roi_tracker.completed_signals

            if not completed_signals:
                text = f"📊 *ИСТОРИЯ СИГНАЛОВ* ({days} дней)\n\n"
                text += "Нет завершённых сигналов"
                await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
                return

            # Фильтровать по дням
            from datetime import datetime, timedelta

            cutoff_date = datetime.now() - timedelta(days=days)

            recent_signals = [
                s
                for s in completed_signals
                if s.close_time and datetime.fromisoformat(s.close_time) > cutoff_date
            ]

            if not recent_signals:
                text = f"📊 *ИСТОРИЯ СИГНАЛОВ* ({days} дней)\n\n"
                text += f"Нет сигналов за последние {days} дней"
                await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
                return

            # Форматировать ответ
            text = f"📊 *ИСТОРИЯ СИГНАЛОВ* ({days} дней)\n\n"
            text += f"📈 *Всего:* {len(recent_signals)} сигналов\n\n"

            # Показать последние 10
            for signal in recent_signals[-10:]:
                direction = "🟢 LONG" if signal.direction == "long" else "🔴 SHORT"
                status_emoji = "✅" if signal.status == "completed" else "🛑"
                roi_emoji = "🟢" if signal.current_roi > 0 else "🔴"

                text += f"{direction} *{signal.symbol}* {status_emoji}\n"
                text += f"├─ Entry: ${signal.entry_price:.2f}\n"
                text += f"├─ Status: {signal.status.upper()}\n"
                text += f"└─ ROI: {roi_emoji} {signal.current_roi:+.2f}%\n\n"

            if len(recent_signals) > 10:
                text += f"...и ещё {len(recent_signals) - 10} сигналов\n"

            await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
            logger.info(
                f"✅ cmd_signal_history успешно отправлена (username={username})"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка в cmd_signal_history: {e}")
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")

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

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Команда /status - Статус системы С ПОЛНОЙ СТАТИСТИКОЙ"""
        try:
            # ========== MEMORY ==========
            memory = self.bot_instance.memory_manager.get_statistics()

            # ========== SIGNALS FROM DB ==========
            db_path = os.path.join(DATA_DIR, "gio_bot.db")
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

            db_path = os.path.join(DATA_DIR, "gio_bot.db")
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

            db_path = os.path.join(DATA_DIR, "gio_bot.db")
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

            db_path = os.path.join(DATA_DIR, "gio_bot.db")
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
            db_path = os.path.join(DATA_DIR, "gio_bot.db")
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

    async def cmd_market(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        📊 /market [SYMBOL] - Market Dashboard (альтернатива Coinglass)

        Использование:
            /market - показать дашборд для BTCUSDT (по умолчанию)
            /market ETHUSDT - показать дашборд для ETHUSDT
            /market eth - показать дашборд для ETHUSDT (автодополнение)
        """
        try:
            # Извлекаем символ из команды
            if context.args:
                symbol = context.args[0].upper()
                if not symbol.endswith("USDT"):
                    symbol = f"{symbol}USDT"
            else:
                symbol = "BTCUSDT"

            logger.info(
                f"📊 /market запрошен для {symbol} (user: {update.effective_user.username})"
            )

            # Проверяем доступность MarketDashboard
            if not hasattr(self.bot_instance, "market_dashboard"):
                await update.message.reply_text(
                    "❌ Market Dashboard не инициализирован. "
                    "Обратитесь к администратору."
                )
                return

            # Отправляем "Загрузка..." сообщение
            loading_msg = await update.message.reply_text(
                f"⏳ Загрузка dashboard для {symbol}..."
            )

            # Генерируем dashboard
            try:
                dashboard_text = (
                    await self.bot_instance.market_dashboard.generate_dashboard(symbol)
                )

                # ========== 🐋 WHALE ACTIVITY INTEGRATION ==========

                # Получить whale activity
                whale_section = ""
                if (
                    hasattr(self.bot_instance, "whale_tracker")
                    and self.bot_instance.whale_tracker
                ):
                    try:
                        whale_activity = (
                            self.bot_instance.whale_tracker.get_whale_activity(symbol)
                        )

                        # Форматирование
                        if whale_activity["trades"] > 0:
                            whale_emoji = "🐋"

                            if whale_activity["dominant_side"] == "bullish":
                                whale_sentiment = "🟢 Bullish"
                            elif whale_activity["dominant_side"] == "bearish":
                                whale_sentiment = "🔴 Bearish"
                            else:
                                whale_sentiment = "⚪ Neutral"

                            # Форматировать объёмы
                            def format_vol(vol):
                                if vol >= 1_000_000:
                                    return f"${vol/1_000_000:.2f}M"
                                elif vol >= 1_000:
                                    return f"${vol/1_000:.2f}K"
                                else:
                                    return f"${vol:.2f}"

                            buy_vol_str = format_vol(whale_activity["buy_volume"])
                            sell_vol_str = format_vol(whale_activity["sell_volume"])
                            net_str = format_vol(abs(whale_activity["net"]))
                            net_sign = "+" if whale_activity["net"] > 0 else "-"
                        else:
                            whale_emoji = "💤"
                            whale_sentiment = "⚪ Neutral"
                            buy_vol_str = "$0.00"
                            sell_vol_str = "$0.00"
                            net_str = "$0.00"
                            net_sign = ""

                        whale_section = f"""
    {whale_emoji} WHALE ACTIVITY (5min)
    ├─ Trades: {whale_activity['trades']}
    ├─ Buy Vol: {buy_vol_str}
    ├─ Sell Vol: {sell_vol_str}
    └─ Net: {net_sign}{net_str} {whale_sentiment}

    """
                    except Exception as e:
                        logger.debug(f"Ошибка получения whale activity: {e}")

                # Вставить whale_section в dashboard_text
                if whale_section:
                    # Найти позицию для вставки (перед LIQUIDATION ZONES)
                    insert_pos = dashboard_text.find("⚠️ LIQUIDATION ZONES")
                    if insert_pos != -1:
                        dashboard_text = (
                            dashboard_text[:insert_pos]
                            + whale_section
                            + dashboard_text[insert_pos:]
                        )
                    else:
                        # Если не найдено, добавить в конец (перед Updated timestamp)
                        insert_pos = dashboard_text.find("⏱️ Updated:")
                        if insert_pos != -1:
                            dashboard_text = (
                                dashboard_text[:insert_pos]
                                + whale_section
                                + dashboard_text[insert_pos:]
                            )
                        else:
                            # Если всё остальное не сработало, просто добавить в конец
                            dashboard_text += whale_section

                # ========== КОНЕЦ ИНТЕГРАЦИИ WHALE TRACKER ==========

                # Удаляем "Загрузка..." и отправляем dashboard
                await loading_msg.delete()

                await update.message.reply_text(
                    dashboard_text, parse_mode=ParseMode.MARKDOWN
                )

            except Exception as e:
                # ✅ ДОБАВЛЕН EXCEPT БЛОК
                logger.error(f"❌ Ошибка генерации dashboard: {e}", exc_info=True)
                await loading_msg.edit_text(
                    f"❌ Ошибка при генерации dashboard для {symbol}\n"
                    f"Причина: {str(e)}"
                )

        except Exception as e:
            # ✅ ВНЕШНИЙ EXCEPT БЛОК
            logger.error(f"❌ Ошибка cmd_market: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Ошибка: {str(e)}", parse_mode=ParseMode.MARKDOWN
            )

    async def cmd_advanced(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /advanced SYMBOL - Расширенная аналитика

        Включает:
        - Продвинутые индикаторы (MACD, Stoch RSI, BB, ATR, ADX)
        - Паттерны (свечные, S/R уровни, структура)
        - Рыночная структура (Wyckoff, режим, ликвидность)
        """
        try:
            # Парсинг аргументов
            if not context.args:
                await update.message.reply_text(
                    "❌ Использование: /advanced BTCUSDT", parse_mode=ParseMode.MARKDOWN
                )
                return

            symbol = context.args[0].upper()
            if not symbol.endswith("USDT"):
                symbol = f"{symbol}USDT"

            logger.info(
                f"📊 /advanced {symbol} от пользователя {update.effective_user.username}"
            )

            # Показываем "печатает..."
            loading_msg = await update.message.reply_text(
                f"🔍 Анализирую {symbol}...\n⏳ Это займёт 5-10 секунд...",
                parse_mode=ParseMode.MARKDOWN,
            )

            # Импортируем новые модули
            from analytics.advanced_indicators import AdvancedIndicators
            from analytics.pattern_detector import PatternDetector
            from analytics.market_structure import MarketStructureAnalyzer

            # Получаем данные через коннектор
            connector = self.bot_instance.bybit_connector

            # Получаем klines для 4H
            klines = await connector.get_klines(symbol, "240", limit=100)

            if not klines or len(klines) == 0:
                await loading_msg.edit_text(
                    f"❌ Не удалось получить данные для {symbol}",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            # Извлекаем OHLCV из списка словарей
            candles = klines  # klines уже список
            opens = [float(c["open"]) for c in candles]
            highs = [float(c["high"]) for c in candles]
            lows = [float(c["low"]) for c in candles]
            closes = [float(c["close"]) for c in candles]
            volumes = [float(c["volume"]) for c in candles]

            # ==========================================
            # 📊 ПРОДВИНУТЫЕ ИНДИКАТОРЫ
            # ==========================================

            macd = AdvancedIndicators.calculate_macd(closes)
            stoch_rsi = AdvancedIndicators.calculate_stoch_rsi(closes)
            bb = AdvancedIndicators.calculate_bollinger_bands(closes)
            atr = AdvancedIndicators.calculate_atr(highs, lows, closes)
            adx = AdvancedIndicators.calculate_adx(highs, lows, closes)

            # ==========================================
            # 🎯 ПАТТЕРНЫ
            # ==========================================

            patterns = PatternDetector.detect_candlestick_patterns(
                opens, highs, lows, closes
            )

            sr_levels = PatternDetector.find_support_resistance(highs, lows, closes)

            trend_structure = PatternDetector.detect_trend_structure(
                highs, lows, closes
            )

            # ==========================================
            # 🏛️ РЫНОЧНАЯ СТРУКТУРА
            # ==========================================

            wyckoff = MarketStructureAnalyzer.analyze_wyckoff_phase(
                opens, highs, lows, closes, volumes
            )

            regime = MarketStructureAnalyzer.identify_market_regime(closes, highs, lows)

            bias = MarketStructureAnalyzer.calculate_market_bias(closes, volumes)

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

    async def cmd_whale(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        🐋 /whale SYMBOL - Детальный просмотр whale activity
        """
        try:
            if not context.args:
                await update.message.reply_text(
                    "❌ Использование: /whale BTCUSDT\n" "Пример: /whale BTC",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            symbol = context.args[0].upper()
            if not symbol.endswith("USDT"):
                symbol = f"{symbol}USDT"

            logger.info(
                f"🐋 /whale запрошен для {symbol} (user: {update.effective_user.username})"
            )

            # Проверить WhaleTracker
            if (
                not hasattr(self.bot_instance, "whale_tracker")
                or not self.bot_instance.whale_tracker
            ):
                await update.message.reply_text(
                    "❌ Whale Tracker не инициализирован. "
                    "Обратитесь к администратору."
                )
                return

            # Показать loading
            loading_msg = await update.message.reply_text(
                f"⏳ Загрузка whale activity для {symbol}..."
            )

            # Получить данные
            whale_activity = self.bot_instance.whale_tracker.get_whale_activity(symbol)

            # Удалить loading
            await loading_msg.delete()

            if whale_activity["trades"] == 0:
                await update.message.reply_text(
                    f"🐋 *WHALE ACTIVITY:* {symbol}\n\n"
                    f"💤 Нет активности китов за последние 5 минут\n"
                    f"(Порог: >$100K за сделку)\n\n"
                    f"🔄 Обновите: /whale {symbol}",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return

            # Форматирование детального отчёта
            buy_vol = whale_activity["buy_volume"]
            sell_vol = whale_activity["sell_volume"]
            net = whale_activity["net"]
            total_vol = buy_vol + sell_vol

            buy_pressure = (buy_vol / total_vol * 100) if total_vol > 0 else 50
            sell_pressure = (sell_vol / total_vol * 100) if total_vol > 0 else 50

            # Определить sentiment
            if whale_activity["dominant_side"] == "bullish":
                sentiment_emoji = "🟢"
                sentiment_text = "BULLISH (Киты покупают)"
                interpretation = """
    ✅ Киты активно покупают
    • Сильный спрос от крупных игроков
    • Возможен рост цены в краткосрочной перспективе
    • Следите за уровнями поддержки"""
            elif whale_activity["dominant_side"] == "bearish":
                sentiment_emoji = "🔴"
                sentiment_text = "BEARISH (Киты продают)"
                interpretation = """
    ❌ Киты активно продают
    • Сильное предложение от крупных игроков
    • Возможно снижение цены в краткосрочной перспективе
    • Следите за уровнями сопротивления"""
            else:
                sentiment_emoji = "⚪"
                sentiment_text = "NEUTRAL (Баланс)"
                interpretation = """
    ⚪ Нейтральная активность
    • Баланс между покупками и продажами
    • Рынок в состоянии равновесия
    • Ожидайте пробоя в любую сторону"""

            message = f"""🐋 *WHALE ACTIVITY:* {symbol}

    📊 *ОБЗОР* (Последние 5 минут)
    ├─ Крупных сделок: *{whale_activity['trades']}*
    ├─ Порог: >$100,000 за сделку
    └─ Sentiment: {sentiment_emoji} *{sentiment_text}*

    💰 *ОБЪЁМЫ*
    ├─ Buy Volume: *${buy_vol:,.2f}*
    ├─ Sell Volume: *${sell_vol:,.2f}*
    ├─ Net Volume: *${net:+,.2f}*
    └─ Total: *${total_vol:,.2f}*

    📊 *ДАВЛЕНИЕ*
    ├─ Buy Pressure: *{buy_pressure:.1f}%* {"🟢" if buy_pressure > 60 else "⚪"}
    └─ Sell Pressure: *{sell_pressure:.1f}%* {"🔴" if sell_pressure > 60 else "⚪"}

    💡 *ИНТЕРПРЕТАЦИЯ*
    {interpretation}

    ⏱️ Окно: Последние 5 минут
    🔄 Обновите: /whale {symbol}"""

            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)

            logger.info(f"✅ Whale activity для {symbol} отправлен")

        except Exception as e:
            logger.error(f"❌ Ошибка cmd_whale: {e}", exc_info=True)
            await update.message.reply_text(
                f"❌ Ошибка при получении whale activity: {str(e)}",
                parse_mode=ParseMode.MARKDOWN,
            )

    async def notify_new_signal(self, signal: Dict):
        """Уведомление о новом сигнале"""
        if not self.auto_signals:
            return

        try:
            emoji = "🟢" if signal.get("direction") == "LONG" else "🔴"
            is_risky = signal.get("quality_score", 100) < 60

            if is_risky:
                await self.notify_risky_entry(signal)
            else:
                text = (
                    f"{emoji} *НОВЫЙ СИГНАЛ #{signal.get('id', 0)}*\n\n"
                    f"🔸 *{signal.get('symbol', 'N/A')}* {signal.get('direction', 'LONG')}\n"
                    f"💰 *Entry:* ${signal.get('entry_price', 0):,.2f}\n"
                    f"🎯 *TP1:* ${signal.get('tp1', 0):,.2f}\n"
                    f"🎯 *TP2:* ${signal.get('tp2', 0):,.2f}\n"
                    f"🎯 *TP3:* ${signal.get('tp3', 0):,.2f}\n"
                    f"🛑 *SL:* ${signal.get('stop_loss', 0):,.2f}\n"
                    f"📊 *RR:* {signal.get('risk_reward', 0):.2f}\n"
                    f"⭐ *Качество:* {signal.get('quality_score', 0):.1f}/100\n"
                    f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )

                await self.send_message(text)

            logger.info(f"✅ Отправлено уведомление о сигнале #{signal.get('id', 0)}")
        except Exception as e:
            logger.error(f"❌ Ошибка отправки уведомления: {e}")

    async def notify_tp1_reached(self, trade: Dict):
        """TP1 достигнут"""
        try:
            emoji = "🎯" if trade.get("direction") == "LONG" else "🔻"
            text = (
                f"{emoji} *TP1 ДОСТИГНУТ #{trade.get('id', 0)}*\n\n"
                f"🔸 *{trade.get('symbol', 'N/A')}* {trade.get('direction', 'LONG')}\n"
                f"💰 *Entry:* ${trade.get('entry_price', 0):,.2f}\n"
                f"🎯 *TP1:* ${trade.get('tp1', 0):,.2f}\n"
                f"🎯 *TP2:* ${trade.get('tp2', 0):,.2f}\n"
                f"🎯 *TP3:* ${trade.get('tp3', 0):,.2f}\n"
                f"📈 *P&L:* +{trade.get('profit_percent', 0):.2f}%\n\n"
                f"✅ *ДЕЙСТВИЕ:*\n"
                f"• Зафиксируй *25% позиции*\n"
                f"• Переведи стоп в *безубыток*\n"
                f"• Остаток держим до TP2"
            )

            await self.send_message(text)
            logger.info(f"✅ TP1 уведомление для #{trade.get('id', 0)}")
        except Exception as e:
            logger.error(f"❌ Ошибка TP1 уведомления: {e}")

    async def notify_tp2_reached(self, trade: Dict):
        """TP2 достигнут"""
        try:
            emoji = "🎯🎯" if trade.get("direction") == "LONG" else "🔻🔻"
            text = (
                f"{emoji} *TP2 ДОСТИГНУТ #{trade.get('id', 0)}*\n\n"
                f"🔸 *{trade.get('symbol', 'N/A')}* {trade.get('direction', 'LONG')}\n"
                f"💰 *Entry:* ${trade.get('entry_price', 0):,.2f}\n"
                f"🎯 *TP1:* ${trade.get('tp1', 0):,.2f} ✅\n"
                f"🎯 *TP2:* ${trade.get('tp2', 0):,.2f}\n"
                f"🎯 *TP3:* ${trade.get('tp3', 0):,.2f}\n"
                f"📈 *P&L:* +{trade.get('profit_percent', 0):.2f}%\n\n"
                f"✅ *ДЕЙСТВИЕ:*\n"
                f"• Зафиксируй *50% позиции*\n"
                f"• Стоп уже в безубытке\n"
                f"• Остаток держим до TP3"
            )

            await self.send_message(text)
            logger.info(f"✅ TP2 уведомление для #{trade.get('id', 0)}")
        except Exception as e:
            logger.error(f"❌ Ошибка TP2 уведомления: {e}")

    async def notify_tp3_reached(self, trade: Dict):
        """TP3 достигнут"""
        try:
            emoji = "🎯🎯🎯" if trade.get("direction") == "LONG" else "🔻🔻🔻"
            text = (
                f"{emoji} *TP3 ДОСТИГНУТ #{trade.get('id', 0)}*\n\n"
                f"🔸 *{trade.get('symbol', 'N/A')}* {trade.get('direction', 'LONG')}\n"
                f"💰 *Entry:* ${trade.get('entry_price', 0):,.2f}\n"
                f"🎯 *TP3:* ${trade.get('tp3', 0):,.2f}\n"
                f"📈 *P&L:* +{trade.get('profit_percent', 0):.2f}%\n\n"
                f"✅ *ДЕЙСТВИЕ:*\n"
                f"• Трейлим остаток 25%\n"
                f"• ИЛИ фиксируем полностью\n"
                f"• Сделка успешно завершена! 🎉"
            )

            await self.send_message(text)
            logger.info(f"✅ TP3 уведомление для #{trade.get('id', 0)}")
        except Exception as e:
            logger.error(f"❌ Ошибка TP3 уведомления: {e}")

    async def notify_risky_entry(self, trade: Dict):
        """Risky Entry - повышенный риск"""
        try:
            text = (
                f"⚠️ *RISKY ENTRY #{trade.get('id', 0)}*\n\n"
                f"🔸 *{trade.get('symbol', 'N/A')}* {trade.get('direction', 'LONG')}\n"
                f"💰 *Entry:* ${trade.get('entry_price', 0):,.2f}\n"
                f"🎯 *TP1:* ${trade.get('tp1', 0):,.2f}\n"
                f"🎯 *TP2:* ${trade.get('tp2', 0):,.2f}\n"
                f"🎯 *TP3:* ${trade.get('tp3', 0):,.2f}\n"
                f"🛑 *SL:* ${trade.get('stop_loss', 0):,.2f}\n"
                f"⭐ *Качество:* {trade.get('quality_score', 0):.1f}/100\n\n"
                f"⚠️ *ВНИМАНИЕ:*\n"
                f"• Повышенный риск!\n"
                f"• Фиксируй *50% на TP1*\n"
                f"• Используй узкий стоп\n"
                f"• Будь готов к выходу"
            )

            await self.send_message(text)
            logger.info(f"⚠️ Risky Entry для #{trade.get('id', 0)}")
        except Exception as e:
            logger.error(f"❌ Ошибка Risky Entry: {e}")

    async def notify_stop_loss_hit(self, trade: Dict):
        """Стоп-лосс активирован"""
        try:
            text = (
                f"🛑 *СТОП АКТИВИРОВАН #{trade.get('id', 0)}*\n\n"
                f"🔸 *{trade.get('symbol', 'N/A')}* {trade.get('direction', 'LONG')}\n"
                f"💰 *Entry:* ${trade.get('entry_price', 0):,.2f}\n"
                f"🛑 *Stop Loss:* ${trade.get('stop_loss', 0):,.2f}\n"
                f"📉 *P&L:* {trade.get('profit_percent', 0):.2f}%\n\n"
                f"❌ *Сделка закрыта.*\n"
                f"Анализируем причины и ждём новых возможностей."
            )

            await self.send_message(text)
            logger.info(f"🛑 Stop Loss для #{trade.get('id', 0)}")
        except Exception as e:
            logger.error(f"❌ Ошибка Stop Loss: {e}")

    async def notify_breakeven_moved(self, trade: Dict):
        """Стоп переведён в безубыток"""
        try:
            text = (
                f"🔒 *СТОП В БЕЗУБЫТОК #{trade.get('id', 0)}*\n\n"
                f"🔸 *{trade.get('symbol', 'N/A')}* {trade.get('direction', 'LONG')}\n"
                f"💰 *Entry:* ${trade.get('entry_price', 0):,.2f}\n"
                f"🔒 *Новый стоп:* ${trade.get('entry_price', 0):,.2f}\n\n"
                f"✅ Позиция защищена!\n"
                f"Теперь можем держать без риска."
            )

            await self.send_message(text)
            logger.info(f"🔒 Breakeven для #{trade.get('id', 0)}")
        except Exception as e:
            logger.error(f"❌ Ошибка Breakeven: {e}")

    async def notify_trailing_started(self, trade: Dict):
        """Начат трейлинг стоп"""
        try:
            text = (
                f"🎯 *ТРЕЙЛИНГ ЗАПУЩЕН #{trade.get('id', 0)}*\n\n"
                f"🔸 *{trade.get('symbol', 'N/A')}* {trade.get('direction', 'LONG')}\n"
                f"💰 *Текущая цена:* ${trade.get('current_price', 0):,.2f}\n"
                f"📈 *P&L:* +{trade.get('profit_percent', 0):.2f}%\n\n"
                f"🎯 *Трейлим остаток позиции*\n"
                f"Стоп подтягивается автоматически"
            )

            await self.send_message(text)
            logger.info(f"🎯 Trailing для #{trade.get('id', 0)}")
        except Exception as e:
            logger.error(f"❌ Ошибка Trailing: {e}")

    async def cmd_scenario(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показать текущий сценарий ММ и фазу рынка (real-time)"""
        try:
            args = context.args
            if not args:
                available = "BTCUSDT, ETHUSDT, SOLUSDT"  # Хардкод списка пар
                await update.message.reply_text(
                    f"❌ Укажите символ!\n\nПример: /scenario BTCUSDT\n\nДоступные: {available}"
                )
                return

            symbol = args[0].upper()
            if symbol not in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
                available = "BTCUSDT, ETHUSDT, SOLUSDT"

                await update.message.reply_text(
                    f"❌ Символ {symbol} не найден!\n\nДоступные: {available}"
                )
                return

            await update.message.reply_text(f"📊 Анализ сценария для {symbol}...")

            # ✅ ШАГ 1: Получаем текущую цену
            ticker = await self.bot_instance.bybit_connector.get_ticker(symbol)
            if not ticker:
                await update.message.reply_text(
                    f"❌ Не удалось получить данные для {symbol}"
                )
                return

            price = float(ticker.get("lastPrice", 0))
            logger.debug(f"cmd_scenario: получен ticker для {symbol}, price=${price}")

            # ✅ ШАГ 2: Вычисляем CVD из WebSocket данных
            cvd_pct = 0.0
            if (
                hasattr(self.bot_instance, "trade_data")
                and symbol in self.bot_instance.trade_data
            ):
                trade_info = self.bot_instance.trade_data[symbol]
                buy_vol = trade_info.get("buy_volume", 0)
                sell_vol = trade_info.get("sell_volume", 0)
                total_vol = buy_vol + sell_vol
                if total_vol > 0:
                    cvd_pct = ((buy_vol - sell_vol) / total_vol) * 100
            logger.debug(f"cmd_scenario: CVD для {symbol} = {cvd_pct:.2f}%")

            # ✅ ШАГ 3: Вычисляем Volume multiplier
            volume_24h = float(ticker.get("turnover24h", 0))
            volume_multiplier = volume_24h / 1_000_000 if volume_24h > 0 else 1.0
            logger.debug(
                f"cmd_scenario: Volume для {symbol} = {volume_multiplier:.1f}x"
            )

            # ✅ ШАГ 4: Получаем Funding & L/S Ratio
            funding_rate = 0.0
            ls_ratio = 0.0
            try:
                funding_data = await self.bot_instance.bybit_connector.get_funding_rate(
                    symbol
                )
                if funding_data:
                    funding_rate = float(funding_data.get("fundingRate", 0)) * 100

                ls_data = await self.bot_instance.bybit_connector.get_long_short_ratio(
                    symbol
                )
                if ls_data:
                    ls_ratio = float(ls_data.get("buyRatio", 0))
            except Exception as e:
                logger.debug(
                    f"cmd_scenario: ошибка получения funding/ls для {symbol}: {e}"
                )

            logger.debug(
                f"cmd_scenario: Funding={funding_rate:.3f}%, L/S={ls_ratio:.2f}"
            )

            # ✅ ШАГ 5: Получаем Multi-Timeframe данные
            mtf_data = {}
            aligned_count = 0
            agreement = 0.0

            try:
                if hasattr(self.bot_instance, "mtf_filter"):
                    logger.debug(f"🔍 cmd_scenario: Запрашиваем MTF для {symbol}...")
                    mtf_result = self.bot_instance.mtf_filter.validate(symbol, "LONG")
                    logger.debug(f"✅ cmd_scenario: MTF результат = {mtf_result}")

                    if mtf_result and isinstance(mtf_result, dict):
                        mtf_data = mtf_result.get("trends", mtf_data)
                        aligned_count = mtf_result.get("aligned_count", 0)
                        agreement = mtf_result.get("agreement", 0.0) * 100
                else:
                    logger.warning("⚠️ MTF Filter недоступен!")
                    # ✅ ИНИЦИАЛИЗИРУЕМ ДЕФОЛТНЫМИ ЗНАЧЕНИЯМИ:
                    mtf_data = {
                        "1h": {"direction": "UNKNOWN", "strength": 0.0},
                        "4h": {"direction": "UNKNOWN", "strength": 0.0},
                        "1d": {"direction": "UNKNOWN", "strength": 0.0},
                    }

            except Exception as e:
                logger.error(
                    f"❌ cmd_scenario: Ошибка MTF для {symbol}: {e}", exc_info=True
                )
                # ✅ ИНИЦИАЛИЗИРУЕМ ДЕФОЛТНЫМИ ЗНАЧЕНИЯМИ:
                mtf_data = {
                    "1h": {"direction": "UNKNOWN", "strength": 0.0},
                    "4h": {"direction": "UNKNOWN", "strength": 0.0},
                    "1d": {"direction": "UNKNOWN", "strength": 0.0},
                }

            # ✅ ШАГ 6: Определяем сценарий через scenario_matcher
            scenario_name = "Unknown"
            market_phase = "Unknown"
            wyckoff_phase = "Unknown"
            strategy = "Unknown"
            quality = 0.0
            confidence = 0.0

            try:
                if hasattr(self.bot_instance, "scenario_matcher"):
                    # ✅ ПРАВИЛЬНО: Подготавливаем ВСЕ параметры
                    # 1. Market Data
                    market_data = {
                        "price": price,
                        "volume_24h": volume_24h,
                        "funding_rate": funding_rate,
                        "ls_ratio": ls_ratio,
                        "cvd": cvd_pct,
                    }

                    # 2. Indicators (базовые значения)
                    indicators = {
                        "rsi": 50,  # TODO: получить реальный RSI
                        "macd": 0,  # TODO: получить реальный MACD
                        "trend": mtf_data.get("1h", {}).get("direction", "NEUTRAL"),
                    }

                    # 3. MTF Trends
                    mtf_trends = mtf_data

                    # 4. Volume Profile (пустой если нет данных)
                    volume_profile = {}

                    # 5. News Sentiment (нейтральный по умолчанию)
                    news_sentiment = "neutral"

                    # 6. Veto Checks (пустой)
                    veto_checks = {}

                    # ✅ ПРАВИЛЬНЫЙ ВЫЗОВ С 7 ПАРАМЕТРАМИ:
                    scenario_result = self.bot_instance.scenario_matcher.match_scenario(
                        symbol,  # 1. symbol
                        "spot",  # 2. scenario_type
                        market_data,  # 3. market_data
                        indicators,  # 4. indicators
                        mtf_trends,  # 5. mtf_trends
                        volume_profile,  # 6. volume_profile
                        news_sentiment,  # 7. news_sentiment
                        veto_checks,  # 8. veto_checks
                    )

                    if scenario_result:
                        scenario_name = scenario_result.get("pattern", "Unknown")
                        market_phase = scenario_result.get("market_phase", "Unknown")
                        wyckoff_phase = scenario_result.get("wyckoff_phase", "Unknown")
                        strategy = scenario_result.get("strategy", "Unknown")
                        quality = scenario_result.get("score", 0.0)
                        confidence = scenario_result.get("confidence", 0.0)
            except Exception as e:
                logger.debug(
                    f"cmd_scenario: ошибка определения сценария для {symbol}: {e}"
                )

            logger.debug(
                f"cmd_scenario: Сценарий для {symbol} = {scenario_name}, quality={quality:.1f}%"
            )

            # ✅ ШАГ 7: Формируем ответ
            # CVD эмодзи
            if abs(cvd_pct) < 0.2:
                cvd_emoji = "⚠️"
            elif cvd_pct > 10:
                cvd_emoji = "🔥"
            elif cvd_pct > 0:
                cvd_emoji = "✅"
            elif cvd_pct < -10:
                cvd_emoji = "❄️"
            else:
                cvd_emoji = "🔴"

            # Volume эмодзи
            vol_emoji = "✅" if volume_multiplier > 1.5 else "⚠️"

            # Funding эмодзи
            if abs(funding_rate) < 0.005:
                funding_emoji = "⚪"
            elif funding_rate > 0.01:
                funding_emoji = "🟢"
            elif funding_rate < -0.01:
                funding_emoji = "🔴"
            else:
                funding_emoji = "⚪"

            # L/S Ratio эмодзи
            if ls_ratio > 1.2:
                ls_emoji = "🟢"
            elif ls_ratio < 0.8:
                ls_emoji = "🔴"
            else:
                ls_emoji = "⚪"

            # MTF эмодзи
            mtf_trend_emoji = {"UP": "📈", "DOWN": "📉", "NEUTRAL": "↔️", "UNKNOWN": "↔️"}

            # Рекомендация
            if quality >= 70 and aligned_count >= 2:
                recommendation = "Сильный сигнал - рассмотрите вход"
            elif quality >= 50:
                recommendation = "Умеренный сигнал - ждите подтверждения"
            else:
                recommendation = "Ожидайте подтверждения"

            message = f"""📊 СЦЕНАРИЙ ДЛЯ {symbol}

    🎯 Текущий сценарий: {scenario_name}
    📈 Фаза рынка: {market_phase} ({confidence:.0f}% conf)
    🏛️ Фаза Wyckoff: {wyckoff_phase}
    ⚡ Стратегия: {strategy}
    💪 Качество: {quality:.1f}%

    🔍 Условия:
    ├─ CVD: {cvd_pct:+.1f}% {cvd_emoji}
    ├─ Volume: {volume_multiplier:.1f}x {vol_emoji}
    ├─ Funding: {funding_rate:+.3f}% {funding_emoji}
    ├─ L/S Ratio: {ls_ratio:.2f} {ls_emoji}
    └─ MTF: {aligned_count}/3 aligned ({agreement:.0f}%)

    🎯 Multi-Timeframe:
    ├─ 1H: {mtf_data.get('1h', {}).get('direction', 'UNKNOWN')} {mtf_trend_emoji.get(mtf_data.get('1h', {}).get('direction', 'UNKNOWN'), '↔️')}
    ├─ 4H: {mtf_data.get('4h', {}).get('direction', 'UNKNOWN')} {mtf_trend_emoji.get(mtf_data.get('4h', {}).get('direction', 'UNKNOWN'), '↔️')}
    └─ 1D: {mtf_data.get('1d', {}).get('direction', 'UNKNOWN')} {mtf_trend_emoji.get(mtf_data.get('1d', {}).get('direction', 'UNKNOWN'), '↔️')}

    💡 Рекомендация: {recommendation}

    ⏱️ Обновлено: {datetime.now().strftime('%H:%M:%S')}"""

            await update.message.reply_text(message)
            logger.debug(f"cmd_scenario: {symbol} - успешно отправлено")

        except Exception as e:
            logger.error(f"Ошибка в cmd_scenario: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка: {str(e)}")
