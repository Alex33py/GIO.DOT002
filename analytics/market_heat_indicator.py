#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Market Heat Indicator
Measures market activity and volatility
"""

from typing import Dict, Any
from config.settings import logger


class MarketHeatIndicator:
    """
    Market Heat Indicator - measures market activity/volatility

    Components:
    - Volatility (ATR vs price)
    - Volume (current vs MA)
    - Price Movement (24h change)
    - OI Change (momentum)
    """

    def __init__(self):
        logger.info("✅ MarketHeatIndicator инициализирован")

    def calculate_heat(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate market heat score (0-100)

        Args:
            features: Market data features

        Returns:
            {
                "heat_score": float (0-100),
                "heat_level": str (EXTREME, HOT, WARM, COOL, COLD),
                "heat_emoji": str (🔥🔥🔥, 🔥🔥, 🔥, ⚪, ❄️),
                "components": {
                    "volatility": float,
                    "volume": float,
                    "price_movement": float,
                    "oi_change": float
                }
            }
        """
        try:
            # Extract features
            price = features.get("price", 0)
            atr = features.get("atr", 0)
            volume = features.get("volume", 0)
            volume_ma = features.get("volume_ma20", 1)
            price_change = abs(features.get("price_change_pct", 0))
            oi_change = abs(features.get("open_interest_delta_pct", 0))

            # 1. Volatility Score (0-25)
            # ATR относительно цены
            if price > 0:
                atr_percent = (atr / price) * 100
                volatility_score = min(atr_percent * 5, 25)  # Max 25
            else:
                volatility_score = 0

            # 2. Volume Score (0-25)
            # Текущий объем относительно MA
            if volume_ma > 0:
                volume_ratio = volume / volume_ma
                volume_score = min((volume_ratio - 1) * 25, 25)  # Max 25
                volume_score = max(0, volume_score)  # Min 0
            else:
                volume_score = 0

            # 3. Price Movement Score (0-25)
            # Изменение цены за 24h
            price_movement_score = min(price_change * 2.5, 25)  # Max 25

            # 4. OI Change Score (0-25)
            # Изменение открытого интереса
            oi_score = min(oi_change * 2.5, 25)  # Max 25

            # Total Heat Score
            heat_score = (
                volatility_score + volume_score + price_movement_score + oi_score
            )

            # Determine heat level
            heat_level, heat_emoji = self._get_heat_level(heat_score)

            return {
                "heat_score": round(heat_score, 1),
                "heat_level": heat_level,
                "heat_emoji": heat_emoji,
                "components": {
                    "volatility": round(volatility_score, 1),
                    "volume": round(volume_score, 1),
                    "price_movement": round(price_movement_score, 1),
                    "oi_change": round(oi_score, 1),
                },
            }

        except Exception as e:
            logger.error(f"calculate_heat error: {e}")
            return {
                "heat_score": 0,
                "heat_level": "COLD",
                "heat_emoji": "❄️",
                "components": {
                    "volatility": 0,
                    "volume": 0,
                    "price_movement": 0,
                    "oi_change": 0,
                },
            }

    def _get_heat_level(self, score: float) -> tuple:
        """
        Determine heat level based on score

        Returns:
            (heat_level, heat_emoji)
        """
        if score >= 80:
            return ("EXTREME", "🔥🔥🔥")
        elif score >= 60:
            return ("HOT", "🔥🔥")
        elif score >= 40:
            return ("WARM", "🔥")
        elif score >= 20:
            return ("COOL", "⚪")
        else:
            return ("COLD", "❄️")

    def format_heat_info(self, heat_data: Dict) -> str:
        """
        Format heat information for display

        Returns:
            Formatted string
        """
        emoji = heat_data["heat_emoji"]
        level = heat_data["heat_level"]
        score = heat_data["heat_score"]

        return f"{emoji} {level} ({score:.0f}/100)"
