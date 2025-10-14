#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Market Phase Detector
Определяет фазу рынка: Accumulation, Markup, Distribution, Markdown
"""

from typing import Dict, Optional
from config.settings import logger


class MarketPhaseDetector:
    """
    Детектор фазы рынка на основе:
    - Volume Profile (POC, VAH, VAL)
    - Orderbook Pressure
    - CVD (Cumulative Volume Delta)
    - Price Action
    """

    def __init__(self):
        self.phases = {
            "ACCUMULATION": {"emoji": "🟢", "color": "green"},
            "MARKUP": {"emoji": "📈", "color": "blue"},
            "DISTRIBUTION": {"emoji": "🔴", "color": "red"},
            "MARKDOWN": {"emoji": "📉", "color": "orange"},
            "CONSOLIDATION": {"emoji": "⚪", "color": "gray"},
        }
        logger.info("✅ MarketPhaseDetector инициализирован")

    async def detect_phase(
        self,
        symbol: str,
        price: float,
        volume_profile: Dict,
        ob_imbalance: float,
        cvd: float,
        price_change_24h: float,
    ) -> Dict:
        """
        Определяет текущую фазу рынка

        Args:
            symbol: Торговая пара
            price: Текущая цена
            volume_profile: VP данные (POC, VAH, VAL)
            ob_imbalance: Orderbook imbalance (%)
            cvd: Cumulative Volume Delta (%)
            price_change_24h: Изменение цены за 24h (%)

        Returns:
            Dict с информацией о фазе
        """
        try:
            # 1. Определяем позицию цены относительно Volume Profile
            poc = volume_profile.get("poc", 0)
            vah = volume_profile.get("vah", 0)
            val = volume_profile.get("val", 0)

            if not poc or not vah or not val:
                return self._unknown_phase()

            # Позиция цены
            above_vah = price > vah
            below_val = price < val
            in_value_area = val <= price <= vah

            # 2. Анализируем метрики
            strong_buying = ob_imbalance > 30 and cvd > 20
            strong_selling = ob_imbalance < -30 and cvd < -20
            neutral = abs(ob_imbalance) < 20 and abs(cvd) < 20

            # 3. Определяем фазу

            # ACCUMULATION: Цена ниже VAL, сильное покупательское давление
            if below_val and strong_buying and price_change_24h > -5:
                phase = "ACCUMULATION"
                confidence = self._calculate_confidence(
                    [ob_imbalance > 30, cvd > 20, price_change_24h > -2]
                )
                description = "Умные деньги накапливают позиции по низким ценам"

            # MARKUP: Цена выше VAH, сильное покупательское давление, рост
            elif above_vah and strong_buying and price_change_24h > 2:
                phase = "MARKUP"
                confidence = self._calculate_confidence(
                    [ob_imbalance > 30, cvd > 20, price_change_24h > 5]
                )
                description = "Активный рост, маркет-мейкеры толкают цену вверх"

            # DISTRIBUTION: Цена выше VAH, сильное давление продавцов
            elif above_vah and strong_selling and price_change_24h < 5:
                phase = "DISTRIBUTION"
                confidence = self._calculate_confidence(
                    [ob_imbalance < -30, cvd < -20, price_change_24h < 2]
                )
                description = "Умные деньги распределяют позиции на хаях"

            # MARKDOWN: Цена ниже VAL, сильное давление продавцов, падение
            elif below_val and strong_selling and price_change_24h < -2:
                phase = "MARKDOWN"
                confidence = self._calculate_confidence(
                    [ob_imbalance < -30, cvd < -20, price_change_24h < -5]
                )
                description = "Активное падение, маркет-мейкеры толкают цену вниз"

            # CONSOLIDATION: Цена в Value Area, нейтральные метрики
            elif in_value_area and neutral:
                phase = "CONSOLIDATION"
                confidence = self._calculate_confidence(
                    [abs(ob_imbalance) < 20, abs(cvd) < 20, abs(price_change_24h) < 3]
                )
                description = "Боковое движение, ожидание определения направления"

            # UNKNOWN: Недостаточно данных
            else:
                return self._unknown_phase()

            return {
                "phase": phase,
                "emoji": self.phases[phase]["emoji"],
                "color": self.phases[phase]["color"],
                "confidence": confidence,
                "description": description,
                "metrics": {
                    "vp_position": self._get_vp_position(price, poc, vah, val),
                    "ob_imbalance": ob_imbalance,
                    "cvd": cvd,
                    "price_change_24h": price_change_24h,
                },
            }

        except Exception as e:
            logger.error(f"detect_phase error for {symbol}: {e}")
            return self._unknown_phase()

    def _get_vp_position(
        self, price: float, poc: float, vah: float, val: float
    ) -> str:
        """Определяет позицию цены относительно VP"""
        if price > vah:
            return "ABOVE_VAH"
        elif price < val:
            return "BELOW_VAL"
        elif price > poc:
            return "ABOVE_POC"
        else:
            return "BELOW_POC"

    def _calculate_confidence(self, conditions: list) -> int:
        """Рассчитывает уверенность в фазе (0-100%)"""
        true_count = sum(1 for c in conditions if c)
        return int((true_count / len(conditions)) * 100)

    def _unknown_phase(self) -> Dict:
        """Возвращает UNKNOWN фазу"""
        return {
            "phase": "UNKNOWN",
            "emoji": "❓",
            "color": "gray",
            "confidence": 0,
            "description": "Недостаточно данных для определения фазы",
            "metrics": {},
        }

    def get_phase_recommendations(self, phase: str) -> Dict:
        """Возвращает рекомендации для каждой фазы"""
        recommendations = {
            "ACCUMULATION": {
                "action": "WATCH",
                "description": "Следите за пробоем VAL. При пробое вверх — возможен переход в MARKUP.",
                "risk": "LOW",
            },
            "MARKUP": {
                "action": "FOLLOW",
                "description": "Активный рост. Следите за объёмами и дивергенциями. При ослаблении — возможна DISTRIBUTION.",
                "risk": "MEDIUM",
            },
            "DISTRIBUTION": {
                "action": "CAUTION",
                "description": "Умные деньги распределяют. Избегайте покупок на хаях. Ждите пробоя VAH вниз.",
                "risk": "HIGH",
            },
            "MARKDOWN": {
                "action": "AVOID",
                "description": "Активное падение. Не ловите падающий нож. Ждите стабилизации ниже VAL.",
                "risk": "HIGH",
            },
            "CONSOLIDATION": {
                "action": "WAIT",
                "description": "Боковик. Ждите пробоя границ Value Area для определения направления.",
                "risk": "LOW",
            },
        }
        return recommendations.get(phase, {"action": "UNKNOWN", "description": "", "risk": "UNKNOWN"})
