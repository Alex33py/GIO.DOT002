#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ExoCharts-уровень Volume Profile с использованием L2 Orderbook
"""

import asyncio
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from config.settings import logger


class ExoChartsVolumeProfileL2:
    """
    Премиум Volume Profile с использованием orderbook L2 данных
    """

    def __init__(self, num_levels: int = 50, orderbook_depth: int = 100):
        self.num_levels = num_levels
        self.orderbook_depth = orderbook_depth
        self.orderbook_cache = {}
        self.last_update = {}

        logger.info(
            f"✅ ExoChartsVolumeProfileL2 инициализирован "
            f"(levels: {num_levels}, depth: {orderbook_depth})"
        )

    async def calculate_volume_profile_l2(
        self,
        symbol: str,
        orderbook_bids: List[List[float]],
        orderbook_asks: List[List[float]],
        trades: List[Dict]
    ) -> Dict:
        """
        Расчет Volume Profile с использованием L2 orderbook + trades

        Args:
            symbol: торговая пара
            orderbook_bids: [[price, volume], ...]
            orderbook_asks: [[price, volume], ...]
            trades: список сделок с полями price, volume, side

        Returns:
            Dict с POC, VAH, VAL, профилем объема, дисбалансами
        """
        try:
            # Объединение данных orderbook и trades
            all_prices = []
            all_volumes = []

            # Добавляем данные из orderbook (биды)
            for price, volume in orderbook_bids[:self.orderbook_depth]:
                all_prices.append(float(price))
                all_volumes.append(float(volume))

            # Добавляем данные из orderbook (аски)
            for price, volume in orderbook_asks[:self.orderbook_depth]:
                all_prices.append(float(price))
                all_volumes.append(float(volume))

            # Добавляем исполненные сделки
            for trade in trades:
                all_prices.append(float(trade.get('price', 0)))
                all_volumes.append(float(trade.get('volume', 0)))

            if not all_prices:
                return self._empty_profile()

            # Определяем диапазон цен
            min_price = min(all_prices)
            max_price = max(all_prices)
            price_range = max_price - min_price

            if price_range == 0:
                return self._empty_profile()

            # Создаем уровни цен
            price_levels = np.linspace(min_price, max_price, self.num_levels)
            level_width = price_range / self.num_levels

            # Распределяем объемы по уровням
            volume_distribution = np.zeros(self.num_levels)

            for price, volume in zip(all_prices, all_volumes):
                level_idx = int((price - min_price) / level_width)
                if 0 <= level_idx < self.num_levels:
                    volume_distribution[level_idx] += volume

            # Расчет POC (Point of Control)
            poc_idx = np.argmax(volume_distribution)
            poc_price = price_levels[poc_idx]
            poc_volume = volume_distribution[poc_idx]

            # Расчет VAH и VAL (Value Area High/Low - 70% объема)
            total_volume = np.sum(volume_distribution)
            value_area_volume = total_volume * 0.70

            vah_idx, val_idx = self._calculate_value_area(
                volume_distribution, poc_idx, value_area_volume
            )

            vah_price = price_levels[vah_idx]
            val_price = price_levels[val_idx]

            # Анализ дисбалансов orderbook
            imbalances = self._calculate_orderbook_imbalances(
                orderbook_bids, orderbook_asks
            )

            # Анализ кластеров объема
            clusters = self._identify_volume_clusters(
                price_levels, volume_distribution, threshold=0.8
            )

            result = {
                'symbol': symbol,
                'poc': poc_price,
                'poc_volume': float(poc_volume),
                'vah': vah_price,
                'val': val_price,
                'value_area_width': vah_price - val_price,
                'total_volume': float(total_volume),
                'price_range': {
                    'min': min_price,
                    'max': max_price,
                    'range': price_range
                },
                'volume_distribution': volume_distribution.tolist(),
                'price_levels': price_levels.tolist(),
                'imbalances': imbalances,
                'volume_clusters': clusters,
                'timestamp': datetime.now().isoformat()
            }

            logger.info(
                f"📊 VP-L2 {symbol}: POC=${poc_price:.2f}, "
                f"VAH=${vah_price:.2f}, VAL=${val_price:.2f}"
            )

            # Кэширование
            self.orderbook_cache[symbol] = result
            self.last_update[symbol] = datetime.now()

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка расчета VP-L2 для {symbol}: {e}")
            return self._empty_profile()

    def _calculate_value_area(
        self,
        volume_dist: np.ndarray,
        poc_idx: int,
        target_volume: float
    ) -> Tuple[int, int]:
        """Расчет Value Area (70% объема вокруг POC)"""
        accumulated_volume = volume_dist[poc_idx]
        vah_idx = poc_idx
        val_idx = poc_idx

        while accumulated_volume < target_volume:
            # Расширяем область вверх и вниз от POC
            upper_volume = volume_dist[vah_idx + 1] if vah_idx + 1 < len(volume_dist) else 0
            lower_volume = volume_dist[val_idx - 1] if val_idx - 1 >= 0 else 0

            if upper_volume >= lower_volume and vah_idx + 1 < len(volume_dist):
                vah_idx += 1
                accumulated_volume += upper_volume
            elif val_idx - 1 >= 0:
                val_idx -= 1
                accumulated_volume += lower_volume
            else:
                break

        return vah_idx, val_idx

    def _calculate_orderbook_imbalances(
        self,
        bids: List[List[float]],
        asks: List[List[float]]
    ) -> Dict:
        """Анализ дисбалансов в orderbook"""
        try:
            total_bid_volume = sum(float(bid[1]) for bid in bids[:20])
            total_ask_volume = sum(float(ask[1]) for ask in asks[:20])

            if total_ask_volume == 0:
                ratio = float('inf') if total_bid_volume > 0 else 1.0
            else:
                ratio = total_bid_volume / total_ask_volume

            # Определение дисбаланса
            if ratio > 1.5:
                imbalance_type = 'strong_bid'
                strength = min((ratio - 1.0) * 100, 100)
            elif ratio < 0.67:
                imbalance_type = 'strong_ask'
                strength = min((1.0 / ratio - 1.0) * 100, 100)
            else:
                imbalance_type = 'balanced'
                strength = 0

            return {
                'bid_volume': total_bid_volume,
                'ask_volume': total_ask_volume,
                'ratio': ratio,
                'type': imbalance_type,
                'strength': round(strength, 2)
            }
        except Exception as e:
            logger.error(f"Ошибка расчета imbalances: {e}")
            return {'type': 'unknown', 'strength': 0}

    def _identify_volume_clusters(
        self,
        price_levels: np.ndarray,
        volume_dist: np.ndarray,
        threshold: float = 0.8
    ) -> List[Dict]:
        """Идентификация кластеров высокого объема"""
        max_volume = np.max(volume_dist)
        cluster_threshold = max_volume * threshold

        clusters = []
        in_cluster = False
        cluster_start = 0

        for i, volume in enumerate(volume_dist):
            if volume >= cluster_threshold and not in_cluster:
                in_cluster = True
                cluster_start = i
            elif volume < cluster_threshold and in_cluster:
                in_cluster = False
                clusters.append({
                    'price_start': float(price_levels[cluster_start]),
                    'price_end': float(price_levels[i - 1]),
                    'total_volume': float(np.sum(volume_dist[cluster_start:i]))
                })

        return clusters

    def _empty_profile(self) -> Dict:
        """Пустой профиль при отсутствии данных"""
        return {
            'symbol': '',
            'poc': 0.0,
            'poc_volume': 0.0,
            'vah': 0.0,
            'val': 0.0,
            'value_area_width': 0.0,
            'total_volume': 0.0,
            'price_range': {'min': 0.0, 'max': 0.0, 'range': 0.0},
            'volume_distribution': [],
            'price_levels': [],
            'imbalances': {'type': 'unknown', 'strength': 0},
            'volume_clusters': [],
            'timestamp': datetime.now().isoformat()
        }
