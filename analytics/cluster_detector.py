#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cluster Detector - Обнаружение кластеров OrderFlow
Анализирует:
- Stacked Imbalances (накопленные дисбалансы)
- POC Shifts (смещение Point of Control)
- Absorption (зоны поглощения)
- Exhaustion (зоны истощения)
"""

from typing import Dict, Optional, List
from datetime import datetime, timedelta
import numpy as np
from config.settings import logger


class ClusterDetector:
    """Обнаружение кластеров на основе OrderFlow"""

    def __init__(self, bot):
        """
        Args:
            bot: Экземпляр GIOCryptoBot для доступа к данным
        """
        self.bot = bot

        # Параметры для stacked imbalances
        self.imbalance_threshold = 0.6  # 60% дисбаланс считается значимым
        self.min_stack_count = 3  # Минимум 3 последовательных дисбаланса

        # Параметры для POC shift
        self.poc_shift_threshold = 0.5  # 0.5% смещение POC считается значимым

        # Параметры для absorption/exhaustion
        self.absorption_volume_multiplier = 2.0  # 2x от среднего объёма
        self.exhaustion_volume_multiplier = 0.3  # 0.3x от среднего объёма

        # Кэш для хранения исторических данных
        self.poc_history: Dict[str, List[float]] = {}
        self.imbalance_history: Dict[str, List[Dict]] = {}

        logger.info("✅ ClusterDetector инициализирован")

    async def detect_stacked_imbalances(self, symbol: str, direction: str) -> int:
        """
        Обнаруживает накопленные дисбалансы (последовательные дисбалансы в одном направлении)

        Args:
            symbol: Торговая пара (например, 'BTCUSDT')
            direction: Направление ('LONG' или 'SHORT')

        Returns:
            int: Количество stacked imbalances (0-5+)
        """
        try:
            # Получаем последние L2 дисбалансы
            if not hasattr(self.bot, 'l2_imbalances') or symbol not in self.bot.l2_imbalances:
                logger.debug(f"⚠️ Нет L2 данных для {symbol}")
                return 0

            # Берём последние 10 дисбалансов
            recent_imbalances = self.bot.l2_imbalances[symbol][-10:]

            if len(recent_imbalances) < self.min_stack_count:
                return 0

            # Определяем ожидаемое направление дисбаланса
            expected_direction = 'BUY' if direction == 'LONG' else 'SELL'

            # Считаем последовательные дисбалансы в нужном направлении
            stack_count = 0
            current_streak = 0

            for imbalance in reversed(recent_imbalances):
                imbalance_value = imbalance.get('imbalance', 0)

                # Проверяем силу дисбаланса
                if expected_direction == 'BUY' and imbalance_value > self.imbalance_threshold:
                    current_streak += 1
                elif expected_direction == 'SELL' and imbalance_value < -self.imbalance_threshold:
                    current_streak += 1
                else:
                    # Прерываем стрик
                    if current_streak >= self.min_stack_count:
                        stack_count = max(stack_count, current_streak)
                    current_streak = 0

            # Проверяем последний стрик
            if current_streak >= self.min_stack_count:
                stack_count = max(stack_count, current_streak)

            logger.debug(f"📊 {symbol}: Stacked Imbalances = {stack_count} ({direction})")
            return min(stack_count, 5)  # Максимум 5

        except Exception as e:
            logger.error(f"❌ Ошибка detect_stacked_imbalances для {symbol}: {e}")
            return 0

    async def detect_poc_shift(self, symbol: str) -> Dict:
        """
        Отслеживает смещение POC (Point of Control) за последние свечи

        Args:
            symbol: Торговая пара

        Returns:
            Dict: {
                'shifted': bool,
                'direction': 'up'/'down'/'none',
                'magnitude': float  # В процентах
            }
        """
        try:
            # Получаем текущий POC из ExoCharts
            current_poc = None

            if hasattr(self.bot, 'exocharts_data') and symbol in self.bot.exocharts_data:
                exo_data = self.bot.exocharts_data[symbol]
                current_poc = exo_data.get('poc')

            if current_poc is None:
                return {'shifted': False, 'direction': 'none', 'magnitude': 0.0}

            # Инициализируем историю POC если нужно
            if symbol not in self.poc_history:
                self.poc_history[symbol] = []

            # Добавляем текущий POC в историю
            self.poc_history[symbol].append(current_poc)

            # Храним только последние 20 значений
            if len(self.poc_history[symbol]) > 20:
                self.poc_history[symbol] = self.poc_history[symbol][-20:]

            # Нужно минимум 5 исторических значений
            if len(self.poc_history[symbol]) < 5:
                return {'shifted': False, 'direction': 'none', 'magnitude': 0.0}

            # Сравниваем текущий POC с средним за последние 5 свечей
            previous_pocs = self.poc_history[symbol][-6:-1]
            avg_previous_poc = np.mean(previous_pocs)

            # Рассчитываем смещение в процентах
            shift_pct = ((current_poc - avg_previous_poc) / avg_previous_poc) * 100

            # Определяем значимость смещения
            shifted = abs(shift_pct) >= self.poc_shift_threshold
            direction = 'up' if shift_pct > 0 else 'down' if shift_pct < 0 else 'none'

            if shifted:
                logger.info(f"🎯 {symbol}: POC Shift {direction.upper()} by {abs(shift_pct):.2f}%")

            return {
                'shifted': shifted,
                'direction': direction,
                'magnitude': abs(shift_pct)
            }

        except Exception as e:
            logger.error(f"❌ Ошибка detect_poc_shift для {symbol}: {e}")
            return {'shifted': False, 'direction': 'none', 'magnitude': 0.0}

    async def detect_absorption(self, symbol: str) -> Dict:
        """
        Определяет зоны поглощения (absorption) - высокий объём без движения цены

        Args:
            symbol: Торговая пара

        Returns:
            Dict: {
                'detected': bool,
                'level': float,      # Уровень цены зоны
                'volume': float      # Объём в зоне
            }
        """
        try:
            # Получаем данные о крупных сделках
            if not hasattr(self.bot, 'large_trades') or symbol not in self.bot.large_trades:
                return {'detected': False, 'level': 0.0, 'volume': 0.0}

            # Берём последние 50 крупных сделок
            recent_trades = self.bot.large_trades[symbol][-50:]

            if len(recent_trades) < 10:
                return {'detected': False, 'level': 0.0, 'volume': 0.0}

            # Группируем сделки по ценовым уровням (±0.1%)
            price_levels = {}

            for trade in recent_trades:
                price = trade.get('price', 0)
                volume = trade.get('quantity', 0)

                # Округляем цену до 0.1%
                level_key = round(price, -int(np.log10(price)) + 2)

                if level_key not in price_levels:
                    price_levels[level_key] = {'volume': 0, 'count': 0}

                price_levels[level_key]['volume'] += volume
                price_levels[level_key]['count'] += 1

            # Находим средний объём
            avg_volume = np.mean([data['volume'] for data in price_levels.values()])

            # Ищем зоны с аномально высоким объёмом
            absorption_threshold = avg_volume * self.absorption_volume_multiplier

            for level, data in price_levels.items():
                if data['volume'] >= absorption_threshold and data['count'] >= 5:
                    logger.info(f"🛡️ {symbol}: Absorption detected at ${level:.2f} (volume: {data['volume']:.2f})")

                    return {
                        'detected': True,
                        'level': level,
                        'volume': data['volume']
                    }

            return {'detected': False, 'level': 0.0, 'volume': 0.0}

        except Exception as e:
            logger.error(f"❌ Ошибка detect_absorption для {symbol}: {e}")
            return {'detected': False, 'level': 0.0, 'volume': 0.0}

    async def detect_exhaustion(self, symbol: str) -> Dict:
        """
        Определяет зоны истощения (exhaustion) - низкий объём после сильного движения

        Args:
            symbol: Торговая пара

        Returns:
            Dict: {
                'detected': bool,
                'level': float,      # Уровень цены зоны
                'strength': float    # Сила истощения (0.0-1.0)
            }
        """
        try:
            # Получаем данные о крупных сделках
            if not hasattr(self.bot, 'large_trades') or symbol not in self.bot.large_trades:
                return {'detected': False, 'level': 0.0, 'strength': 0.0}

            # Берём последние 100 крупных сделок
            all_trades = self.bot.large_trades[symbol][-100:]

            if len(all_trades) < 20:
                return {'detected': False, 'level': 0.0, 'strength': 0.0}

            # Разделяем на 2 части: старые (80%) и новые (20%)
            split_point = int(len(all_trades) * 0.8)
            old_trades = all_trades[:split_point]
            new_trades = all_trades[split_point:]

            # Рассчитываем средний объём для каждой части
            old_avg_volume = np.mean([t.get('quantity', 0) for t in old_trades])
            new_avg_volume = np.mean([t.get('quantity', 0) for t in new_trades])

            # Проверяем снижение объёма
            if new_avg_volume < old_avg_volume * self.exhaustion_volume_multiplier:
                # Истощение обнаружено

                # Рассчитываем силу истощения
                volume_drop = (old_avg_volume - new_avg_volume) / old_avg_volume
                strength = min(volume_drop, 1.0)

                # Находим текущий уровень цены
                current_level = new_trades[-1].get('price', 0) if new_trades else 0

                logger.info(f"💥 {symbol}: Exhaustion detected at ${current_level:.2f} (strength: {strength:.2f})")

                return {
                    'detected': True,
                    'level': current_level,
                    'strength': strength
                }

            return {'detected': False, 'level': 0.0, 'strength': 0.0}

        except Exception as e:
            logger.error(f"❌ Ошибка detect_exhaustion для {symbol}: {e}")
            return {'detected': False, 'level': 0.0, 'strength': 0.0}

    async def get_cluster_score(self, symbol: str, direction: str) -> float:
        """
        Рассчитывает общий score кластерного анализа (0.0-1.0)

        Args:
            symbol: Торговая пара
            direction: Направление ('LONG' или 'SHORT')

        Returns:
            float: Score от 0.0 до 1.0
        """
        try:
            # Получаем все метрики
            stacked = await self.detect_stacked_imbalances(symbol, direction)
            poc_shift = await self.detect_poc_shift(symbol)
            absorption = await self.detect_absorption(symbol)
            exhaustion = await self.detect_exhaustion(symbol)

            # Рассчитываем score (0.0-1.0)
            score = 0.0

            # Stacked imbalances (0-0.4)
            score += min(stacked / 5.0, 1.0) * 0.4

            # POC shift (0-0.3)
            if poc_shift['shifted']:
                expected_direction = 'up' if direction == 'LONG' else 'down'
                if poc_shift['direction'] == expected_direction:
                    score += min(poc_shift['magnitude'] / 2.0, 1.0) * 0.3

            # Absorption (0-0.15)
            if absorption['detected']:
                score += 0.15

            # Exhaustion (0-0.15)
            if exhaustion['detected']:
                score += exhaustion['strength'] * 0.15

            logger.debug(f"📊 {symbol} Cluster Score: {score:.2f}")
            return score

        except Exception as e:
            logger.error(f"❌ Ошибка get_cluster_score для {symbol}: {e}")
            return 0.0


# Экспорт
__all__ = ["ClusterDetector"]
