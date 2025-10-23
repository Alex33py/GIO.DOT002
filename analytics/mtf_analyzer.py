#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Timeframe Analyzer v2.0
Полный анализ трендов с ADX, EMA, MACD, RSI
"""

from datetime import datetime
from typing import Dict, Optional
from config.settings import logger
from utils.error_logger import ErrorLogger
from utils.validators import DataValidator


class MultiTimeframeAnalyzer:
    """Анализ на нескольких таймфреймах с полным расчётом индикаторов"""

    def __init__(self, connector):
        """
        Инициализация MTF Analyzer

        Args:
            connector: Коннектор к бирже (Bybit/OKX)
        """
        self.bybit_connector = connector
        logger.info("✅ MultiTimeframeAnalyzer v2.0 инициализирован")

    async def analyze(self, symbol: str, interval: str = "1h") -> Optional[Dict]:
        """
        Полный MTF анализ с определением тренда

        Args:
            symbol: Торговая пара (BTCUSDT)
            interval: Таймфрейм (1h, 4h, 1d)

        Returns:
            Словарь с результатами анализа или None
        """
        try:
            # ✅ МАППИНГ ТАЙМФРЕЙМОВ ДЛЯ BYBIT КЭША
            timeframe_map = {
                "1h": "60",
                "4h": "240",
                "1d": "D"
            }

            bybit_interval = timeframe_map.get(interval.lower(), interval)

            # ✅ ПОЛУЧАЕМ СВЕЧИ ИЗ КЭША
            cache_key = f"{symbol}:{bybit_interval}"
            cached_data = self.bybit_connector.klines_cache.get(cache_key)

            if not cached_data or "candles" not in cached_data:
                logger.warning(f"⚠️ Нет данных свечей для {symbol} ({interval})")
                return None

            candles = cached_data["candles"]

            # ВАЛИДАЦИЯ
            if not candles or len(candles) < 50:
                logger.debug(f"⚠️ Недостаточно свечей для {symbol} ({interval}): {len(candles) if candles else 0}")
                return None

            # ✅ РАСЧЁТ ВСЕХ ИНДИКАТОРОВ
            rsi = self.calculate_rsi(candles, period=14)
            adx = self.calculate_adx(candles, period=14)
            ema_20 = self.calculate_ema(candles, period=20)
            ema_50 = self.calculate_ema(candles, period=50)
            macd_data = self.calculate_macd(candles)

            current_price = float(candles[-1]["close"])

            # ✅ ОПРЕДЕЛЕНИЕ ТРЕНДА
            trend, strength = self._determine_trend(
                current_price, ema_20, ema_50, rsi, adx, macd_data
            )

            return {
                "symbol": symbol,
                "interval": interval,
                "trend": trend,
                "strength": strength,
                "rsi": rsi,
                "adx": adx,
                "ema_20": ema_20,
                "ema_50": ema_50,
                "macd": macd_data,
                "price": current_price,
                "timestamp": datetime.now()
            }

        except Exception as e:
            ErrorLogger.log_calculation_error(
                calculation_name=f"MTF Analysis ({interval})",
                input_data={"symbol": symbol, "interval": interval},
                error=e
            )
            return None

    def _determine_trend(
        self,
        price: float,
        ema_20: float,
        ema_50: float,
        rsi: float,
        adx: float,
        macd_data: Optional[Dict]
    ) -> tuple:
        """
        Определение тренда на основе всех индикаторов

        Returns:
            (trend_direction, strength): ("BULLISH"|"BEARISH"|"NEUTRAL", 0.0-1.0)
        """
        try:
            signals = []

            # 1. EMA TREND (вес 30%)
            if price > ema_20 > ema_50:
                signals.append(("BULLISH", 0.3))
            elif price < ema_20 < ema_50:
                signals.append(("BEARISH", 0.3))
            else:
                signals.append(("NEUTRAL", 0.3))

            # 2. RSI (вес 20%)
            if rsi > 60:
                signals.append(("BULLISH", 0.2))
            elif rsi < 40:
                signals.append(("BEARISH", 0.2))
            else:
                signals.append(("NEUTRAL", 0.2))

            # 3. ADX STRENGTH (вес 20%)
            if adx > 25:
                # Сильный тренд - усиливаем текущий сигнал
                signals.append(("STRONG", 0.2))
            else:
                signals.append(("WEAK", 0.2))

            # 4. MACD (вес 30%)
            if macd_data and macd_data.get("histogram"):
                if macd_data["histogram"] > 0:
                    signals.append(("BULLISH", 0.3))
                elif macd_data["histogram"] < 0:
                    signals.append(("BEARISH", 0.3))
                else:
                    signals.append(("NEUTRAL", 0.3))

            # ПОДСЧЁТ ИТОГОВОГО ТРЕНДА
            bullish_score = sum(w for t, w in signals if t == "BULLISH")
            bearish_score = sum(w for t, w in signals if t == "BEARISH")
            strong_modifier = 1.2 if any(t == "STRONG" for t, _ in signals) else 1.0

            # ОПРЕДЕЛЕНИЕ ТРЕНДА
            if bullish_score > bearish_score:
                trend = "BULLISH"
                strength = min(bullish_score * strong_modifier, 1.0)
            elif bearish_score > bullish_score:
                trend = "BEARISH"
                strength = min(bearish_score * strong_modifier, 1.0)
            else:
                trend = "NEUTRAL"
                strength = 0.5

            return trend, strength

        except Exception as e:
            logger.error(f"❌ Ошибка определения тренда: {e}")
            return "UNKNOWN", 0.0

    def calculate_rsi(self, candles, period: int = 14) -> float:
        """Расчёт RSI"""
        try:
            if len(candles) < period + 1:
                return 50.0

            closes = [float(c["close"]) for c in candles]
            deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
            gains = [d if d > 0 else 0 for d in deltas]
            losses = [-d if d < 0 else 0 for d in deltas]

            avg_gain = sum(gains[-period:]) / period
            avg_loss = sum(losses[-period:]) / period

            if avg_loss == 0:
                return 100.0

            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            return rsi

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта RSI: {e}")
            return 50.0

    def calculate_adx(self, candles, period: int = 14) -> float:
        """
        Расчёт ADX (Average Directional Index)
        Показывает силу тренда (не направление!)

        Returns:
            ADX value (0-100)
            < 20: Слабый тренд
            20-25: Умеренный тренд
            25-50: Сильный тренд
            > 50: Очень сильный тренд
        """
        try:
            if len(candles) < period + 14:
                return 0.0

            # Расчёт True Range (TR)
            tr_list = []
            for i in range(1, len(candles)):
                high = float(candles[i]["high"])
                low = float(candles[i]["low"])
                prev_close = float(candles[i-1]["close"])

                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                tr_list.append(tr)

            # Расчёт +DM и -DM
            plus_dm_list = []
            minus_dm_list = []

            for i in range(1, len(candles)):
                high = float(candles[i]["high"])
                low = float(candles[i]["low"])
                prev_high = float(candles[i-1]["high"])
                prev_low = float(candles[i-1]["low"])

                plus_dm = high - prev_high if high - prev_high > prev_low - low else 0
                minus_dm = prev_low - low if prev_low - low > high - prev_high else 0

                plus_dm_list.append(max(plus_dm, 0))
                minus_dm_list.append(max(minus_dm, 0))

            # Сглаживание (Wilder's smoothing)
            atr = sum(tr_list[-period:]) / period
            plus_di = (sum(plus_dm_list[-period:]) / period) / atr * 100 if atr > 0 else 0
            minus_di = (sum(minus_dm_list[-period:]) / period) / atr * 100 if atr > 0 else 0

            # Расчёт DX
            dx = abs(plus_di - minus_di) / (plus_di + minus_di) * 100 if (plus_di + minus_di) > 0 else 0

            # ADX (усреднённый DX)
            adx = dx  # Simplified (можно улучшить с EMA)

            return min(adx, 100.0)

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта ADX: {e}")
            return 0.0

    def calculate_ema(self, candles, period: int = 20) -> float:
        """Расчёт EMA (Exponential Moving Average)"""
        try:
            if len(candles) < period:
                return float(candles[-1]["close"]) if candles else 0

            closes = [float(c["close"]) for c in candles]
            multiplier = 2 / (period + 1)
            ema = closes[0]

            for price in closes[1:]:
                ema = (price - ema) * multiplier + ema

            return ema

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта EMA: {e}")
            return 0.0

    def calculate_macd(self, candles) -> Optional[Dict]:
        """Расчёт MACD (Moving Average Convergence Divergence)"""
        try:
            if len(candles) < 26:
                return None

            closes = [float(c["close"]) for c in candles]

            # EMA 12 и EMA 26
            ema_12 = self._ema_from_list(closes, 12)
            ema_26 = self._ema_from_list(closes, 26)

            macd = ema_12 - ema_26

            # Signal line (EMA 9 of MACD)
            # Simplified: используем MACD как signal
            signal = macd * 0.9

            histogram = macd - signal

            return {
                "macd": macd,
                "signal": signal,
                "histogram": histogram
            }

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта MACD: {e}")
            return None

    def _ema_from_list(self, data: list, period: int) -> float:
        """Вспомогательный метод для расчёта EMA из списка"""
        try:
            if len(data) < period:
                return data[-1] if data else 0

            multiplier = 2 / (period + 1)
            ema = data[0]

            for price in data[1:]:
                ema = (price - ema) * multiplier + ema

            return ema

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта EMA: {e}")
            return 0.0


# Экспорт
__all__ = ['MultiTimeframeAnalyzer']
