#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liquidity Handler
Telegram command handler for /liquidity
"""

import asyncio
from typing import List
from telegram import Update
from telegram.ext import ContextTypes
from config.settings import logger


class LiquidityHandler:
    """Handler for /liquidity command"""

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.default_symbol = "BTCUSDT"
        logger.info("✅ LiquidityHandler инициализирован")

    async def cmd_liquidity(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """
        /liquidity — Liquidity analysis for BTCUSDT
        /liquidity SYMBOL — Liquidity analysis for specific symbol
        """
        try:
            user = update.effective_user.username or "Unknown"
            logger.info(f"💧 /liquidity от @{user}")

            # Определяем символ
            if context.args and len(context.args) >= 1:
                symbol = context.args[0].upper()
                if not symbol.endswith("USDT"):
                    symbol = f"{symbol}USDT"
            else:
                symbol = self.default_symbol

            # Loading message
            loading = await update.message.reply_text(
                f"💧 Анализирую ликвидность {symbol}..."
            )

            # Analyze liquidity
            result = await self.bot.liquidity_depth_analyzer.analyze_liquidity(symbol)

            # Format output
            output = self.bot.liquidity_depth_analyzer.format_liquidity_analysis(result)

            # Send result
            await loading.delete()
            await update.message.reply_text(output, parse_mode=None)

        except Exception as e:
            logger.error(f"❌ /liquidity error: {e}", exc_info=True)
            await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")
