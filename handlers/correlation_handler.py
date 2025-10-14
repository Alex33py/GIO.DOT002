#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Correlation Handler
Telegram command handler for /correlation
"""

import asyncio
from typing import List
from telegram import Update
from telegram.ext import ContextTypes
from config.settings import logger


class CorrelationHandler:
    """Handler for /correlation command"""

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.default_symbols = [
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT",
            "XRPUSDT",
            "BNBUSDT",
        ]
        logger.info("✅ CorrelationHandler инициализирован")

    async def cmd_correlation(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        /correlation - Show correlation matrix for top assets
        /correlation BTC ETH SOL - Show correlation for specific assets
        """
        try:
            user = update.effective_user.username or "Unknown"
            logger.info(f"📊 /correlation от @{user}")

            # Определяем символы
            if context.args and len(context.args) >= 2:
                # User provided symbols
                symbols = []
                for arg in context.args:
                    symbol = arg.upper()
                    if not symbol.endswith("USDT"):
                        symbol = f"{symbol}USDT"
                    symbols.append(symbol)
            else:
                # Use default top 5 symbols
                symbols = self.default_symbols

            # Loading message
            loading = await update.message.reply_text(
                f"🔍 Вычисляю корреляции для {len(symbols)} активов..."
            )

            # Calculate correlation
            result = await self.bot.correlation_analyzer.calculate_correlation_matrix(
                symbols, period="24h"
            )

            # Format output
            output = self.bot.correlation_analyzer.format_correlation_matrix(result)

            # Send result
            await loading.delete()
            await update.message.reply_text(output, parse_mode=None)

        except Exception as e:
            logger.error(f"❌ /correlation error: {e}", exc_info=True)
            await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")

    async def cmd_correlation_pair(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        /corrpair BTCUSDT ETHUSDT - Show correlation between two specific assets
        """
        try:
            if not context.args or len(context.args) < 2:
                await update.message.reply_text(
                    "⚠️ Использование: /corrpair SYMBOL1 SYMBOL2\n"
                    "Пример: /corrpair BTC ETH"
                )
                return

            user = update.effective_user.username or "Unknown"
            logger.info(f"📊 /corrpair от @{user}")

            # Parse symbols
            symbol1 = context.args[0].upper()
            symbol2 = context.args[1].upper()

            if not symbol1.endswith("USDT"):
                symbol1 = f"{symbol1}USDT"
            if not symbol2.endswith("USDT"):
                symbol2 = f"{symbol2}USDT"

            # Loading message
            loading = await update.message.reply_text(
                f"🔍 Вычисляю корреляцию {symbol1} и {symbol2}..."
            )

            # Calculate correlation for pair
            result = await self.bot.correlation_analyzer.calculate_correlation_matrix(
                [symbol1, symbol2], period="24h"
            )

            # Format pair-specific output
            matrix = result["matrix"]
            corr_value = matrix[0][1] if len(matrix) > 1 else 0

            # Interpretation
            if corr_value > 0.8:
                strength = "ОЧЕНЬ СИЛЬНАЯ"
                emoji = "🔥"
            elif corr_value > 0.6:
                strength = "СИЛЬНАЯ"
                emoji = "🟢"
            elif corr_value > 0.4:
                strength = "УМЕРЕННАЯ"
                emoji = "🟡"
            elif corr_value > 0.2:
                strength = "СЛАБАЯ"
                emoji = "⚪"
            else:
                strength = "ОЧЕНЬ СЛАБАЯ"
                emoji = "🔴"

            output = (
                f"📊 CORRELATION: {symbol1.replace('USDT', '')} ↔ {symbol2.replace('USDT', '')}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"{emoji} Корреляция: {corr_value:.2f}\n"
                f"Сила: {strength}\n\n"
                f"💡 Интерпретация:\n"
            )

            if corr_value > 0.7:
                output += "• Активы движутся синхронно\n"
                output += "• Высокая предсказуемость\n"
                output += "• Диверсификация ограничена"
            elif corr_value > 0.4:
                output += "• Умеренная связь движений\n"
                output += "• Средняя предсказуемость\n"
                output += "• Частичная диверсификация"
            else:
                output += "• Слабая связь или независимость\n"
                output += "• Хорошая диверсификация\n"
                output += "• Возможны расхождения"

            await loading.delete()
            await update.message.reply_text(output, parse_mode=None)

        except Exception as e:
            logger.error(f"❌ /corrpair error: {e}", exc_info=True)
            await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")
