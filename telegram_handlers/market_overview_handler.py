#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Market Overview Handler
Multi-Symbol Quick Scan Dashboard with Color Coding
"""

import asyncio
from datetime import datetime
from typing import Dict, List
from telegram import Update
from telegram.ext import ContextTypes
from config.settings import logger


class MarketOverviewHandler:
    """Multi-Symbol Overview Handler with Color Coding"""

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.default_symbols = [
            "BTCUSDT",
            "ETHUSDT",
            "SOLUSDT",
            "XRPUSDT",
            "BNBUSDT",
            "DOGEUSDT",
            "ADAUSDT",
            "AVAXUSDT",
        ]
        logger.info("✅ MarketOverviewHandler инициализирован")

    def get_price_emoji(self, price_change: float) -> str:
        """
        Возвращает emoji для изменения цены

        Args:
            price_change: Процент изменения цены

        Returns:
            Emoji строка (🟢, 🔴, ⚪)
        """
        if price_change > 0.5:
            return "🟢"
        elif price_change < -0.5:
            return "🔴"
        else:
            return "⚪"

    def get_phase_emoji(self, phase: str, confidence: float) -> str:
        """
        Возвращает emoji для фазы рынка

        Args:
            phase: BULLISH_EXPANSION, BEARISH_COMPRESSION, CONSOLIDATION
            confidence: Уверенность 0-100

        Returns:
            Emoji строка (🟢, 🔴, ⚪, 🟡)
        """
        if confidence < 60:
            return "🟡"  # Низкая уверенность

        if phase == "BULLISH_EXPANSION":
            return "🟢"
        elif phase == "BEARISH_COMPRESSION":
            return "🔴"
        else:  # CONSOLIDATION
            return "⚪"

    def format_phase_name(self, phase: str) -> str:
        """Форматирует название фазы для отображения"""
        phase_names = {
            "BULLISH_EXPANSION": "BULLISH EXP",
            "BEARISH_COMPRESSION": "BEARISH CMP",
            "CONSOLIDATION": "CONSOLIDATION",
        }
        return phase_names.get(phase, phase)

    async def cmd_overview(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /overview - Multi-Symbol Market Overview with Color Coding
        Показывает 8 активов с цветными индикаторами и фазами
        """
        try:
            user = update.effective_user.username or "Unknown"
            logger.info(f"📊 /overview от @{user}")

            # Loading сообщение
            loading = await update.message.reply_text(
                "🔍 Загружаю обзор рынка для 8 активов..."
            )

            # Собираем данные параллельно
            overview = await self.build_overview(self.default_symbols)

            # Отправляем overview
            await loading.delete()
            await update.message.reply_text(overview, parse_mode=None)

        except Exception as e:
            logger.error(f"❌ /overview error: {e}", exc_info=True)
            await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")

    async def build_overview(self, symbols: List[str]) -> str:
        """Построение multi-symbol overview с color coding"""
        try:
            lines = []
            lines.append("📊 GIO MARKET OVERVIEW — 8 Assets")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("")

            # Собираем данные параллельно
            tasks = [self.get_symbol_data(symbol) for symbol in symbols]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Формируем список с emoji
            for symbol, data in zip(symbols, results):
                if isinstance(data, Exception):
                    logger.error(f"Error for {symbol}: {data}")
                    continue

                if not data:
                    continue

                # Получаем emoji
                price_emoji = self.get_price_emoji(data["change"])
                phase_emoji = self.get_phase_emoji(data["phase"], data["confidence"])

                # Форматируем название фазы
                phase_name = self.format_phase_name(data["phase"])

                # Форматируем цену (убираем USDT)
                symbol_short = symbol.replace("USDT", "")

                # Форматируем строку с heat indicator
                line = (
                    f"{price_emoji} {symbol_short}: "
                    f"${data['price']:,.2f} ({data['change']:+.2f}%) | "
                    f"{phase_emoji} {phase_name} ({data['confidence']:.0f}%) | "  # ← ДОБАВИЛ " | " В КОНЦЕ
                    f"{data['heat_emoji']}"
                )

                lines.append(line)

            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"⏱️ Updated: {datetime.now().strftime('%H:%M:%S')}")
            lines.append("")

            # Легенда
            lines.append("📖 LEGEND:")
            lines.append("├─ 🟢 Bullish | 🔴 Bearish | ⚪ Neutral")
            lines.append("├─ 🟡 Uncertain (low confidence)")
            lines.append("└─ Use /gio SYMBOL for details")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"❌ build_overview error: {e}", exc_info=True)
            return f"⚠️ Ошибка построения обзора: {str(e)}"

    async def get_symbol_data(self, symbol: str) -> Dict:
        """Получение данных для одного символа включая market phase"""
        try:
            data = {}

            # 1. Price & Change
            ticker = await self.bot.bybit_connector.get_ticker(symbol)
            if ticker:
                data["price"] = float(ticker.get("lastPrice", 0))
                data["change"] = float(ticker.get("price24hPcnt", 0)) * 100
            else:
                return None

            # 2. Market Phase Detection
            try:
                # ИСПРАВЛЕНО: используем get_market_data вместо extract_features
                market_data = await self.bot.get_market_data(symbol)

                if market_data and hasattr(self.bot, "market_phase_detector"):
                    # Получаем Volume Profile
                    vp = market_data.get("volume_profile", {})

                    # Получаем OI данные
                    oi_data = await self.bot.bybit_connector.get_open_interest(symbol)
                    oi_change = oi_data.get("openInterestDelta", 0) if oi_data else 0

                    # Получаем Funding
                    funding_data = self.bot.bybit_connector.get_funding_rate(
                        symbol
                    )
                    funding_rate = (
                        funding_data.get("fundingRate", 0) if funding_data else 0
                    )

                    # Собираем features для phase detector
                    features = {
                        "price": data["price"],
                        "volume": market_data.get("volume", 0),
                        "volume_ma20": market_data.get("volume_ma20", 1),
                        "atr": market_data.get("atr", 1),
                        "poc": vp.get("poc", data["price"]),
                        "vah": vp.get("vah", data["price"] * 1.01),
                        "val": vp.get("val", data["price"] * 0.99),
                        "open_interest_delta_pct": oi_change,
                        "funding_rate_bp": funding_rate * 10000,
                        "price_change_pct": data["change"],
                    }

                    phase_info = self.bot.market_phase_detector.detect_phase(features)
                    data["phase"] = phase_info["phase"]
                    data["confidence"] = phase_info["confidence"]
                else:
                    # Fallback: определяем фазу по price change
                    if abs(data["change"]) < 1.0:
                        data["phase"] = "CONSOLIDATION"
                        data["confidence"] = 65.0
                    elif data["change"] > 1.0:
                        data["phase"] = "BULLISH_EXPANSION"
                        data["confidence"] = 70.0
                    else:
                        data["phase"] = "BEARISH_COMPRESSION"
                        data["confidence"] = 70.0

            except Exception as e:
                logger.warning(f"Phase detection failed for {symbol}: {e}")
                # Fallback: определяем фазу по price change
                if abs(data["change"]) < 1.0:
                    data["phase"] = "CONSOLIDATION"
                    data["confidence"] = 65.0
                elif data["change"] > 1.0:
                    data["phase"] = "BULLISH_EXPANSION"
                    data["confidence"] = 70.0
                else:
                    data["phase"] = "BEARISH_COMPRESSION"
                    data["confidence"] = 70.0

            # 3. Market Heat
            try:
                if hasattr(self.bot, "market_heat_indicator"):
                    features_for_heat = {
                        "price": data["price"],
                        "atr": 1.0,  # Default
                        "volume": 1000000,  # Default
                        "volume_ma20": 1000000,
                        "price_change_pct": data["change"],
                        "open_interest_delta_pct": 0,
                    }

                    heat_data = self.bot.market_heat_indicator.calculate_heat(
                        features_for_heat
                    )
                    data["heat_emoji"] = heat_data["heat_emoji"]
                    data["heat_score"] = heat_data["heat_score"]
                else:
                    data["heat_emoji"] = "⚪"
                    data["heat_score"] = 0
            except Exception as e:
                logger.warning(f"Heat calculation failed for {symbol}: {e}")
                data["heat_emoji"] = "⚪"
                data["heat_score"] = 0

            return data

        except Exception as e:
            logger.error(f"get_symbol_data error for {symbol}: {e}")
            return None
