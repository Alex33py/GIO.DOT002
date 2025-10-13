#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pattern Detector - распознавание паттернов на графиках
Candlestick patterns, Support/Resistance, Trend Lines
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from config.settings import logger


class PatternDetector:
    """Детектор графических паттернов"""

    @staticmethod
    def detect_candlestick_patterns(
        opens: List[float],
        highs: List[float],
        lows: List[float],
        closes: List[float],
        lookback: int = 3,
    ) -> Dict:
        """
        Обнаружение свечных паттернов

        Args:
            opens: Цены открытия
            highs: Максимумы
            lows: Минимумы
            closes: Цены закрытия
            lookback: Количество свечей для анализа

        Returns:
            Dict с найденными паттернами
        """
        try:
            if len(closes) < lookback:
                return {"patterns": [], "signal": "neutral"}

            patterns = []

            # Последние свечи
            o = opens[-lookback:]
            h = highs[-lookback:]
            l = lows[-lookback:]
            c = closes[-lookback:]

            # 1. DOJI - нерешительность
            last_body = abs(c[-1] - o[-1])
            last_range = h[-1] - l[-1]
            if last_range > 0 and (last_body / last_range) < 0.1:
                patterns.append(
                    {
                        "name": "Doji",
                        "type": "reversal",
                        "strength": "medium",
                        "description": "Нерешительность рынка",
                    }
                )

            # 2. HAMMER - бычий разворот
            if c[-1] > o[-1]:  # Зелёная свеча
                body = c[-1] - o[-1]
                lower_shadow = o[-1] - l[-1]
                upper_shadow = h[-1] - c[-1]

                if lower_shadow > body * 2 and upper_shadow < body * 0.5:
                    patterns.append(
                        {
                            "name": "Hammer",
                            "type": "bullish_reversal",
                            "strength": "strong",
                            "description": "Сильный бычий разворот",
                        }
                    )

            # 3. SHOOTING STAR - медвежий разворот
            if o[-1] > c[-1]:  # Красная свеча
                body = o[-1] - c[-1]
                lower_shadow = c[-1] - l[-1]
                upper_shadow = h[-1] - o[-1]

                if upper_shadow > body * 2 and lower_shadow < body * 0.5:
                    patterns.append(
                        {
                            "name": "Shooting Star",
                            "type": "bearish_reversal",
                            "strength": "strong",
                            "description": "Сильный медвежий разворот",
                        }
                    )

            # 4. ENGULFING - поглощение (2 свечи)
            if len(c) >= 2:
                prev_body = abs(c[-2] - o[-2])
                curr_body = abs(c[-1] - o[-1])

                # Bullish Engulfing
                if o[-2] > c[-2] and c[-1] > o[-1]:  # Была красная, стала зелёная
                    if c[-1] > o[-2] and o[-1] < c[-2] and curr_body > prev_body:
                        patterns.append(
                            {
                                "name": "Bullish Engulfing",
                                "type": "bullish_reversal",
                                "strength": "very_strong",
                                "description": "Очень сильный бычий сигнал",
                            }
                        )

                # Bearish Engulfing
                if c[-2] > o[-2] and o[-1] > c[-1]:  # Была зелёная, стала красная
                    if o[-1] > c[-2] and c[-1] < o[-2] and curr_body > prev_body:
                        patterns.append(
                            {
                                "name": "Bearish Engulfing",
                                "type": "bearish_reversal",
                                "strength": "very_strong",
                                "description": "Очень сильный медвежий сигнал",
                            }
                        )

            # 5. MORNING/EVENING STAR (3 свечи)
            if len(c) >= 3:
                # Morning Star (бычий)
                if (
                    o[-3] > c[-3]  # 1я свеча красная
                    and abs(c[-2] - o[-2]) < (h[-3] - l[-3]) * 0.3  # 2я маленькая
                    and c[-1] > o[-1]  # 3я зелёная
                    and c[-1] > (o[-3] + c[-3]) / 2
                ):  # Закрылась выше середины 1й

                    patterns.append(
                        {
                            "name": "Morning Star",
                            "type": "bullish_reversal",
                            "strength": "very_strong",
                            "description": "Мощный бычий разворот",
                        }
                    )

                # Evening Star (медвежий)
                if (
                    c[-3] > o[-3]  # 1я свеча зелёная
                    and abs(c[-2] - o[-2]) < (h[-3] - l[-3]) * 0.3  # 2я маленькая
                    and o[-1] > c[-1]  # 3я красная
                    and c[-1] < (o[-3] + c[-3]) / 2
                ):  # Закрылась ниже середины 1й

                    patterns.append(
                        {
                            "name": "Evening Star",
                            "type": "bearish_reversal",
                            "strength": "very_strong",
                            "description": "Мощный медвежий разворот",
                        }
                    )

            # Определяем общий сигнал
            if patterns:
                bullish = sum(1 for p in patterns if "bullish" in p["type"])
                bearish = sum(1 for p in patterns if "bearish" in p["type"])

                if bullish > bearish:
                    signal = "bullish"
                elif bearish > bullish:
                    signal = "bearish"
                else:
                    signal = "mixed"
            else:
                signal = "neutral"

            return {"patterns": patterns, "signal": signal, "count": len(patterns)}

        except Exception as e:
            logger.error(f"❌ Ошибка детекции паттернов: {e}")
            return {"patterns": [], "signal": "neutral"}

    @staticmethod
    def find_support_resistance(
        highs: List[float],
        lows: List[float],
        closes: List[float],
        lookback: int = 50,
        touch_threshold: float = 0.02,
    ) -> Dict:
        """
        Поиск уровней поддержки и сопротивления

        Args:
            highs: Максимумы
            lows: Минимумы
            closes: Цены закрытия
            lookback: Период анализа
            touch_threshold: Порог касания уровня (2%)

        Returns:
            Dict с уровнями поддержки/сопротивления
        """
        try:
            if len(closes) < lookback:
                return {"support": [], "resistance": []}

            # Берём последние N свечей
            recent_highs = highs[-lookback:]
            recent_lows = lows[-lookback:]
            current_price = closes[-1]

            # Находим локальные максимумы
            resistance_levels = []
            for i in range(2, len(recent_highs) - 2):
                if (
                    recent_highs[i] > recent_highs[i - 1]
                    and recent_highs[i] > recent_highs[i - 2]
                    and recent_highs[i] > recent_highs[i + 1]
                    and recent_highs[i] > recent_highs[i + 2]
                ):

                    # Считаем количество касаний
                    touches = sum(
                        1
                        for h in recent_highs
                        if abs(h - recent_highs[i]) / recent_highs[i] < touch_threshold
                    )

                    if touches >= 2:  # Минимум 2 касания
                        resistance_levels.append(
                            {
                                "level": round(recent_highs[i], 2),
                                "touches": touches,
                                "strength": "strong" if touches >= 3 else "medium",
                                "distance_pct": round(
                                    ((recent_highs[i] - current_price) / current_price)
                                    * 100,
                                    2,
                                ),
                            }
                        )

            # Находим локальные минимумы
            support_levels = []
            for i in range(2, len(recent_lows) - 2):
                if (
                    recent_lows[i] < recent_lows[i - 1]
                    and recent_lows[i] < recent_lows[i - 2]
                    and recent_lows[i] < recent_lows[i + 1]
                    and recent_lows[i] < recent_lows[i + 2]
                ):

                    # Считаем количество касаний
                    touches = sum(
                        1
                        for l in recent_lows
                        if abs(l - recent_lows[i]) / recent_lows[i] < touch_threshold
                    )

                    if touches >= 2:  # Минимум 2 касания
                        support_levels.append(
                            {
                                "level": round(recent_lows[i], 2),
                                "touches": touches,
                                "strength": "strong" if touches >= 3 else "medium",
                                "distance_pct": round(
                                    ((current_price - recent_lows[i]) / current_price)
                                    * 100,
                                    2,
                                ),
                            }
                        )

            # Убираем дубликаты (близкие уровни)
            def remove_duplicates(levels):
                if not levels:
                    return []

                unique = []
                for level in sorted(levels, key=lambda x: x["level"]):
                    if (
                        not unique
                        or abs(level["level"] - unique[-1]["level"]) / level["level"]
                        > touch_threshold
                    ):
                        unique.append(level)
                return unique

            resistance_levels = remove_duplicates(resistance_levels)
            support_levels = remove_duplicates(support_levels)

            # Сортируем по силе
            resistance_levels.sort(key=lambda x: x["touches"], reverse=True)
            support_levels.sort(key=lambda x: x["touches"], reverse=True)

            # Топ-3 уровня
            return {
                "support": support_levels[:3],
                "resistance": resistance_levels[:3],
                "current_price": round(current_price, 2),
            }

        except Exception as e:
            logger.error(f"❌ Ошибка поиска S/R уровней: {e}")
            return {"support": [], "resistance": []}

    @staticmethod
    def detect_trend_structure(
        highs: List[float], lows: List[float], closes: List[float], lookback: int = 20
    ) -> Dict:
        """
        Анализ структуры тренда (Higher Highs/Lower Lows)

        Args:
            highs: Максимумы
            lows: Минимумы
            closes: Цены закрытия
            lookback: Период анализа

        Returns:
            Dict со структурой тренда
        """
        try:
            if len(closes) < lookback:
                return {"trend": "unknown", "structure": "sideways"}

            recent_highs = highs[-lookback:]
            recent_lows = lows[-lookback:]

            # Находим swing points (локальные экстремумы)
            swing_highs = []
            swing_lows = []

            for i in range(2, len(recent_highs) - 2):
                # Swing High
                if (
                    recent_highs[i] > recent_highs[i - 1]
                    and recent_highs[i] > recent_highs[i + 1]
                ):
                    swing_highs.append(recent_highs[i])

                # Swing Low
                if (
                    recent_lows[i] < recent_lows[i - 1]
                    and recent_lows[i] < recent_lows[i + 1]
                ):
                    swing_lows.append(recent_lows[i])

            # Анализируем тренд
            if len(swing_highs) >= 2 and len(swing_lows) >= 2:
                # Higher Highs и Higher Lows = Uptrend
                hh = all(
                    swing_highs[i] > swing_highs[i - 1]
                    for i in range(1, len(swing_highs))
                )
                hl = all(
                    swing_lows[i] > swing_lows[i - 1] for i in range(1, len(swing_lows))
                )

                # Lower Highs и Lower Lows = Downtrend
                lh = all(
                    swing_highs[i] < swing_highs[i - 1]
                    for i in range(1, len(swing_highs))
                )
                ll = all(
                    swing_lows[i] < swing_lows[i - 1] for i in range(1, len(swing_lows))
                )

                if hh and hl:
                    trend = "uptrend"
                    structure = "higher_highs_higher_lows"
                elif lh and ll:
                    trend = "downtrend"
                    structure = "lower_highs_lower_lows"
                else:
                    trend = "sideways"
                    structure = "mixed"
            else:
                trend = "unknown"
                structure = "insufficient_data"

            return {
                "trend": trend,
                "structure": structure,
                "swing_highs_count": len(swing_highs),
                "swing_lows_count": len(swing_lows),
                "last_swing_high": round(swing_highs[-1], 2) if swing_highs else 0,
                "last_swing_low": round(swing_lows[-1], 2) if swing_lows else 0,
            }

        except Exception as e:
            logger.error(f"❌ Ошибка анализа структуры тренда: {e}")
            return {"trend": "unknown", "structure": "error"}


# Экспорт
__all__ = ["PatternDetector"]
