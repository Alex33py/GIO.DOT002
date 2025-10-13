#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Market Structure Analyzer - анализ рыночной структуры
Wyckoff Method, Market Phases, Smart Money Concepts
"""

import numpy as np
from typing import List, Dict, Optional
from config.settings import logger


class MarketStructureAnalyzer:
    """Анализатор рыночной структуры"""

    @staticmethod
    def analyze_wyckoff_phase(
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
        lookback: int = 50,
    ) -> Dict:
        """
        Анализ фазы Wyckoff

        Фазы:
        - Accumulation (накопление)
        - Markup (рост)
        - Distribution (распределение)
        - Markdown (падение)

        Args:
            opens, highs, lows, closes: OHLC данные
            volumes: Объёмы
            lookback: Период анализа

        Returns:
            Dict с фазой рынка
        """
        try:
            if len(closes) < lookback:
                return {"phase": "unknown", "confidence": "low"}

            # Берём последние N свечей
            recent_closes = closes[-lookback:]
            recent_volumes = volumes[-lookback:]
            recent_highs = highs[-lookback:]
            recent_lows = lows[-lookback:]

            # Вычисляем метрики
            price_range = max(recent_highs) - min(recent_lows)
            avg_volume = np.mean(recent_volumes)

            # Волатильность (стандартное отклонение)
            volatility = np.std(recent_closes)

            # Тренд (линейная регрессия)
            x = np.arange(len(recent_closes))
            slope = np.polyfit(x, recent_closes, 1)[0]

            # Относительная волатильность
            rel_volatility = (volatility / np.mean(recent_closes)) * 100

            # Анализ объёмов
            volume_trend = np.polyfit(x, recent_volumes, 1)[0]

            # Определяем фазу
            phase = "unknown"
            confidence = "low"

            # ACCUMULATION - низкая волатильность, боковик, растущие объёмы
            if (
                rel_volatility < 2.0
                and abs(slope) < np.mean(recent_closes) * 0.001
                and volume_trend > 0
            ):
                phase = "accumulation"
                confidence = "high"
                description = "Накопление: крупные игроки собирают позиции"

            # MARKUP - сильный рост, высокие объёмы
            elif (
                slope > np.mean(recent_closes) * 0.002
                and avg_volume > np.median(recent_volumes) * 1.2
            ):
                phase = "markup"
                confidence = "high"
                description = "Рост: активная покупка, тренд вверх"

            # DISTRIBUTION - низкая волатильность, боковик, падающие объёмы
            elif (
                rel_volatility < 2.5
                and abs(slope) < np.mean(recent_closes) * 0.001
                and volume_trend < 0
            ):
                phase = "distribution"
                confidence = "high"
                description = "Распределение: крупные игроки продают позиции"

            # MARKDOWN - сильное падение
            elif slope < -np.mean(recent_closes) * 0.002:
                phase = "markdown"
                confidence = "high"
                description = "Падение: активная продажа, тренд вниз"

            # TRANSITION - переходные состояния
            else:
                phase = "transition"
                confidence = "medium"
                description = "Переходная фаза: неопределённость"

            return {
                "phase": phase,
                "confidence": confidence,
                "description": description,
                "volatility": round(rel_volatility, 2),
                "trend_strength": round(abs(slope), 4),
                "volume_trend": "increasing" if volume_trend > 0 else "decreasing",
            }

        except Exception as e:
            logger.error(f"❌ Ошибка анализа фазы Wyckoff: {e}")
            return {"phase": "error", "confidence": "low"}

    @staticmethod
    def identify_market_regime(
        closes: List[float], highs: List[float], lows: List[float], lookback: int = 30
    ) -> Dict:
        """
        Определение режима рынка

        Режимы:
        - Trending (трендовый)
        - Range-bound (боковик)
        - Volatile (волатильный)

        Args:
            closes: Цены закрытия
            highs: Максимумы
            lows: Минимумы
            lookback: Период анализа

        Returns:
            Dict с режимом рынка
        """
        try:
            if len(closes) < lookback:
                return {"regime": "unknown", "strength": "low"}

            recent_closes = closes[-lookback:]
            recent_highs = highs[-lookback:]
            recent_lows = lows[-lookback:]

            # ADX proxy (сила тренда)
            price_changes = np.abs(np.diff(recent_closes))
            avg_price_change = np.mean(price_changes)
            trend_consistency = np.std(price_changes)

            # Диапазон
            price_range = max(recent_highs) - min(recent_lows)
            avg_price = np.mean(recent_closes)
            range_pct = (price_range / avg_price) * 100

            # Волатильность
            volatility = np.std(recent_closes)
            rel_volatility = (volatility / avg_price) * 100

            # Определяем режим
            if trend_consistency < avg_price_change * 0.5:
                # Низкая дисперсия = сильный тренд
                regime = "trending"
                strength = "strong"
                description = "Чёткий тренд с низкой волатильностью"

            elif range_pct < 5 and rel_volatility < 2:
                # Узкий диапазон = боковик
                regime = "range_bound"
                strength = "strong"
                description = "Боковое движение, консолидация"

            elif rel_volatility > 4:
                # Высокая волатильность
                regime = "volatile"
                strength = "high"
                description = "Высокая волатильность, нестабильность"

            else:
                regime = "mixed"
                strength = "medium"
                description = "Смешанный режим, неопределённость"

            return {
                "regime": regime,
                "strength": strength,
                "description": description,
                "volatility_pct": round(rel_volatility, 2),
                "range_pct": round(range_pct, 2),
            }

        except Exception as e:
            logger.error(f"❌ Ошибка определения режима: {e}")
            return {"regime": "error", "strength": "low"}

    @staticmethod
    def detect_liquidity_zones(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        volumes: List[float],
        lookback: int = 50,
    ) -> Dict:
        """
        Обнаружение зон ликвидности (Smart Money Concepts)

        Args:
            highs: Максимумы
            lows: Минимумы
            closes: Цены закрытия
            volumes: Объёмы
            lookback: Период анализа

        Returns:
            Dict с зонами ликвидности
        """
        try:
            if len(closes) < lookback:
                return {"zones": [], "current_zone": None}

            recent_highs = highs[-lookback:]
            recent_lows = lows[-lookback:]
            recent_closes = closes[-lookback:]
            recent_volumes = volumes[-lookback:]

            zones = []

            # Находим зоны с высокими объёмами
            volume_threshold = np.percentile(recent_volumes, 75)  # Топ 25%

            for i in range(len(recent_volumes)):
                if recent_volumes[i] > volume_threshold:
                    # Это зона с высокой активностью
                    zone_high = recent_highs[i]
                    zone_low = recent_lows[i]
                    zone_mid = (zone_high + zone_low) / 2

                    zones.append(
                        {
                            "price": round(zone_mid, 2),
                            "high": round(zone_high, 2),
                            "low": round(zone_low, 2),
                            "volume": round(recent_volumes[i], 2),
                            "type": "high_volume_node",
                        }
                    )

            # Убираем дубликаты (близкие зоны)
            unique_zones = []
            for zone in sorted(zones, key=lambda x: x["price"]):
                if (
                    not unique_zones
                    or abs(zone["price"] - unique_zones[-1]["price"])
                    > zone["price"] * 0.01
                ):
                    unique_zones.append(zone)

            # Определяем текущую зону
            current_price = recent_closes[-1]
            current_zone = None

            for zone in unique_zones:
                if zone["low"] <= current_price <= zone["high"]:
                    current_zone = zone
                    break

            return {
                "zones": unique_zones[:5],  # Топ-5 зон
                "current_zone": current_zone,
                "total_zones": len(unique_zones),
            }

        except Exception as e:
            logger.error(f"❌ Ошибка поиска зон ликвидности: {e}")
            return {"zones": [], "current_zone": None}

    @staticmethod
    def calculate_market_bias(
        closes: List[float],
        volumes: List[float],
        short_period: int = 10,
        long_period: int = 30,
    ) -> Dict:
        """
        Определение направления рынка (bias)

        Args:
            closes: Цены закрытия
            volumes: Объёмы
            short_period: Короткий период
            long_period: Длинный период

        Returns:
            Dict с направлением рынка
        """
        try:
            if len(closes) < long_period:
                return {"bias": "neutral", "strength": "low"}

            # Короткая и длинная MA
            short_ma = np.mean(closes[-short_period:])
            long_ma = np.mean(closes[-long_period:])

            # Текущая цена
            current_price = closes[-1]

            # Средний объём
            avg_volume_short = np.mean(volumes[-short_period:])
            avg_volume_long = np.mean(volumes[-long_period:])

            # Определяем bias
            if short_ma > long_ma and current_price > short_ma:
                bias = "bullish"
                strength = "strong" if avg_volume_short > avg_volume_long else "medium"
                description = "Бычий тренд: покупатели контролируют рынок"

            elif short_ma < long_ma and current_price < short_ma:
                bias = "bearish"
                strength = "strong" if avg_volume_short > avg_volume_long else "medium"
                description = "Медвежий тренд: продавцы контролируют рынок"

            else:
                bias = "neutral"
                strength = "low"
                description = "Нейтральное состояние: баланс сил"

            # Momentum
            momentum = ((current_price - long_ma) / long_ma) * 100

            return {
                "bias": bias,
                "strength": strength,
                "description": description,
                "momentum_pct": round(momentum, 2),
                "short_ma": round(short_ma, 2),
                "long_ma": round(long_ma, 2),
            }

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта bias: {e}")
            return {"bias": "error", "strength": "low"}


# Экспорт
__all__ = ["MarketStructureAnalyzer"]
