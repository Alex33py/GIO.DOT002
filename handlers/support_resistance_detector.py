#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Support/Resistance Detector для GIO Bot
Объединяет Volume Profile, Order Book, Price Clusters, CVD для определения уровней
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from config.settings import logger


class AdvancedSupportResistanceDetector:
    """
    Улучшенный детектор уровней поддержки и сопротивления.
    Объединяет анализ объема, стакана ордеров, CVD и ценовых кластеров.
    """

    def __init__(self, atr_multiplier: float = 0.5, volume_threshold: float = 1.5):
        self.atr_multiplier = atr_multiplier
        self.volume_threshold = volume_threshold
        self.previous_levels = {'support': [], 'resistance': []}

    def detect_support_resistance(self, features: Dict) -> Dict:
        """
        Определяет уровни поддержки и сопротивления на основе множества факторов.
        """
        try:
            # Извлечение features
            price = features.get("price")
            poc = features.get("poc", 0)
            vah = features.get("vah", 0)
            val = features.get("val", 0)
            atr = features.get("atr", 1.0)
            cvd_slope = features.get("cvd_slope", 0)
            cvd_value = features.get("cvd_value", 0)
            bids = features.get("order_book_bids", 0)
            asks = features.get("order_book_asks", 0)
            high = features.get("high", price)
            low = features.get("low", price)
            volume_profile = features.get("volume_profile", {})

            if not price or price == 0:
                logger.warning("SR Detector: price = 0, returning empty levels")
                return self._empty_result()

            # 1. Базовые уровни из Volume Profile
            base_support, base_resistance = self._get_volume_levels(val, vah, poc, price, atr)

            # 2. Уровни из стакана ордеров
            order_book_levels = self._get_order_book_levels(price, bids, asks, atr)

            # 3. Уровни из ценовых кластеров (High/Low)
            price_cluster_levels = self._get_price_cluster_levels(high, low, price, atr)

            # 4. Объединение всех уровней
            all_support = base_support + order_book_levels['support'] + price_cluster_levels['support']
            all_resistance = base_resistance + order_book_levels['resistance'] + price_cluster_levels['resistance']

            # 5. Фильтрация и взвешивание уровней по CVD
            filtered_levels = self._apply_cvd_filter(
                all_support, all_resistance, cvd_slope, cvd_value, price
            )

            # 6. Консолидация и ранжирование уровней
            final_levels = self._consolidate_levels(filtered_levels, price, atr)

            # 7. Определение силы уровней
            strength_analysis = self._analyze_strength(final_levels, volume_profile, bids, asks)

            # 8. Обновление истории для отслеживания пробитий
            self._update_level_history(final_levels, price)

            return {
                "support_levels": final_levels['support'],
                "resistance_levels": final_levels['resistance'],
                "key_support": final_levels['key_support'],
                "key_resistance": final_levels['key_resistance'],
                "cvd_bias": "bullish" if cvd_slope > 0 else "bearish",
                "strength_analysis": strength_analysis,
                "trading_zones": self._define_trading_zones(final_levels, price),
                "summary": self._generate_summary(final_levels, cvd_slope, strength_analysis)
            }
        except Exception as e:
            logger.error(f"SR Detector error: {e}", exc_info=True)
            return self._empty_result()

    def _empty_result(self) -> Dict:
        """Возвращает пустой результат при ошибке"""
        return {
            "support_levels": [],
            "resistance_levels": [],
            "key_support": None,
            "key_resistance": None,
            "cvd_bias": "neutral",
            "strength_analysis": {},
            "trading_zones": {"zone": "undefined", "range": None},
            "summary": "Недостаточно данных"
        }

    def _get_volume_levels(self, val: float, vah: float, poc: float,
                          price: float, atr: float) -> Tuple[List, List]:
        """Определяет уровни на основе Volume Profile."""
        support = []
        resistance = []

        # VAL как основной уровень поддержки
        if val and val < price:
            support.append({"price": val, "strength": "strong", "source": "volume"})

        # VAH как основной уровень сопротивления
        if vah and vah > price:
            resistance.append({"price": vah, "strength": "strong", "source": "volume"})

        # POC как динамический уровень
        if poc:
            distance_to_poc = abs(price - poc)
            if distance_to_poc <= self.atr_multiplier * atr:
                strength = "medium"
            else:
                strength = "strong"

            if poc < price:
                support.append({"price": poc, "strength": strength, "source": "volume_poc"})
            else:
                resistance.append({"price": poc, "strength": strength, "source": "volume_poc"})

        return support, resistance

    def _get_order_book_levels(self, price: float, bids: float, asks: float,
                              atr: float) -> Dict:
        """Анализирует стакан ордеров для определения уровней."""
        support = []
        resistance = []

        # Анализ дисбаланса
        if bids > 0 and asks > 0:
            imbalance = bids / asks

            if imbalance > self.volume_threshold:
                # Сильные покупатели - текущая цена как поддержка
                support.append({
                    "price": price,
                    "strength": "medium",
                    "source": "order_book",
                    "imbalance": imbalance
                })
            elif imbalance < (1 / self.volume_threshold):
                # Сильные продавцы - текущая цена как сопротивление
                resistance.append({
                    "price": price,
                    "strength": "medium",
                    "source": "order_book",
                    "imbalance": imbalance
                })

        return {'support': support, 'resistance': resistance}

    def _get_price_cluster_levels(self, high: float, low: float,
                                 price: float, atr: float) -> Dict:
        """Определяет уровни на основе ценовых экстремумов."""
        support = []
        resistance = []

        # Недавний минимум как поддержка
        if low and low < price and (price - low) <= 2 * atr:
            support.append({
                "price": low,
                "strength": "medium",
                "source": "recent_low"
            })

        # Недавний максимум как сопротивление
        if high and high > price and (high - price) <= 2 * atr:
            resistance.append({
                "price": high,
                "strength": "medium",
                "source": "recent_high"
            })

        return {'support': support, 'resistance': resistance}

    def _apply_cvd_filter(self, support: List, resistance: List,
                         cvd_slope: float, cvd_value: float, price: float) -> Dict:
        """Применяет CVD анализ для фильтрации и взвешивания уровней."""

        cvd_bias = "bullish" if cvd_slope > 0 else "bearish"
        cvd_strength = min(abs(cvd_slope) / 100, 1.0)  # Нормализация силы CVD

        filtered_support = []
        filtered_resistance = []

        if cvd_bias == "bullish":
            # Бычий тренд: усиливаем поддержки, фильтруем слабые сопротивления
            for level in support:
                if level['price'] <= price:
                    level['strength'] = self._enhance_strength(level['strength'], cvd_strength)
                    level['cvd_bias'] = "confirmed"
                    filtered_support.append(level)

            for level in resistance:
                if level['price'] > price * 1.02:  # Только значительные сопротивления
                    level['cvd_bias'] = "weakened"
                    filtered_resistance.append(level)

        else:  # Медвежий тренд
            for level in resistance:
                if level['price'] >= price:
                    level['strength'] = self._enhance_strength(level['strength'], cvd_strength)
                    level['cvd_bias'] = "confirmed"
                    filtered_resistance.append(level)

            for level in support:
                if level['price'] < price * 0.98:  # Только значительные поддержки
                    level['cvd_bias'] = "weakened"
                    filtered_support.append(level)

        return {'support': filtered_support, 'resistance': filtered_resistance}

    def _enhance_strength(self, current_strength: str, cvd_strength: float) -> str:
        """Усиливает уровень на основе силы CVD."""
        strength_map = {"weak": 1, "medium": 2, "strong": 3}
        enhanced_value = strength_map.get(current_strength, 1) + cvd_strength

        if enhanced_value >= 2.5:
            return "strong"
        elif enhanced_value >= 1.5:
            return "medium"
        else:
            return "weak"

    def _consolidate_levels(self, levels: Dict, price: float, atr: float) -> Dict:
        """Консолидирует и ранжирует уровни."""
        # Объединение близких уровней
        support = self._merge_near_levels(levels['support'], atr * 0.3)
        resistance = self._merge_near_levels(levels['resistance'], atr * 0.3)

        # Сортировка
        support.sort(key=lambda x: x['price'], reverse=True)  # Ближайшие сверху
        resistance.sort(key=lambda x: x['price'])  # Ближайшие снизу

        # Выбор ключевых уровней
        key_support = self._select_key_level(support, price, "below")
        key_resistance = self._select_key_level(resistance, price, "above")

        return {
            'support': support[:5],  # Топ 5 поддержек
            'resistance': resistance[:5],  # Топ 5 сопротивлений
            'key_support': key_support,
            'key_resistance': key_resistance
        }

    def _merge_near_levels(self, levels: List, threshold: float) -> List:
        """Объединяет уровни, находящиеся близко друг к другу."""
        if not levels:
            return []

        levels.sort(key=lambda x: x['price'])
        merged = [levels[0]]

        for level in levels[1:]:
            last = merged[-1]
            if abs(level['price'] - last['price']) <= threshold:
                merged_price = (last['price'] + level['price']) / 2
                merged_strength = self._merge_strengths(last['strength'], level['strength'])

                merged[-1] = {
                    'price': merged_price,
                    'strength': merged_strength,
                    'source': f"merged_{last['source']}_{level['source']}",
                    'original_levels': [last, level]
                }
            else:
                merged.append(level)

        return merged

    def _merge_strengths(self, strength1: str, strength2: str) -> str:
        """Объединяет силы двух уровней."""
        strength_values = {"weak": 1, "medium": 2, "strong": 3}
        total = strength_values.get(strength1, 1) + strength_values.get(strength2, 1)

        if total >= 5:
            return "strong"
        elif total >= 3:
            return "medium"
        else:
            return "weak"

    def _select_key_level(self, levels: List, price: float, position: str) -> Optional[Dict]:
        """Выбирает ключевой уровень поддержки/сопротивления."""
        if not levels:
            return None

        if position == "below":
            candidate_levels = [level for level in levels if level['price'] < price]
        else:  # "above"
            candidate_levels = [level for level in levels if level['price'] > price]

        if not candidate_levels:
            return None

        return max(candidate_levels, key=lambda x: (
            x['strength'] == "strong",
            x['strength'] == "medium",
            -abs(x['price'] - price)
        ))

    def _analyze_strength(self, levels: Dict, volume_profile: Dict,
                         bids: float, asks: float) -> Dict:
        """Анализирует общую силу уровней."""
        support_strength = sum(1 for level in levels['support'] if level['strength'] == "strong")
        resistance_strength = sum(1 for level in levels['resistance'] if level['strength'] == "strong")

        total_strength = support_strength + resistance_strength
        bias = "bullish" if support_strength > resistance_strength else "bearish"

        return {
            "support_strength": support_strength,
            "resistance_strength": resistance_strength,
            "total_market_strength": total_strength,
            "bias": bias,
            "order_book_imbalance": bids / asks if asks > 0 else 1.0
        }

    def _define_trading_zones(self, levels: Dict, price: float) -> Dict:
        """Определяет торговые зоны."""
        key_support = levels['key_support']
        key_resistance = levels['key_resistance']

        if not key_support or not key_resistance:
            return {"zone": "undefined", "range": None}

        support_price = key_support['price']
        resistance_price = key_resistance['price']

        if price < support_price:
            zone = "bearish_below_support"
        elif price > resistance_price:
            zone = "bullish_above_resistance"
        elif abs(price - support_price) < abs(price - resistance_price):
            zone = "near_support"
        else:
            zone = "near_resistance"

        return {
            "zone": zone,
            "range": (support_price, resistance_price),
            "range_width": resistance_price - support_price
        }

    def _update_level_history(self, levels: Dict, price: float):
        """Обновляет историю уровней для отслеживания пробитий."""
        self.previous_levels['support'] = [level['price'] for level in levels['support']]
        self.previous_levels['resistance'] = [level['price'] for level in levels['resistance']]

    def _generate_summary(self, levels: Dict, cvd_slope: float,
                     strength_analysis: Dict) -> str:
        """Генерирует текстовую сводку."""
        key_support = levels.get('key_support', {})
        key_resistance = levels.get('key_resistance', {})

        support_price = key_support.get('price', 0) if key_support else 0
        resistance_price = key_resistance.get('price', 0) if key_resistance else 0

        # ✅ ИСПРАВЛЕНО: всегда возвращаем строку
        if support_price == 0 or resistance_price == 0:
            return 'Недостаточно данных для определения уровней'

        return (f"CVD: {'bullish' if cvd_slope > 0 else 'bearish'} | "
                f"Key S/R: {support_price:.2f} / {resistance_price:.2f} | "
                f"Bias: {strength_analysis['bias']} | "
                f"Strength: S{strength_analysis['support_strength']}/R{strength_analysis['resistance_strength']}")
