#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dashboard Helpers - вспомогательные функции для форматирования дашбордов
"""

from typing import Dict, Optional
from datetime import datetime


class DashboardFormatter:
    """Форматирование дашбордов для Telegram"""

    @staticmethod
    def format_price(price: float, decimals: int = 2) -> str:
        """Форматирует цену с разделителями тысяч"""
        return f"${price:,.{decimals}f}"

    @staticmethod
    def format_percentage(
        value: float, decimals: int = 2, show_sign: bool = True
    ) -> str:
        """Форматирует процент с знаком"""
        sign = "+" if value > 0 and show_sign else ""
        return f"{sign}{value:.{decimals}f}%"

    @staticmethod
    def format_volume(volume: float) -> str:
        """Форматирует объём (B/M/K)"""
        if volume >= 1_000_000_000:
            return f"${volume / 1_000_000_000:.2f}B"
        elif volume >= 1_000_000:
            return f"${volume / 1_000_000:.2f}M"
        elif volume >= 1_000:
            return f"${volume / 1_000:.2f}K"
        else:
            return f"${volume:.2f}"

    @staticmethod
    def get_trend_emoji(trend: str) -> str:
        """Получить emoji для тренда"""
        if not trend:
            return "⚪"
        trend = trend.upper()
        if trend in ["UP", "BULLISH", "LONG"]:
            return "🟢"
        elif trend in ["DOWN", "BEARISH", "SHORT"]:
            return "🔴"
        else:
            return "⚪"

    @staticmethod
    def get_cvd_emoji(cvd: float) -> str:
        """Получить emoji для CVD"""
        if cvd >= 5:
            return "🟢 Strong BUY"
        elif cvd >= 1:
            return "🟢 BUY"
        elif cvd <= -5:
            return "🔴 Strong SELL"
        elif cvd <= -1:
            return "🔴 SELL"
        else:
            return "⚪ Neutral"

    @staticmethod
    def get_funding_emoji(funding: float) -> str:
        """Получить emoji для Funding Rate"""
        if funding >= 0.05:
            return "🔥 Very Bullish"
        elif funding >= 0.01:
            return "🟢 Bullish"
        elif funding <= -0.05:
            return "❄️ Very Bearish"
        elif funding <= -0.01:
            return "🔴 Bearish"
        else:
            return "⚪ Neutral"

    @staticmethod
    def get_ls_ratio_emoji(ratio: float) -> str:
        """Получить emoji для Long/Short Ratio"""
        if ratio >= 2.0:
            return "🔥 Very Bullish"
        elif ratio >= 1.5:
            return "🟢 Bullish"
        elif ratio <= 0.5:
            return "❄️ Very Bearish"
        elif ratio <= 0.75:
            return "🔴 Bearish"
        else:
            return "⚪ Neutral"

    @staticmethod
    def get_sentiment_emoji(sentiment: str) -> str:
        """Получить emoji для sentiment"""
        if not sentiment:
            return "⚪"
        sentiment = sentiment.lower()
        if sentiment in ["positive", "bullish"]:
            return "🟢"
        elif sentiment in ["negative", "bearish"]:
            return "🔴"
        else:
            return "⚪"

    @staticmethod
    def get_phase_emoji(phase: str) -> str:
        """Получить emoji для market phase"""
        if not phase:
            return "⚪"
        phase = phase.upper()
        emojis = {
            "ACCUMULATION": "🟢",
            "MARKUP": "🚀",
            "DISTRIBUTION": "🔴",
            "MARKDOWN": "📉",
            "RANGING": "↔️",
            "TRENDING": "📈",
            "VOLATILE": "⚡",
            "BREAKOUT": "💥",
            "SQUEEZE": "🎯",
        }
        return emojis.get(phase, "⚪")

    @staticmethod
    def get_regime_emoji(regime: str) -> str:
        """
        Получить emoji для Market Regime (КРИТЕРИЙ 2)

        Используется в market_dashboard.py для отображения
        Market Regime вместо старого Phase.

        Args:
            regime: Market Regime (UPPERCASE: TRENDING, RANGING, SQUEEZING, EXPANDING, NEUTRAL)

        Returns:
            Эмодзи для визуализации режима

        Examples:
            >>> get_regime_emoji("TRENDING")
            '📈'
            >>> get_regime_emoji("RANGING")
            '↔️'
            >>> get_regime_emoji("SQUEEZING")
            '🎯'
        """
        if not regime:
            return "⚪"

        regime_emojis = {
            "TRENDING": "📈",
            "RANGING": "↔️",
            "SQUEEZING": "🎯",
            "EXPANDING": "💥",
            "NEUTRAL": "⚪",
            "UNKNOWN": "❓",
        }
        return regime_emojis.get(regime.upper(), "⚪")

    @staticmethod
    def format_timestamp(timestamp: Optional[datetime] = None) -> str:
        """Форматирует timestamp"""
        if timestamp is None:
            timestamp = datetime.now()
        return timestamp.strftime("%H:%M:%S")

    @staticmethod
    def format_large_number(number: float) -> str:
        """Форматирует большие числа (1.2K, 3.5M, etc.)"""
        if number >= 1_000_000_000:
            return f"{number / 1_000_000_000:.1f}B"
        elif number >= 1_000_000:
            return f"{number / 1_000_000:.1f}M"
        elif number >= 1_000:
            return f"{number / 1_000:.1f}K"
        else:
            return f"{number:.0f}"


# Экспорт
__all__ = ["DashboardFormatter"]
