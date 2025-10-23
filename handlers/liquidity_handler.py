#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liquidity Handler
Telegram command handler for /liquidity with enhanced analysis
"""
import asyncio
from typing import List
from telegram import Update
from telegram.ext import ContextTypes
from config.settings import logger


class LiquidityHandler:
    """Handler for /liquidity command with enhanced analysis"""

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.default_symbol = "BTCUSDT"
        logger.info("✅ LiquidityHandler инициализирован")

    async def cmd_liquidity(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /liquidity — Enhanced liquidity analysis for BTCUSDT
        /liquidity SYMBOL — Enhanced liquidity analysis for specific symbol
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
                f"💧 Analyzing liquidity depth for {symbol}..."
            )

            # ✅ ИСПОЛЬЗУЕМ ENHANCED ANALYZER, если доступен
            if hasattr(self.bot, "enhanced_liquidity_analyzer"):
                try:
                    # Проводим расширенный анализ
                    analysis = await self.bot.enhanced_liquidity_analyzer.analyze(
                        symbol
                    )

                    # Форматируем расширенный вывод
                    output = self._format_enhanced_analysis(symbol, analysis)

                    # ✅ ДОБАВЛЯЕМ AI ИНТЕРПРЕТАЦИЮ (ИЗМЕНЕНИЕ 1)
                    output += "\n\n * AI INTERPRETATION *\n"
                    output += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

                    ai_text = await self._generate_ai_interpretation(analysis, symbol)
                    if not ai_text:
                        ai_text = self._generate_rule_based_interpretation(
                            analysis, symbol
                        )

                    output += ai_text

                except Exception as e:
                    logger.error(f"Enhanced analyzer error: {e}", exc_info=True)
                    # Fallback на старый анализатор
                    output = await self._fallback_analysis(symbol)

            # ❌ Если enhanced analyzer недоступен, используем старый
            elif hasattr(self.bot, "liquidity_depth_analyzer"):
                output = await self._fallback_analysis(symbol)

            else:
                await loading.delete()
                await update.message.reply_text("❌ Liquidity analyzer not available")
                return

            # Send result
            await loading.delete()
            await update.message.reply_text(output, parse_mode="Markdown")

        except Exception as e:
            logger.error(f"❌ /liquidity error: {e}", exc_info=True)
            await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")

    async def _fallback_analysis(self, symbol: str) -> str:
        """Fallback на старый анализатор"""
        result = await self.bot.liquidity_depth_analyzer.analyze_liquidity(symbol)
        return self.bot.liquidity_depth_analyzer.format_liquidity_analysis(result)

    def _format_enhanced_analysis(self, symbol: str, analysis) -> str:
        """Форматирование расширенного анализа ликвидности"""

        # 1. Header
        message = f"💧 *LIQUIDITY DEPTH ANALYSIS — {symbol.replace('USDT', '')}*\n"
        message += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

        # 2. Current Price
        message += f"💰 *Current Price:* ${analysis.current_price:,.2f}\n\n"

        # 3. Orderbook Summary
        total_volume = analysis.total_bid + analysis.total_ask
        bid_pct = (analysis.total_bid / total_volume) * 100 if total_volume > 0 else 0
        ask_pct = (analysis.total_ask / total_volume) * 100 if total_volume > 0 else 0

        message += "📊 *ORDERBOOK SUMMARY*\n"
        message += f"├─ Total BID: ${analysis.total_bid/1e6:.1f}M ({bid_pct:.1f}%)\n"
        message += f"├─ Total ASK: ${analysis.total_ask/1e6:.1f}M ({ask_pct:.1f}%)\n"

        imbalance_emoji = "🟢" if analysis.imbalance > 0 else "🔴"
        pressure = "BUY" if analysis.imbalance > 0 else "SELL"
        message += f"└─ Imbalance: ${analysis.imbalance/1e6:+.1f}M ({pressure} pressure) {imbalance_emoji}\n\n"

        # 4. Spread Analysis
        spread_status = (
            "🟢 TIGHT"
            if analysis.spread_pct < 0.05
            else "🟡 NORMAL" if analysis.spread_pct < 0.15 else "🔴 WIDE"
        )

        message += "💱 *SPREAD ANALYSIS*\n"
        message += f"├─ Best BID: ${analysis.best_bid:,.2f}\n"
        message += f"├─ Best ASK: ${analysis.best_ask:,.2f}\n"
        message += f"├─ Spread: ${analysis.spread:.2f} ({analysis.spread_pct:.4f}%)\n"
        message += f"└─ Status: {spread_status}\n\n"

        # 5. Key Levels
        message += "🎯 *KEY LEVELS*\n"

        if analysis.resistance_zones:
            message += "├─ *RESISTANCE ZONES:*\n"
            for i, zone in enumerate(analysis.resistance_zones[:2]):
                prefix = "│  ├─" if i == 0 else "│  └─"
                message += (
                    f"{prefix} ${zone['price_low']:,.0f} - ${zone['price_high']:,.0f} "
                )
                message += (
                    f"({zone['strength']} wall: ${zone['volume_usd']/1e6:.1f}M)\n"
                )

        if analysis.support_zones:
            message += "├─ *SUPPORT ZONES:*\n"
            for i, zone in enumerate(analysis.support_zones[:2]):
                prefix = "│  ├─" if i == 0 else "│  └─"
                message += (
                    f"{prefix} ${zone['price_low']:,.0f} - ${zone['price_high']:,.0f} "
                )
                message += f"({zone['strength']}: ${zone['volume_usd']/1e6:.1f}M)\n"

        message += f"└─ POC (Point of Control): ${analysis.poc_price:,.0f}\n\n"

        # 6. Slippage Estimate
        message += "⚡ *SLIPPAGE ESTIMATE*\n"
        message += "*For BUY orders:*\n"
        for i, (size, slip) in enumerate(analysis.slippage_buy.items()):
            prefix = "├─" if i < len(analysis.slippage_buy) - 1 else "└─"
            if slip is None:
                message += f"{prefix} ${size/1000:.0f}K: ❌ Insufficient liquidity\n"
            else:
                emoji = "🟢" if slip < 0.1 else "🟡" if slip < 0.5 else "🔴"
                message += f"{prefix} ${size/1000:.0f}K: ~{slip:.2f}% {emoji}\n"

        message += "\n*For SELL orders:*\n"
        for i, (size, slip) in enumerate(analysis.slippage_sell.items()):
            prefix = "├─" if i < len(analysis.slippage_sell) - 1 else "└─"
            if slip is None:
                message += f"{prefix} ${size/1000:.0f}K: ❌ Insufficient liquidity\n"
            else:
                emoji = "🟢" if slip < 0.1 else "🟡" if slip < 0.5 else "🔴"
                message += f"{prefix} ${size/1000:.0f}K: ~{slip:.2f}% {emoji}\n"

        message += "\n"

        # 7. Risk Assessment
        message += "⚠️ *RISK ASSESSMENT*\n"
        message += f"├─ Liquidity Score: {analysis.liquidity_score:.1f}/10 ({analysis.market_depth_status})\n"
        message += f"├─ BID/ASK Ratio: {analysis.bid_ask_ratio:.2f}x "

        if analysis.bid_ask_ratio > 2.0:
            message += "(Extremely bullish)\n"
        elif analysis.bid_ask_ratio > 1.2:
            message += "(Bullish)\n"
        elif analysis.bid_ask_ratio < 0.5:
            message += "(Extremely bearish)\n"
        elif analysis.bid_ask_ratio < 0.8:
            message += "(Bearish)\n"
        else:
            message += "(Neutral)\n"

        message += f"└─ Market Depth: {analysis.market_depth_status}\n\n"

        # 8. Trading Signals
        message += "🎯 *TRADING SIGNALS*\n\n"

        # Long signal
        if analysis.long_signal["recommended"]:
            message += (
                f"*LONG (Buy):* ✅ ({analysis.long_signal['confidence']}% confidence)\n"
            )
            for reason in analysis.long_signal["reasons"]:
                message += f"  • {reason}\n"

            if analysis.long_signal.get("entry"):
                message += f"Entry: ${analysis.long_signal['entry']:,.2f}\n"
                message += f"Stop-Loss: ${analysis.long_signal['stop_loss']:,.2f} "

                sl_pct = (
                    analysis.long_signal["stop_loss"] / analysis.long_signal["entry"]
                    - 1
                ) * 100
                message += f"({sl_pct:.1f}%)\n"

                message += f"Target: ${analysis.long_signal['target']:,.2f} "

                target_pct = (
                    analysis.long_signal["target"] / analysis.long_signal["entry"] - 1
                ) * 100
                message += f"({target_pct:+.1f}%)\n"

                message += f"Risk/Reward: 1:{analysis.long_signal['risk_reward']:.1f}\n"

            message += "\n"
        else:
            message += f"*LONG (Buy):* ⚠️ Not recommended ({analysis.long_signal['confidence']}% confidence)\n\n"

        # Short signal
        if analysis.short_signal["recommended"]:
            message += f"*SHORT (Sell):* ✅ ({analysis.short_signal['confidence']}% confidence)\n"
            for reason in analysis.short_signal["reasons"]:
                message += f"  • {reason}\n"

            if analysis.short_signal.get("entry"):
                message += f"Entry: ${analysis.short_signal['entry']:,.2f}\n"
                message += f"Stop-Loss: ${analysis.short_signal['stop_loss']:,.2f} "

                sl_pct = (
                    analysis.short_signal["stop_loss"] / analysis.short_signal["entry"]
                    - 1
                ) * 100
                message += f"({sl_pct:+.1f}%)\n"

                message += f"Target: ${analysis.short_signal['target']:,.2f} "

                target_pct = (
                    analysis.short_signal["target"] / analysis.short_signal["entry"] - 1
                ) * 100
                message += f"({target_pct:.1f}%)\n"

                message += (
                    f"Risk/Reward: 1:{analysis.short_signal['risk_reward']:.1f}\n"
                )

            message += "\n"
        else:
            message += f"*SHORT (Sell):* ⚠️ Not recommended ({analysis.short_signal['confidence']}% confidence)\n\n"

        # 9. Historical Trends (если доступны)
        if hasattr(analysis, "avg_bid_6h") and analysis.avg_bid_6h:
            bid_change = (
                (analysis.total_bid - analysis.avg_bid_6h) / analysis.avg_bid_6h
            ) * 100
            ask_change = (
                (analysis.total_ask - analysis.avg_ask_6h) / analysis.avg_ask_6h
            ) * 100

            if analysis.avg_imbalance_6h != 0:
                imb_change = (
                    (analysis.imbalance - analysis.avg_imbalance_6h)
                    / abs(analysis.avg_imbalance_6h)
                ) * 100
            else:
                imb_change = 0

            message += "📈 *LIQUIDITY TRENDS (6h)*\n"
            message += f"├─ BID Volume: ${analysis.avg_bid_6h/1e6:.1f}M → ${analysis.total_bid/1e6:.1f}M "
            message += f"({'🟢' if bid_change > 0 else '🔴'} {bid_change:+.1f}%)\n"
            message += f"├─ ASK Volume: ${analysis.avg_ask_6h/1e6:.1f}M → ${analysis.total_ask/1e6:.1f}M "
            message += f"({'🟢' if ask_change > 0 else '🔴'} {ask_change:+.1f}%)\n"
            message += f"└─ Imbalance: ${analysis.avg_imbalance_6h/1e6:+.1f}M → ${analysis.imbalance/1e6:+.1f}M "
            message += f"({'🟢' if imb_change > 0 else '🔴'} {imb_change:+.1f}%)\n"

        return message

    async def _generate_ai_interpretation(self, analysis, symbol: str) -> str:
        """Генерация AI интерпретации через Gemini"""
        try:
            if not hasattr(self.bot, "telegram_handler") or not hasattr(
                self.bot.telegram_handler, "gemini_interpreter"
            ):
                return ""

            gemini = self.bot.telegram_handler.gemini_interpreter
            if not gemini:
                return ""

            prompt = f"""Проанализируй ликвидность для {symbol}:
Цена: ${analysis.current_price:.2f}
BID/ASK: {analysis.bid_ask_ratio:.2f}x
Дисбаланс: ${analysis.imbalance/1_000_000:.1f}M
Спред: {analysis.spread_pct:.4f}%
Оценка: {analysis.liquidity_score}/10

Long: {'✅' if analysis.long_signal['recommended'] else '⚠️'} ({analysis.long_signal['confidence']}%)
Short: {'✅' if analysis.short_signal['recommended'] else '⚠️'} ({analysis.short_signal['confidence']}%)

Предоставь 3-4 предложения на русском языке: 1) Настроение рынка, 2) Риски, 3) Рекомендация."""

            response = await gemini.generate_response(prompt)
            if response:
                lines = response.strip().split("\n")
                return "\n".join(f"{line}" for line in lines if line.strip())
            return ""
        except Exception as e:
            logger.error(f"AI interpretation error: {e}")
            return ""

    def _generate_rule_based_interpretation(self, analysis, symbol: str) -> str:
        """Rule-based AI интерпретация (fallback) - на русском языке"""

        # Настроение
        if analysis.bid_ask_ratio > 2.0:
            sentiment = "🟢 *Сильно бычий* - Мощное давление покупателей"
        elif analysis.bid_ask_ratio > 1.2:
            sentiment = "🟢 *Бычий* - Покупатели доминируют"
        elif analysis.bid_ask_ratio < 0.5:
            sentiment = "🔴 *Сильно медвежий* - Мощное давление продавцов"
        elif analysis.bid_ask_ratio < 0.8:
            sentiment = "🔴 *Медвежий* - Продавцы доминируют"
        else:
            sentiment = "🟡 *Нейтральный* - Сбалансированный рынок"

        # Риск
        if analysis.spread_pct > 0.2:
            risk = f"Широкий спред ({analysis.spread_pct:.2f}%) может повлиять на исполнение"
        elif abs(analysis.imbalance) > 1_000_000:
            side = "продаж" if analysis.imbalance < 0 else "покупок"
            risk = f"Сильное давление {side} (дисбаланс ${abs(analysis.imbalance)/1_000_000:.1f}M)"
        else:
            risk = "Стабильные рыночные условия"

        # Рекомендация
        if (
            analysis.long_signal["recommended"]
            and analysis.long_signal["confidence"] > 60
        ):
            rec = f"✅ *LONG* @ ${analysis.current_price:,.2f}, SL ${analysis.long_signal['stop_loss']:,.2f}"
        elif (
            analysis.short_signal["recommended"]
            and analysis.short_signal["confidence"] > 60
        ):
            rec = f"⚠️ *SHORT* @ ${analysis.current_price:,.2f}, SL ${analysis.short_signal['stop_loss']:,.2f}"
        else:
            rec = "⏸️ *Ожидать* более чётких сигналов"

        return f"""*Настроение:* {sentiment}
        *Риск:* {risk}
        *Действие:* {rec}"""
