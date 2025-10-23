# -*- coding: utf-8 -*-
"""
Продвинутый Volume Profile с использованием реального L2 orderbook
ExoCharts-уровень анализа
"""

import numpy as np
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from config.settings import logger

class ExoChartsVolumeProfile:
    """
    ExoCharts-уровень Volume Profile анализа
    Использует реальный L2 orderbook для максимальной точности
    """

    def __init__(self, num_levels: int = 50):
        self.num_levels = num_levels
        self.profile_cache = {}
        logger.info(f"✅ ExoChartsVolumeProfile инициализирован (уровней: {num_levels})")

    def calculate_profile_from_orderbook(self, orderbook: Dict, trades: List[Dict]) -> Dict:
        """
        Расчёт Volume Profile на основе реального L2 orderbook + сделок

        Это даёт ExoCharts-level точность:
        - POC из реального стакана
        - VAH/VAL на основе фактического распределения ликвидности
        - Liquidity gaps определяются точно
        """

        if not orderbook or not orderbook.get('bids') or not orderbook.get('asks'):
            logger.warning("⚠️ Пустой orderbook для Volume Profile")
            return self._empty_profile()

        bids = orderbook['bids']
        asks = orderbook['asks']

        # 1. Создаём ценовые уровни
        all_prices = [float(b[0]) for b in bids] + [float(a[0]) for a in asks]
        if not all_prices:
            return self._empty_profile()

        min_price = min(all_prices)
        max_price = max(all_prices)

        price_range = max_price - min_price
        if price_range <= 0:
            return self._empty_profile()

        level_size = price_range / self.num_levels

        # 2. Распределяем orderbook объём по уровням
        volume_by_level = defaultdict(float)

        # Bid объём
        for price_str, qty_str in bids:
            price = float(price_str)
            qty = float(qty_str)
            level = int((price - min_price) / level_size)
            level = min(level, self.num_levels - 1)
            volume_by_level[level] += qty

        # Ask объём
        for price_str, qty_str in asks:
            price = float(price_str)
            qty = float(qty_str)
            level = int((price - min_price) / level_size)
            level = min(level, self.num_levels - 1)
            volume_by_level[level] += qty

        # 3. Добавляем объём из реальных сделок
        for trade in trades:
            price = trade.get('price', 0)
            qty = trade.get('qty', 0)

            if min_price <= price <= max_price:
                level = int((price - min_price) / level_size)
                level = min(level, self.num_levels - 1)
                volume_by_level[level] += qty * 2.0

        # 4. Находим POC
        poc_level = max(volume_by_level.items(), key=lambda x: x[1])[0] if volume_by_level else 0
        poc_price = min_price + (poc_level * level_size) + (level_size / 2)
        poc_volume = volume_by_level[poc_level]

        # 5. Рассчитываем Value Area (70% объёма вокруг POC)
        total_volume = sum(volume_by_level.values())
        target_volume = total_volume * 0.70

        va_levels = [poc_level]
        va_volume = volume_by_level[poc_level]

        lower = poc_level - 1
        upper = poc_level + 1

        while va_volume < target_volume and (lower >= 0 or upper < self.num_levels):
            lower_vol = volume_by_level.get(lower, 0) if lower >= 0 else 0
            upper_vol = volume_by_level.get(upper, 0) if upper < self.num_levels else 0

            if lower_vol > upper_vol and lower >= 0:
                va_levels.append(lower)
                va_volume += lower_vol
                lower -= 1
            elif upper < self.num_levels:
                va_levels.append(upper)
                va_volume += upper_vol
                upper += 1
            else:
                break

        vah_level = max(va_levels)
        val_level = min(va_levels)

        vah_price = min_price + (vah_level * level_size) + (level_size / 2)
        val_price = min_price + (val_level * level_size) + (level_size / 2)

        # 6. Находим liquidity gaps
        liquidity_gaps = self._find_liquidity_gaps(volume_by_level, min_price, level_size)

        # 7. Определяем зоны накопления
        accumulation_zones = self._find_accumulation_zones(volume_by_level, min_price, level_size, poc_level)

        # 8. Рассчитываем bid/ask imbalance
        imbalance = self._calculate_orderbook_imbalance(orderbook)

        profile = {
            'poc': poc_price,
            'poc_volume': poc_volume,
            'vah': vah_price,
            'val': val_price,
            'value_area_volume': va_volume,
            'value_area_percentage': (va_volume / total_volume * 100) if total_volume > 0 else 0,
            'total_volume': total_volume,
            'price_range': (min_price, max_price),
            'liquidity_gaps': liquidity_gaps,
            'accumulation_zones': accumulation_zones,
            'orderbook_imbalance': imbalance,
            'volume_distribution': dict(volume_by_level),
            'level_size': level_size,
            'data_quality': 'exocharts_level'
        }

        logger.debug(f"📊 ExoCharts Profile: POC=${poc_price:.2f}, VAH=${vah_price:.2f}, VAL=${val_price:.2f}")

        return profile

    def _find_liquidity_gaps(self, volume_by_level: Dict, min_price: float, level_size: float) -> List[Dict]:
        """Находит пропуски в ликвидности"""
        gaps = []
        avg_volume = np.mean(list(volume_by_level.values())) if volume_by_level else 0

        for level in sorted(volume_by_level.keys()):
            volume = volume_by_level[level]

            if volume < avg_volume * 0.2:
                gap_price = min_price + (level * level_size) + (level_size / 2)
                gaps.append({
                    'price': gap_price,
                    'level': level,
                    'volume': volume,
                    'gap_percentage': (1 - volume / avg_volume) * 100 if avg_volume > 0 else 100
                })

        return gaps

    def _find_accumulation_zones(self, volume_by_level: Dict, min_price: float,
                                 level_size: float, poc_level: int) -> List[Dict]:
        """Находит зоны накопления"""
        zones = []

        if not volume_by_level:
            return zones

        avg_volume = np.mean(list(volume_by_level.values()))

        for level, volume in volume_by_level.items():
            distance_from_poc = abs(level - poc_level)

            if volume > avg_volume * 1.5 and distance_from_poc > 5:
                zone_price = min_price + (level * level_size) + (level_size / 2)
                zones.append({
                    'price': zone_price,
                    'level': level,
                    'volume': volume,
                    'volume_ratio': volume / avg_volume,
                    'distance_from_poc': distance_from_poc,
                    'type': 'accumulation' if level < poc_level else 'distribution'
                })

        return sorted(zones, key=lambda x: x['volume'], reverse=True)

    def _calculate_orderbook_imbalance(self, orderbook: Dict) -> Dict:
        """Расчёт дисбаланса bid/ask в стакане"""
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        top_bid_volume = sum(float(b[1]) for b in bids[:5])
        top_ask_volume = sum(float(a[1]) for a in asks[:5])

        total_bid_volume = sum(float(b[1]) for b in bids)
        total_ask_volume = sum(float(a[1]) for a in asks)

        total_volume = total_bid_volume + total_ask_volume

        return {
            'top_bid_volume': top_bid_volume,
            'top_ask_volume': top_ask_volume,
            'top_bid_ratio': top_bid_volume / (top_bid_volume + top_ask_volume) if (top_bid_volume + top_ask_volume) > 0 else 0.5,
            'total_bid_volume': total_bid_volume,
            'total_ask_volume': total_ask_volume,
            'total_bid_ratio': total_bid_volume / total_volume if total_volume > 0 else 0.5,
            'imbalance_strength': abs(total_bid_volume - total_ask_volume) / total_volume if total_volume > 0 else 0
        }

    def _empty_profile(self) -> Dict:
        """Возвращает пустой профиль"""
        return {
            'poc': 0,
            'vah': 0,
            'val': 0,
            'total_volume': 0,
            'liquidity_gaps': [],
            'accumulation_zones': [],
            'orderbook_imbalance': {},
            'data_quality': 'no_data'
        }

    def get_trading_signals(self, profile: Dict, current_price: float) -> Dict:
        """Генерация торговых сигналов на основе Volume Profile"""
        signals = {
            'strength': 0.0,
            'direction': 'neutral',
            'reasons': []
        }

        poc = profile.get('poc', 0)
        vah = profile.get('vah', 0)
        val = profile.get('val', 0)

        if not all([poc, vah, val]):
            return signals

        if current_price > vah:
            signals['reasons'].append('Цена выше VAH (возможна коррекция)')
            signals['direction'] = 'bearish'
            signals['strength'] += 0.3
        elif current_price < val:
            signals['reasons'].append('Цена ниже VAL (возможен отскок)')
            signals['direction'] = 'bullish'
            signals['strength'] += 0.3
        elif val <= current_price <= vah:
            signals['reasons'].append('Цена в Value Area (справедливая цена)')
            signals['direction'] = 'neutral'

        poc_distance = abs(current_price - poc) / poc * 100
        if poc_distance < 1:
            signals['reasons'].append('Цена около POC (магнитная зона)')
            signals['strength'] += 0.2

        for gap in profile.get('liquidity_gaps', []):
            gap_distance = abs(current_price - gap['price']) / current_price * 100
            if gap_distance < 2:
                signals['reasons'].append(f'Близко к liquidity gap (${gap["price"]:.2f})')
                signals['strength'] += 0.2

        for zone in profile.get('accumulation_zones', []):
            zone_distance = abs(current_price - zone['price']) / current_price * 100
            if zone_distance < 2:
                signals['reasons'].append(f'{zone["type"].capitalize()} зона (${zone["price"]:.2f})')
                signals['strength'] += 0.3

        imbalance = profile.get('orderbook_imbalance', {})
        bid_ratio = imbalance.get('total_bid_ratio', 0.5)

        if bid_ratio > 0.65:
            signals['reasons'].append(f'Сильное bid давление ({bid_ratio:.1%})')
            signals['direction'] = 'bullish'
            signals['strength'] += 0.4
        elif bid_ratio < 0.35:
            signals['reasons'].append(f'Сильное ask давление ({1-bid_ratio:.1%})')
            signals['direction'] = 'bearish'
            signals['strength'] += 0.4

        signals['strength'] = min(signals['strength'], 1.0)

        return signals

    def get_ai_interpretation(self, profile: Dict, current_price: float) -> str:
        """
        AI интерпретация Volume Profile для пользователя

        Args:
            profile: Volume Profile данные
            current_price: Текущая цена

        Returns:
            Строка с AI интерпретацией
        """
        try:
            poc = profile.get('poc', 0)
            vah = profile.get('vah', 0)
            val = profile.get('val', 0)

            if not all([poc, vah, val]):
                return "⚠️ Недостаточно данных для анализа Volume Profile."

            interpretation = []

            # 1. Позиция цены относительно Value Area
            if current_price > vah:
                distance = ((current_price - vah) / vah) * 100
                interpretation.append(f"📈 Цена выше VAH (${vah:.2f}, дистанция +{distance:.1f}%) — рынок в зоне **переоценки**, возможна коррекция к POC.")
            elif current_price < val:
                distance = ((val - current_price) / val) * 100
                interpretation.append(f"📉 Цена ниже VAL (${val:.2f}, дистанция -{distance:.1f}%) — рынок в зоне **недооценки**, возможен отскок к POC.")
            else:
                interpretation.append(f"✅ Цена в Value Area (${val:.2f}-${vah:.2f}) — **справедливая зона**, торговля сбалансирована.")

            # 2. Расстояние от POC
            poc_distance = abs(current_price - poc) / poc * 100
            if poc_distance < 1:
                interpretation.append(f"🎯 Цена около POC (${poc:.2f}) — **магнитная зона**, высокая вероятность консолидации.")
            elif poc_distance > 3:
                interpretation.append(f"⚡ Цена далеко от POC (${poc:.2f}, дистанция {poc_distance:.1f}%) — возможно сильное движение назад к центру стоимости.")
            else:
                interpretation.append(f"📊 Цена на умеренном расстоянии от POC (${poc:.2f}, {poc_distance:.1f}%).")

            # 3. Orderbook Imbalance
            imbalance = profile.get('orderbook_imbalance', {})
            bid_ratio = imbalance.get('total_bid_ratio', 0.5)

            if bid_ratio > 0.60:
                interpretation.append(f"🟢 Сильное **bid давление** ({bid_ratio:.1%}) — покупатели доминируют в стакане.")
            elif bid_ratio < 0.40:
                interpretation.append(f"🔴 Сильное **ask давление** ({1-bid_ratio:.1%}) — продавцы доминируют в стакане.")
            else:
                interpretation.append(f"⚪ Orderbook сбалансирован (bid {bid_ratio:.1%}, ask {1-bid_ratio:.1%}).")

            # 4. Liquidity Gaps
            gaps = profile.get('liquidity_gaps', [])
            nearest_gap = None
            min_distance = float('inf')

            for gap in gaps:
                distance = abs(current_price - gap['price']) / current_price * 100
                if distance < min_distance:
                    min_distance = distance
                    nearest_gap = gap

            if nearest_gap and min_distance < 2:
                interpretation.append(f"⚠️ Близко к **liquidity gap** (${nearest_gap['price']:.2f}, {min_distance:.1f}%) — зона низкой ликвидности, возможны резкие движения!")
            elif gaps:
                interpretation.append(f"📊 Обнаружено {len(gaps)} liquidity gaps — будь осторожен при пересечении этих зон.")

            # 5. Accumulation/Distribution Zones
            zones = profile.get('accumulation_zones', [])
            if zones:
                zone = zones[0]  # Берём самую сильную зону
                zone_distance = abs(current_price - zone['price']) / current_price * 100
                zone_type = "📈 Accumulation" if zone['type'] == 'accumulation' else "📉 Distribution"

                if zone_distance < 3:
                    interpretation.append(f"{zone_type} зона (${zone['price']:.2f}, {zone_distance:.1f}%) — крупные игроки {'набирают' if zone['type'] == 'accumulation' else 'сбрасывают'} позицию.")
                elif zones:
                    interpretation.append(f"📊 Обнаружено {len(zones)} accumulation/distribution зон — важные уровни для отслеживания.")

            # 6. Рекомендация
            signals = self.get_trading_signals(profile, current_price)
            direction = signals.get('direction', 'neutral')
            strength = signals.get('strength', 0)

            if direction == 'bullish' and strength > 0.5:
                interpretation.append(f"\n💡 **РЕКОМЕНДАЦИЯ:** 🚀 Рассмотри **LONG** (уверенность {strength:.0%}). Причины: {', '.join(signals.get('reasons', []))}")
            elif direction == 'bearish' and strength > 0.5:
                interpretation.append(f"\n💡 **РЕКОМЕНДАЦИЯ:** 🔻 Рассмотри **SHORT** (уверенность {strength:.0%}). Причины: {', '.join(signals.get('reasons', []))}")
            else:
                interpretation.append(f"\n💡 **РЕКОМЕНДАЦИЯ:** ⏸️ Ожидание подтверждения (сигнал слабый: {strength:.0%}). {', '.join(signals.get('reasons', []))}")

            return " ".join(interpretation)

        except Exception as e:
            logger.error(f"❌ Ошибка AI интерпретации Volume Profile: {e}")
            return "⚠️ Ошибка генерации AI интерпретации."

# Экспорт
__all__ = ['ExoChartsVolumeProfile']
