# -*- coding: utf-8 -*-
"""
Модуль определения трендов на разных таймфреймах
Использует EMA crossover и MACD для классификации
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional

from config.settings import logger
from config.constants import TrendDirectionEnum
from utils.data_validator import DataValidator


class MultiTimeframeTrendDetector:
    """Определение трендов на 1H, 4H, 1D таймфреймах"""

    def __init__(self):
        """Инициализация detector"""
        self.timeframes = {
            '1h': {'ema_fast': 12, 'ema_slow': 26},
            '4h': {'ema_fast': 12, 'ema_slow': 26},
            '1d': {'ema_fast': 12, 'ema_slow': 26}
        }

        # ✅ ДОБАВИТЬ: Кэш для трендов
        self.trend_cache = {}

        logger.info("✅ MultiTimeframeTrendDetector инициализирован")

    def detect_trends(
        self,
        candles_1h: pd.DataFrame,
        candles_4h: pd.DataFrame,
        candles_1d: pd.DataFrame
    ) -> Dict[str, TrendDirectionEnum]:
        """
        Определение трендов на всех таймфреймах

        Параметры:
            candles_1h: DataFrame со свечами 1H
            candles_4h: DataFrame со свечами 4H
            candles_1d: DataFrame со свечами 1D

        Возвращает:
            Словарь {timeframe: trend_direction}
        """
        try:
            trends = {}

            # Валидация данных
            candles_1h = DataValidator.clean_dataframe(candles_1h)
            candles_4h = DataValidator.clean_dataframe(candles_4h)
            candles_1d = DataValidator.clean_dataframe(candles_1d)

            # Определяем тренд для каждого ТФ
            if not candles_1h.empty:
                trends['trend_1h'] = self._detect_trend(candles_1h, '1h')
            else:
                trends['trend_1h'] = TrendDirectionEnum.NEUTRAL

            if not candles_4h.empty:
                trends['trend_4h'] = self._detect_trend(candles_4h, '4h')
            else:
                trends['trend_4h'] = TrendDirectionEnum.NEUTRAL

            if not candles_1d.empty:
                trends['trend_1d'] = self._detect_trend(candles_1d, '1d')
            else:
                trends['trend_1d'] = TrendDirectionEnum.NEUTRAL

            logger.debug(
                f"📈 Тренды: 1H={trends['trend_1h'].value}, "
                f"4H={trends['trend_4h'].value}, "
                f"1D={trends['trend_1d'].value}"
            )

            return trends

        except Exception as e:
            logger.error(f"❌ Ошибка определения трендов: {e}")
            return {
                'trend_1h': TrendDirectionEnum.NEUTRAL,
                'trend_4h': TrendDirectionEnum.NEUTRAL,
                'trend_1d': TrendDirectionEnum.NEUTRAL
            }

    def _detect_trend(
        self,
        df: pd.DataFrame,
        timeframe: str
    ) -> TrendDirectionEnum:
        """
        Определение тренда для одного таймфрейма

        Логика:
        1. Рассчитываем EMA (fast и slow)
        2. Рассчитываем MACD histogram
        3. Если EMA_fast > EMA_slow И MACD > 0 → BULLISH
        4. Если EMA_fast < EMA_slow И MACD < 0 → BEARISH
        5. Иначе → NEUTRAL
        """
        try:
            if df.empty or len(df) < 30:
                return TrendDirectionEnum.NEUTRAL

            # Параметры EMA
            params = self.timeframes.get(timeframe, {'ema_fast': 12, 'ema_slow': 26})
            ema_fast_period = params['ema_fast']
            ema_slow_period = params['ema_slow']

            # Рассчитываем EMA
            df = df.copy()
            df['ema_fast'] = df['close'].ewm(span=ema_fast_period, adjust=False).mean()
            df['ema_slow'] = df['close'].ewm(span=ema_slow_period, adjust=False).mean()

            # Рассчитываем MACD
            df['macd'] = df['ema_fast'] - df['ema_slow']
            df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
            df['macd_histogram'] = df['macd'] - df['macd_signal']

            # Последние значения
            last = df.iloc[-1]

            ema_fast = last['ema_fast']
            ema_slow = last['ema_slow']
            macd_hist = last['macd_histogram']

            # Определение тренда
            if ema_fast > ema_slow and macd_hist > 0:
                return TrendDirectionEnum.BULLISH
            elif ema_fast < ema_slow and macd_hist < 0:
                return TrendDirectionEnum.BEARISH
            else:
                return TrendDirectionEnum.NEUTRAL

        except Exception as e:
            logger.warning(f"⚠️ Ошибка определения тренда для {timeframe}: {e}")
            return TrendDirectionEnum.NEUTRAL

    def calculate_trend_strength(
        self,
        df: pd.DataFrame,
        timeframe: str
    ) -> float:
        """
        Расчёт силы тренда (0.0 - 1.0)

        Логика:
        - Расстояние между EMA fast и slow
        - Величина MACD histogram
        - Консистентность направления (последние N свечей)
        """
        try:
            if df.empty or len(df) < 30:
                return 0.5

            # Рассчитываем индикаторы если их нет
            if 'ema_fast' not in df.columns:
                params = self.timeframes.get(timeframe, {'ema_fast': 12, 'ema_slow': 26})
                df = df.copy()
                df['ema_fast'] = df['close'].ewm(span=params['ema_fast'], adjust=False).mean()
                df['ema_slow'] = df['close'].ewm(span=params['ema_slow'], adjust=False).mean()
                df['macd'] = df['ema_fast'] - df['ema_slow']
                df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
                df['macd_histogram'] = df['macd'] - df['macd_signal']

            last = df.iloc[-1]

            # 1. Расстояние между EMA (нормализованное)
            ema_distance = abs(last['ema_fast'] - last['ema_slow']) / last['close']
            ema_score = min(ema_distance * 100, 1.0)  # 0-1

            # 2. Величина MACD histogram (нормализованная)
            macd_magnitude = abs(last['macd_histogram']) / last['close']
            macd_score = min(macd_magnitude * 1000, 1.0)  # 0-1

            # 3. Консистентность (последние 10 свечей)
            last_10 = df.tail(10)
            bullish_count = sum(1 for _, row in last_10.iterrows() if row['ema_fast'] > row['ema_slow'])
            consistency_score = abs((bullish_count / 10) - 0.5) * 2  # 0-1

            # Общая сила тренда (взвешенная сумма)
            strength = (ema_score * 0.4 + macd_score * 0.3 + consistency_score * 0.3)

            return round(strength, 3)

        except Exception as e:
            logger.warning(f"⚠️ Ошибка расчёта силы тренда: {e}")
            return 0.5

    def get_mtf_alignment(
        self,
        trends: Dict[str, TrendDirectionEnum]
    ) -> Dict:
        """
        Анализ согласованности трендов

        Возвращает:
            Словарь с информацией о согласованности
        """
        try:
            trend_1h = trends.get('trend_1h', TrendDirectionEnum.NEUTRAL)
            trend_4h = trends.get('trend_4h', TrendDirectionEnum.NEUTRAL)
            trend_1d = trends.get('trend_1d', TrendDirectionEnum.NEUTRAL)

            trend_list = [trend_1h, trend_4h, trend_1d]

            # Подсчёт
            bullish_count = sum(1 for t in trend_list if t == TrendDirectionEnum.BULLISH)
            bearish_count = sum(1 for t in trend_list if t == TrendDirectionEnum.BEARISH)
            neutral_count = sum(1 for t in trend_list if t == TrendDirectionEnum.NEUTRAL)

            # Определение общего направления
            if bullish_count == 3:
                alignment = "full_bullish"
                score = 1.0
            elif bearish_count == 3:
                alignment = "full_bearish"
                score = 1.0
            elif bullish_count >= 2:
                alignment = "majority_bullish"
                score = 0.7
            elif bearish_count >= 2:
                alignment = "majority_bearish"
                score = 0.7
            else:
                alignment = "mixed"
                score = 0.3

            return {
                "alignment": alignment,
                "score": score,
                "bullish_count": bullish_count,
                "bearish_count": bearish_count,
                "neutral_count": neutral_count,
                "trends": {
                    "1h": trend_1h.value,
                    "4h": trend_4h.value,
                    "1d": trend_1d.value
                }
            }

        except Exception as e:
            logger.error(f"❌ Ошибка анализа MTF alignment: {e}")
            return {
                "alignment": "unknown",
                "score": 0.0,
                "bullish_count": 0,
                "bearish_count": 0,
                "neutral_count": 3
            }

    # ========================================================================
    # ✅ НОВЫЕ МЕТОДЫ ДЛЯ 100/100 - ДОБАВИТЬ ЗДЕСЬ!
    # ========================================================================

    def check_mtf_alignment(self, symbol: str, candles_data: Dict = None) -> Dict:
        """
        Проверить согласованность трендов на всех таймфреймах

        Args:
            symbol: Символ (BTCUSDT)
            candles_data: {
                '1H': [...],  # List of dicts или DataFrame
                '4H': [...],
                '1D': [...]
            }

        Returns:
            {
                'aligned': bool,
                'direction': 'LONG' | 'SHORT' | 'NEUTRAL',
                'strength': 0-100,
                'trends': {'1H': ..., '4H': ..., '1D': ...},
                'agreement_score': 0-100,
                'recommendation': str
            }
        """
        try:
            timeframes = ['1H', '4H', '1D']
            trends = {}

            # Получить тренд для каждого таймфрейма
            for tf in timeframes:
                if candles_data and tf in candles_data:
                    # Используем предоставленные данные
                    trend = self._analyze_trend_from_candles(candles_data[tf])
                else:
                    # Получаем данные из кэша
                    trend = self.get_trend(symbol, tf)

                trends[tf] = trend

            # Подсчитать количество каждого тренда
            uptrends = sum(1 for t in trends.values() if t == 'UPTREND')
            downtrends = sum(1 for t in trends.values() if t == 'DOWNTREND')
            neutrals = sum(1 for t in trends.values() if t == 'NEUTRAL')

            total_tf = len(timeframes)

            # Perfect alignment (все 3 TF в одном направлении)
            if uptrends == total_tf:
                return {
                    'aligned': True,
                    'direction': 'LONG',
                    'strength': 100,
                    'trends': trends,
                    'agreement_score': 100,
                    'recommendation': '🟢 STRONG BUY - All timeframes bullish'
                }

            if downtrends == total_tf:
                return {
                    'aligned': True,
                    'direction': 'SHORT',
                    'strength': 100,
                    'trends': trends,
                    'agreement_score': 100,
                    'recommendation': '🔴 STRONG SELL - All timeframes bearish'
                }

            # Partial alignment (2 из 3 TF согласованы)
            if uptrends == 2:
                agreement = (uptrends / total_tf) * 100
                return {
                    'aligned': True,
                    'direction': 'LONG',
                    'strength': 70,
                    'trends': trends,
                    'agreement_score': agreement,
                    'recommendation': '🟡 MODERATE BUY - 2 timeframes bullish'
                }

            if downtrends == 2:
                agreement = (downtrends / total_tf) * 100
                return {
                    'aligned': True,
                    'direction': 'SHORT',
                    'strength': 70,
                    'trends': trends,
                    'agreement_score': agreement,
                    'recommendation': '🟠 MODERATE SELL - 2 timeframes bearish'
                }

            # No alignment (mixed or all neutral)
            if neutrals >= 2:
                return {
                    'aligned': False,
                    'direction': 'NEUTRAL',
                    'strength': 30,
                    'trends': trends,
                    'agreement_score': 30,
                    'recommendation': '⚪ WAIT - Market indecisive'
                }

            # Conflicting signals (1 up, 1 down, 1 neutral)
            return {
                'aligned': False,
                'direction': 'NEUTRAL',
                'strength': 40,
                'trends': trends,
                'agreement_score': 40,
                'recommendation': '⚠️ CAUTION - Conflicting timeframes'
            }

        except Exception as e:
            logger.error(f"❌ check_mtf_alignment error: {e}")
            return {
                'aligned': False,
                'direction': 'NEUTRAL',
                'strength': 0,
                'trends': {},
                'agreement_score': 0,
                'recommendation': '❌ ERROR'
            }

    def _analyze_trend_from_candles(self, candles) -> str:
        """
        Определить тренд из массива свечей

        Args:
            candles: Список свечей [{open, high, low, close, volume}, ...] или DataFrame

        Returns:
            'UPTREND' | 'DOWNTREND' | 'NEUTRAL'
        """
        try:
            # Конвертировать в DataFrame если это список
            if isinstance(candles, list):
                if not candles or len(candles) < 20:
                    return 'NEUTRAL'
                df = pd.DataFrame(candles)
            elif isinstance(candles, pd.DataFrame):
                df = candles
            else:
                return 'NEUTRAL'

            if df.empty or len(df) < 20:
                return 'NEUTRAL'

            # Используем последние 20 свечей
            recent = df.tail(20)

            # Простой метод: сравнить первую и последнюю цену
            first_close = float(recent.iloc[0]['close'])
            last_close = float(recent.iloc[-1]['close'])

            if last_close > first_close * 1.02:  # +2%
                return 'UPTREND'
            elif last_close < first_close * 0.98:  # -2%
                return 'DOWNTREND'
            else:
                return 'NEUTRAL'

        except Exception as e:
            logger.warning(f"⚠️ _analyze_trend_from_candles error: {e}")
            return 'NEUTRAL'

    def get_trend(self, symbol: str, timeframe: str) -> str:
        """
        Получить тренд для символа и таймфрейма из кэша

        Args:
            symbol: BTCUSDT, ETHUSDT, etc.
            timeframe: 1H, 4H, 1D

        Returns:
            'UPTREND' | 'DOWNTREND' | 'NEUTRAL'
        """
        try:
            cache_key = f"{symbol}_{timeframe}"

            if cache_key in self.trend_cache:
                cached_trend = self.trend_cache[cache_key]

                # Конвертировать TrendDirectionEnum в строку если нужно
                if isinstance(cached_trend, TrendDirectionEnum):
                    if cached_trend == TrendDirectionEnum.BULLISH:
                        return 'UPTREND'
                    elif cached_trend == TrendDirectionEnum.BEARISH:
                        return 'DOWNTREND'
                    else:
                        return 'NEUTRAL'

                return cached_trend

            # Если нет в кэше, вернуть NEUTRAL
            return 'NEUTRAL'

        except Exception as e:
            logger.warning(f"⚠️ get_trend error: {e}")
            return 'NEUTRAL'

    # ========================================================================
    # КОНЕЦ НОВЫХ МЕТОДОВ
    # ========================================================================


# Экспорт
__all__ = ['MultiTimeframeTrendDetector']
