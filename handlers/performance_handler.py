#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Performance Handler
Telegram command handler for signal performance analytics
"""

import asyncio
import sqlite3
from typing import List
from telegram import Update
from telegram.ext import ContextTypes
from config.settings import logger, DB_FILE


class PerformanceHandler:
    """Handler for signal performance commands"""

    def __init__(self, bot_instance):
        self.bot = bot_instance
        logger.info("✅ PerformanceHandler инициализирован")

    async def cmd_performance(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /performance — Overall performance statistics
        /performance 7 — Performance for last 7 days
        /performance 90 — Performance for last 90 days
        """
        try:
            user = update.effective_user.username or "Unknown"
            logger.info(f"📊 /performance от @{user}")

            # Определяем период (дни)
            days = 30  # По умолчанию 30 дней
            if context.args and len(context.args) >= 1:
                try:
                    days = int(context.args[0])
                    if days < 1 or days > 365:
                        days = 30
                except:
                    days = 30

            # Loading message
            loading = await update.message.reply_text(
                f"📊 Анализирую производительность за {days} дней..."
            )

            # Get performance stats
            stats = await self.bot.signal_performance_analyzer.get_performance_overview(
                days
            )

            # Format output
            output = self.bot.signal_performance_analyzer.format_performance_overview(
                stats
            )

            # Send result
            await loading.delete()
            await update.message.reply_text(output, parse_mode=None)

        except Exception as e:
            logger.error(f"❌ /performance error: {e}", exc_info=True)
            await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")

    async def cmd_bestsignals(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /bestsignals — Top 10 best performing signals
        """
        try:
            user = update.effective_user.username or "Unknown"
            logger.info(f"🏆 /bestsignals от @{user}")

            # Get top signals
            top_signals = await self._get_top_signals(limit=10, best=True)

            if not top_signals:
                await update.message.reply_text(
                    "📊 Пока нет закрытых сигналов для анализа"
                )
                return

            # Format output
            lines = ["🏆 TOP 10 BEST SIGNALS", "━━━━━━━━━━━━━━━━━━━━━━", ""]

            for i, signal in enumerate(top_signals, 1):
                symbol = signal["symbol"]
                roi = signal["roi"]
                direction = signal["direction"] or "UNKNOWN"
                entry_time = (
                    signal["entry_time"][:10] if signal["entry_time"] else "N/A"
                )

                emoji = (
                    "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
                )
                lines.append(
                    f"{emoji} {symbol} {direction}: {roi:+.2f}% ROI\n"
                    f"   📅 {entry_time}"
                )

            lines.append("")
            lines.append("💡 Используйте /performance для полной статистики")

            await update.message.reply_text("\n".join(lines), parse_mode=None)

        except Exception as e:
            logger.error(f"❌ /bestsignals error: {e}", exc_info=True)
            await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")

    async def cmd_worstsignals(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        /worstsignals — Top 10 worst performing signals
        """
        try:
            user = update.effective_user.username or "Unknown"
            logger.info(f"📉 /worstsignals от @{user}")

            # Get worst signals
            worst_signals = await self._get_top_signals(limit=10, best=False)

            if not worst_signals:
                await update.message.reply_text(
                    "📊 Пока нет закрытых сигналов для анализа"
                )
                return

            # Format output
            lines = ["📉 TOP 10 WORST SIGNALS", "━━━━━━━━━━━━━━━━━━━━━━", ""]

            for i, signal in enumerate(worst_signals, 1):
                symbol = signal["symbol"]
                roi = signal["roi"]
                direction = signal["direction"] or "UNKNOWN"
                entry_time = (
                    signal["entry_time"][:10] if signal["entry_time"] else "N/A"
                )

                lines.append(
                    f"{i}. {symbol} {direction}: {roi:+.2f}% ROI\n"
                    f"   📅 {entry_time}"
                )

            lines.append("")
            lines.append("💡 Используйте /performance для полной статистики")

            await update.message.reply_text("\n".join(lines), parse_mode=None)

        except Exception as e:
            logger.error(f"❌ /worstsignals error: {e}", exc_info=True)
            await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")

    async def _get_top_signals(self, limit: int = 10, best: bool = True) -> List[dict]:
        """
        Получить топ сигналов по ROI

        Args:
            limit: Количество сигналов
            best: True для лучших, False для худших

        Returns:
            Список сигналов [{symbol, roi, direction, entry_time}, ...]
        """
        try:
            conn = sqlite3.connect(DB_FILE)
            cursor = conn.cursor()

            # Сортировка: DESC для лучших, ASC для худших
            order = "DESC" if best else "ASC"

            cursor.execute(
                f"""
                SELECT symbol, roi, direction, entry_time
                FROM signals
                WHERE status = 'closed'
                  AND roi IS NOT NULL
                ORDER BY roi {order}
                LIMIT ?
            """,
                (limit,),
            )

            rows = cursor.fetchall()
            conn.close()

            if not rows:
                return []

            return [
                {
                    "symbol": row[0],
                    "roi": row[1],
                    "direction": row[2],
                    "entry_time": row[3],
                }
                for row in rows
            ]

        except Exception as e:
            logger.error(f"_get_top_signals error: {e}")
            return []
