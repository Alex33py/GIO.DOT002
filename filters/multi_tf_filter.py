#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Timeframe Filter - согласование тренда по нескольким таймфреймам
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import numpy as np
from config.settings import logger


class MultiTimeframeFilter:
    """
    Фильтр согласования тренда по таймфреймам
    Проверяет, чтобы 1m, 1h, 4h, 1d были в одном направлении
    """

    def __init__(
        self,
        bot=None,
        require_all_aligned: bool = False,
        min_aligned_count: int = 1,
        higher_tf_weight: float = 2.0,
    ):
        """
        Args:
            bot: Экземпляр GIOCryptoBot для доступа к MTFAnalyzer
            require_all_aligned: Требовать согласование всех TF
            min_aligned_count: Минимальное количество согласованных TF
            higher_tf_weight: Вес старших таймфреймов (1d > 4h > 1h > 1m)
        """
        self.bot = bot
        self.require_all_aligned = require_all_aligned
        self.min_aligned_count = min_aligned_count
        self.higher_tf_weight = higher_tf_weight

        # Веса таймфреймов (старшие важнее)
        self.tf_weights = {
            "1m": 1.0,
            "15m": 1.2,
            "1h": 1.5,
            "4h": 2.0,
            "1d": 2.5,
        }

        # Таймфреймы для анализа (по умолчанию)
        self.default_timeframes = ["1h", "4h", "1d"]

        # Параметры для определения тренда
        self.ema_fast_period = 20  # Быстрая EMA
        self.ema_slow_period = 50  # Медленная EMA
        self.sma_period = 200  # SMA для глобального тренда

        # Кэш для хранения данных MTF
        self.mtf_cache: Dict[str, Dict] = {}
        self.cache_expiry = timedelta(minutes=5)
        self.last_cache_update: Dict[str, datetime] = {}

        logger.info(
            f"✅ MultiTimeframeFilter инициализирован "
            f"(require_all={require_all_aligned}, min_aligned={min_aligned_count})"
        )

    async def validate(
        self,
        symbol: str,
        direction: str,
        timeframes: Optional[List[str]] = None,
        min_agreement: Optional[int] = None,
        scenario_name: Optional[str] = None,  # ✅ ДОБАВЛЕН ПАРАМЕТР
    ) -> Tuple[bool, Dict[str, str], str]:
        """
        **ОСНОВНОЙ МЕТОД** - Валидация сигнала через мультитаймфреймовый анализ
        """
        try:
            # ✅ ИСКЛЮЧЕНИЕ ДЛЯ MEAN REVERSION
            if scenario_name and "Mean_Reversion" in scenario_name:
                logger.info(
                    f"✅ {symbol} {direction}: Mean Reversion исключение — "
                    f"MTF Filter пропущен (сценарий: {scenario_name})"
                )
                # Возвращаем "успех" без проверки трендов
                return True, {}, f"Mean Reversion bypass (scenario: {scenario_name})"

            if timeframes is None:
                timeframes = self.default_timeframes

            if min_agreement is None:
                min_agreement = self.min_aligned_count

            direction = direction.upper()
            if direction not in ["LONG", "SHORT"]:
                return False, {}, f"❌ Неверное направление: {direction}"

            # Получаем MTF данные (с трендом и силой)
            mtf_data = await self._get_mtf_data(symbol, timeframes)

            if not mtf_data:
                logger.warning(f"⚠️ MTF данные для {symbol} отсутствуют")
                return False, {}, f"❌ Не удалось получить MTF данные для {symbol}"

            # Валидация через существующий метод validate_signal
            signal = {"direction": direction}
            is_valid, reason = self.validate_signal(signal, mtf_data, symbol)

            # Извлекаем тренды для возврата
            trends = {tf: data.get("trend", "NEUTRAL") for tf, data in mtf_data.items()}

            # Логируем результат
            if is_valid:
                logger.info(
                    f"✅ MTF Filter PASSED: {symbol} {direction} | "
                    f"Trends: {trends} | {reason}"
                )
            else:
                logger.warning(
                    f"⚠️ MTF Filter BLOCKED: {symbol} {direction} | "
                    f"Trends: {trends} | {reason}"
                )

            return is_valid, trends, reason

        except Exception as e:
            logger.error(
                f"❌ Ошибка в MTF Filter.validate() для {symbol}: {e}", exc_info=True
            )
            return False, {}, f"❌ Ошибка валидации: {str(e)}"


    async def analyze(
        self,
        symbol: str,
        direction: str,
        timeframes: Optional[List[str]] = None,
    ) -> Dict:
        """
        Алиас для validate() - возвращает результат в формате для cmd_scenario

        Returns:
            Dict: {
                'passed': bool,
                'aligned_count': int,
                'agreement': float,
                'trends': {'1h': {'direction': 'UP', 'strength': 0.8}, ...}
            }
        """
        is_valid, trends, reason = await self.validate(symbol, direction, timeframes)

        # Подсчёт согласованных таймфреймов
        expected_trend = "UP" if direction == "LONG" else "DOWN"
        aligned_count = sum(1 for t in trends.values() if t == expected_trend)
        agreement = (aligned_count / len(trends) * 100) if trends else 0.0

        # Формируем детализированные данные по трендам
        detailed_trends = {}
        mtf_data = await self._get_mtf_data(
            symbol, timeframes or self.default_timeframes
        )
        for tf, data in mtf_data.items():
            detailed_trends[tf] = {
                "direction": data.get("trend", "UNKNOWN"),
                "strength": data.get("strength", 0.0),
            }

        return {
            "passed": is_valid,
            "aligned_count": aligned_count,
            "agreement": agreement,
            "trends": detailed_trends,
            "reason": reason,
        }

    async def _get_mtf_data(
        self, symbol: str, timeframes: List[str]
    ) -> Dict[str, Dict]:
        """
        Получает MTF данные (тренд + сила) для всех таймфреймов

        Использует:
        1. MTFAnalyzer из бота (если доступен)
        2. Прямой расчет из klines
        3. Кэш (если данные свежие)

        Returns:
            Dict[str, Dict]: {
                '1h': {'trend': 'UP', 'strength': 0.85},
                '4h': {'trend': 'UP', 'strength': 0.92},
                '1d': {'trend': 'DOWN', 'strength': 0.65}
            }
        """
        try:
            # Проверяем кэш
            if self._is_cache_valid(symbol):
                logger.debug(f"📦 Использую кэш MTF для {symbol}")
                return self.mtf_cache[symbol]

            mtf_data = {}

            # Метод 1: Получаем из MTFAnalyzer (если доступен)
            if self.bot and hasattr(self.bot, "mtf_analyzer"):
                for tf in timeframes:
                    try:
                        # Получаем данные из MTFAnalyzer
                        trend_data = await self._get_trend_from_mtf_analyzer(symbol, tf)
                        if trend_data:
                            mtf_data[tf] = trend_data
                    except Exception as e:
                        logger.debug(f"⚠️ MTFAnalyzer недоступен для {symbol} {tf}: {e}")

            # Метод 2: Расчет напрямую из klines (fallback)
            if not mtf_data:
                for tf in timeframes:
                    trend_data = await self._calculate_trend_from_klines(symbol, tf)
                    if trend_data:
                        mtf_data[tf] = trend_data

            # Сохраняем в кэш
            if mtf_data:
                self.mtf_cache[symbol] = mtf_data
                self.last_cache_update[symbol] = datetime.now()

            return mtf_data

        except Exception as e:
            logger.error(f"❌ Ошибка получения MTF данных для {symbol}: {e}")
            return {}

    async def _get_trend_from_mtf_analyzer(self, symbol: str, timeframe: str) -> Dict:
        """Получение тренда из MTFAnalyzer"""
        try:
            # ✅ ИСПОЛЬЗУЕМ _get_klines_from_connector!
            klines = await self._get_klines_from_connector(symbol, timeframe)

            if not klines or len(klines) < 20:
                logger.debug(
                    f"⚠️ Недостаточно свечей для MTF анализа {symbol} {timeframe}"
                )
                return {"trend": "UNKNOWN", "strength": 0}  # ✅ ПРАВИЛЬНО!

            # ✅ Анализируем тренд
            trend_data = self._analyze_trend_simple(klines)

            logger.debug(
                f"✅ MTFAnalyzer {symbol} {timeframe}: {trend_data['trend']} (strength: {trend_data['strength']:.2f})"  # ✅ ПРАВИЛЬНО!
            )

            return trend_data

        except Exception as e:
            logger.debug(f"⚠️ Ошибка получения из MTFAnalyzer {symbol} {timeframe}: {e}")
            return {"trend": "UNKNOWN", "strength": 0}  # ✅ ПРАВИЛЬНО!

    def _analyze_trend_simple(self, klines: List[Dict]) -> Dict:
        """
        Упрощённый анализ тренда по klines

        Returns:
            {'trend': 'UP'/'DOWN'/'NEUTRAL', 'strength': 0.0-1.0}
        """
        if not klines or len(klines) < 20:
            return {"trend": "NEUTRAL", "strength": 0.0}

        try:
            import pandas as pd

            df = pd.DataFrame(klines)
            df["close"] = pd.to_numeric(df["close"], errors="coerce")
            df = df.dropna(subset=["close"])

            if len(df) < 20:
                return {"trend": "NEUTRAL", "strength": 0.0}

            # Вычисляем EMA 20
            ema20 = df["close"].ewm(span=20, adjust=False).mean().iloc[-1]
            current_price = df["close"].iloc[-1]

            # Вычисляем процент отклонения
            deviation = ((current_price - ema20) / ema20) * 100

            # ✅ РАССЧИТЫВАЕМ STRENGTH
            strength = min(abs(deviation) / 5.0, 1.0)

            # ✅ ОПРЕДЕЛЯЕМ ТРЕНД ПО НАПРАВЛЕНИЮ (БЕЗ ЖЁСТКОГО ПОРОГА!)
            if deviation > 0:
                trend = "UP"
            elif deviation < 0:
                trend = "DOWN"
            else:
                trend = "NEUTRAL"

            # ✅ ЕСЛИ STRENGTH < 0.02, ТО NEUTRAL (ТОЛЬКО ДЛЯ ОЧЕНЬ СЛАБЫХ)
            if strength < 0.02:
                trend = "NEUTRAL"

            return {"trend": trend, "strength": strength}

        except Exception as e:
            logger.debug(f"Ошибка в _analyze_trend_simple: {e}")
            return {"trend": "NEUTRAL", "strength": 0.0}

    async def _calculate_trend_from_klines(
        self, symbol: str, timeframe: str
    ) -> Optional[Dict]:
        """
        Рассчитывает тренд напрямую из klines (fallback метод)

        Returns:
            Dict: {'trend': 'UP', 'strength': 0.85} или None
        """
        try:
            # Получаем klines напрямую из коннектора
            klines = await self._get_klines_from_connector(symbol, timeframe)

            if not klines or len(klines) < 50:
                return None

            # Рассчитываем тренд
            trend, strength = self._calculate_trend_and_strength(klines)

            return {"trend": trend, "strength": strength}

        except Exception as e:
            logger.debug(f"⚠️ Ошибка расчета тренда {symbol} {timeframe}: {e}")
            return None

    def _calculate_trend_and_strength(self, klines: List[Dict]) -> Tuple[str, float]:
        """
        Рассчитывает тренд и его силу на основе klines

        Использует:
        - EMA 20/50 crossover
        - SMA 200 для глобального тренда
        - Price position относительно EMA/SMA

        Returns:
            Tuple[str, float]: ('UP'/'DOWN'/'NEUTRAL', strength 0.0-1.0)
        """
        try:
            # Извлекаем цены закрытия
            closes = np.array([float(k.get("close", k.get("c", 0))) for k in klines])

            if len(closes) < 50:
                return "NEUTRAL", 0.5

            current_price = closes[-1]

            # Рассчитываем индикаторы
            ema_fast = self._calculate_ema(closes, self.ema_fast_period)
            ema_slow = self._calculate_ema(closes, self.ema_slow_period)

            if len(closes) >= self.sma_period:
                sma_200 = self._calculate_sma(closes, self.sma_period)
                sma_200_current = sma_200[-1]
            else:
                sma_200_current = current_price

            # Текущие значения
            ema_fast_current = ema_fast[-1]
            ema_slow_current = ema_slow[-1]

            # Определяем тренд (scoring system)
            trend_signals = 0
            strength_factors = []

            # 1. EMA crossover (самый важный сигнал, вес 2)
            if ema_fast_current > ema_slow_current:
                trend_signals += 2
                ema_distance = (ema_fast_current - ema_slow_current) / ema_slow_current
                strength_factors.append(min(abs(ema_distance) * 100, 1.0))
            elif ema_fast_current < ema_slow_current:
                trend_signals -= 2
                ema_distance = (ema_slow_current - ema_fast_current) / ema_slow_current
                strength_factors.append(min(abs(ema_distance) * 100, 1.0))

            # 2. Цена относительно SMA 200 (глобальный тренд, вес 1)
            if current_price > sma_200_current:
                trend_signals += 1
                strength_factors.append(0.8)
            elif current_price < sma_200_current:
                trend_signals -= 1
                strength_factors.append(0.8)

            # 3. Цена относительно быстрой EMA (краткосрочный импульс, вес 1)
            if current_price > ema_fast_current:
                trend_signals += 1
                strength_factors.append(0.6)
            elif current_price < ema_fast_current:
                trend_signals -= 1
                strength_factors.append(0.6)

            # Определяем итоговый тренд
            if trend_signals >= 2:
                trend = "UP"
            elif trend_signals <= -2:
                trend = "DOWN"
            else:
                trend = "NEUTRAL"

            # Рассчитываем силу тренда (0.0 - 1.0)
            if strength_factors:
                strength = np.mean(strength_factors)
            else:
                strength = 0.5

            # Нормализуем силу в зависимости от количества согласованных сигналов
            strength = min(strength * (abs(trend_signals) / 4), 1.0)

            return trend, float(strength)

        except Exception as e:
            logger.error(f"❌ Ошибка расчета тренда: {e}")
            return "NEUTRAL", 0.5

    async def _get_klines_from_connector(
        self, symbol: str, timeframe: str
    ) -> List[Dict]:
        """
        Получает klines напрямую через Bybit REST API

        Использует прямой HTTP запрос к api.bybit.com
        """
        try:
            import httpx

            # Конвертируем timeframe в формат Bybit
            interval_map = {
                "1m": "1",
                "3m": "3",
                "5m": "5",
                "15m": "15",
                "30m": "30",
                "1h": "60",
                "2h": "120",
                "4h": "240",
                "6h": "360",
                "12h": "720",
                "1d": "D",
                "1w": "W",
                "1M": "M",
            }

            interval = interval_map.get(timeframe, "60")

            url = "https://api.bybit.com/v5/market/kline"
            params = {
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "limit": 200,
            }

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(url, params=params)
                data = response.json()

                if data.get("retCode") == 0 and data.get("result", {}).get("list"):
                    klines_raw = data["result"]["list"]

                    # Конвертируем в нужный формат
                    klines = []
                    for k in klines_raw:
                        klines.append(
                            {
                                "time": int(k[0]),
                                "open": float(k[1]),
                                "high": float(k[2]),
                                "low": float(k[3]),
                                "close": float(k[4]),
                                "volume": float(k[5]),
                            }
                        )

                    # Bybit возвращает в обратном порядке (от новых к старым)
                    klines.reverse()

                    logger.info(
                        f"✅ Получено {len(klines)} klines из Bybit REST для {symbol} {timeframe}"
                    )
                    return klines
                else:
                    logger.warning(
                        f"⚠️ Bybit API error: {data.get('retMsg', 'Unknown error')}"
                    )
                    return []

        except Exception as e:
            logger.error(
                f"❌ Ошибка получения klines через REST API {symbol} {timeframe}: {e}"
            )
            return []

    def validate_signal(
        self, signal: Dict, mtf_data: Dict, symbol: str
    ) -> tuple[bool, str]:
        """
        Валидация сигнала через Multi-TF согласование

        Args:
            signal: Сигнал для валидации {'direction': 'LONG'}
            mtf_data: Данные по таймфреймам {
                '1m': {'trend': 'UP', 'strength': 0.8},
                '1h': {'trend': 'UP', 'strength': 0.9},
                '4h': {'trend': 'UP', 'strength': 0.85},
                '1d': {'trend': 'UP', 'strength': 0.7},
            }
            symbol: Торговая пара

        Returns:
            (is_valid, reason) - флаг валидности и причина
        """
        try:
            direction = signal.get("direction", "LONG")
            expected_trend = "UP" if direction == "LONG" else "DOWN"

            aligned_tfs = []
            conflicting_tfs = []
            weighted_score = 0.0
            max_score = 0.0

            # Проверка каждого таймфрейма
            for tf, data in mtf_data.items():
                if not data:
                    continue

                trend = data.get("trend", "NEUTRAL")
                strength = data.get("strength", 0.5)
                weight = self.tf_weights.get(tf, 1.0)

                max_score += weight

                if trend == expected_trend:
                    aligned_tfs.append(tf)
                    weighted_score += weight * strength
                    logger.debug(
                        f"  ✅ {tf}: {trend} (strength: {strength:.2f}, "
                        f"weight: {weight:.1f})"
                    )
                elif trend != "NEUTRAL":
                    conflicting_tfs.append(tf)
                    logger.debug(f"  ❌ {tf}: {trend} (conflicts)")

            # Расчёт процента согласования
            alignment_pct = (weighted_score / max_score * 100) if max_score > 0 else 0

            # Проверка условий
            aligned_count = len(aligned_tfs)
            total_tfs = len(mtf_data)

            # Логирование результата
            logger.info(
                f"📊 {symbol} Multi-TF: {aligned_count}/{total_tfs} aligned "
                f"({alignment_pct:.1f}%), conflicting: {len(conflicting_tfs)}"
            )

            # Валидация
            if self.require_all_aligned:
                if aligned_count == total_tfs:
                    logger.info(f"✅ {symbol}: Все TF согласованы!")
                    return (True, f"All {total_tfs} TFs aligned")
                else:
                    logger.warning(
                        f"⚠️ {symbol}: Не все TF согласованы "
                        f"({aligned_count}/{total_tfs})"
                    )
                    return (False, f"Only {aligned_count}/{total_tfs} TFs aligned")
            else:
                if aligned_count >= self.min_aligned_count:
                    logger.info(
                        f"✅ {symbol}: {aligned_count} TF согласованы "
                        f"(требуется {self.min_aligned_count})"
                    )
                    return (True, f"{aligned_count} TFs aligned ({alignment_pct:.1f}%)")
                else:
                    logger.warning(
                        f"⚠️ {symbol}: Недостаточно согласованных TF "
                        f"({aligned_count} < {self.min_aligned_count})"
                    )
                    return (
                        False,
                        f"Only {aligned_count} TFs aligned "
                        f"(need {self.min_aligned_count})",
                    )

        except Exception as e:
            logger.error(f"❌ Ошибка MultiTimeframeFilter для {symbol}: {e}")
            return (False, f"Error: {e}")

    def get_trend_strength(self, mtf_data: Dict) -> float:
        """
        Расчёт силы тренда по всем таймфреймам

        Returns:
            float: 0.0 - 1.0 (чем выше, тем сильнее тренд)
        """
        try:
            total_weight = 0.0
            weighted_strength = 0.0

            for tf, data in mtf_data.items():
                if not data:
                    continue

                strength = data.get("strength", 0.5)
                weight = self.tf_weights.get(tf, 1.0)

                total_weight += weight
                weighted_strength += weight * strength

            if total_weight == 0:
                return 0.5

            return weighted_strength / total_weight

        except Exception as e:
            logger.error(f"❌ Ошибка get_trend_strength: {e}")
            return 0.5

    def _calculate_ema(self, data: np.ndarray, period: int) -> np.ndarray:
        """Рассчитывает экспоненциальную скользящую среднюю (EMA)"""
        ema = np.zeros_like(data)
        ema[0] = data[0]
        multiplier = 2 / (period + 1)

        for i in range(1, len(data)):
            ema[i] = (data[i] * multiplier) + (ema[i - 1] * (1 - multiplier))

        return ema

    def _calculate_sma(self, data: np.ndarray, period: int) -> np.ndarray:
        """Рассчитывает простую скользящую среднюю (SMA)"""
        if len(data) < period:
            return np.full_like(data, np.nan)

        sma = np.convolve(data, np.ones(period) / period, mode="valid")
        # Дополняем начало массива NaN значениями
        padding = np.full(period - 1, np.nan)
        return np.concatenate([padding, sma])

    def _is_cache_valid(self, symbol: str) -> bool:
        """Проверяет валидность кэша для символа"""
        if symbol not in self.mtf_cache or symbol not in self.last_cache_update:
            return False

        time_since_update = datetime.now() - self.last_cache_update[symbol]
        return time_since_update < self.cache_expiry

    def clear_cache(self, symbol: Optional[str] = None):
        """Очищает кэш MTF данных"""
        if symbol:
            self.mtf_cache.pop(symbol, None)
            self.last_cache_update.pop(symbol, None)
            logger.info(f"🧹 MTF кэш очищен для {symbol}")
        else:
            self.mtf_cache.clear()
            self.last_cache_update.clear()
            logger.info("🧹 Весь MTF кэш очищен")

    async def get_trend_summary(self, symbol: str) -> Dict:
        """
        Получает сводку по трендам для символа (для дебага/мониторинга)

        Returns:
            Dict с информацией о трендах на всех таймфреймах
        """
        mtf_data = await self._get_mtf_data(symbol, self.default_timeframes)

        if not mtf_data:
            return {
                "symbol": symbol,
                "error": "No MTF data available",
                "timestamp": datetime.now().isoformat(),
            }

        trends = {tf: data.get("trend", "NEUTRAL") for tf, data in mtf_data.items()}

        # Определяем доминирующий тренд
        up_count = sum(1 for t in trends.values() if t == "UP")
        down_count = sum(1 for t in trends.values() if t == "DOWN")

        if up_count > down_count:
            dominant = "UP"
        elif down_count > up_count:
            dominant = "DOWN"
        else:
            dominant = "NEUTRAL"

        return {
            "symbol": symbol,
            "trends": trends,
            "dominant_trend": dominant,
            "agreement_score": max(up_count, down_count) / len(trends),
            "overall_strength": self.get_trend_strength(mtf_data),
            "timestamp": datetime.now().isoformat(),
        }


# Экспорт
__all__ = ["MultiTimeframeFilter"]
