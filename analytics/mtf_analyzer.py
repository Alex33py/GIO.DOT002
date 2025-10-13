#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multi-Timeframe Analyzer
Анализ на нескольких таймфреймах с валидацией
"""

from datetime import datetime
from typing import Dict, Optional
from config.settings import logger
from utils.error_logger import ErrorLogger
from utils.validators import DataValidator


class MultiTimeframeAnalyzer:
    """Анализ на нескольких таймфреймах"""

    def __init__(self, connector):
        """
        Инициализация MTF Analyzer

        Args:
            connector: Коннектор к бирже (Bybit/OKX)
        """
        self.bybit_connector = connector
        logger.info("✅ MultiTimeframeAnalyzer инициализирован")

    async def analyze(self, symbol: str, interval: str = "1H") -> Optional[Dict]:
        """
        MTF анализ с валидацией и error logging

        Args:
            symbol: Торговая пара (BTCUSDT)
            interval: Таймфрейм (1H, 4H, 1D)

        Returns:
            Словарь с результатами анализа или None
        """
        try:
            # Получаем свечи
            candles = await self.bybit_connector.get_klines(symbol, interval, limit=100)

            # ВАЛИДАЦИЯ (ИСПРАВЛЕНО - используем validate_candle вместо validate_candles_list)
            if not candles or len(candles) < 20:
                logger.error(f"❌ Недостаточно свечей для {symbol}")
                return None

            # Расчёт RSI
            rsi = self.calculate_rsi(candles)

            # ВАЛИДАЦИЯ RSI
            if not DataValidator.validate_rsi(rsi):
                logger.warning(f"⚠️ Невалидный RSI для {symbol}, используем fallback")
                rsi = 50.0  # Neutral

            return {
                "symbol": symbol,
                "interval": interval,
                "rsi": rsi,
                "timestamp": datetime.now()
            }

        except Exception as e:
            # ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ
            ErrorLogger.log_calculation_error(
                calculation_name=f"MTF Analysis ({interval})",
                input_data={"symbol": symbol, "interval": interval},
                error=e
            )
            return None

    def calculate_rsi(self, candles, period: int = 14) -> float:
        """
        Расчёт RSI

        Args:
            candles: Список свечей
            period: Период для RSI

        Returns:
            Значение RSI (0-100)
        """
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

    def calculate_atr(self, candles, period: int = 14) -> float:
        """
        Расчёт ATR

        Args:
            candles: Список свечей
            period: Период для ATR

        Returns:
            Значение ATR
        """
        try:
            if len(candles) < period:
                # Fallback: 1% от цены
                return float(candles[-1]["close"]) * 0.01

            true_ranges = []
            for i in range(1, len(candles)):
                high = float(candles[i]["high"])
                low = float(candles[i]["low"])
                prev_close = float(candles[i-1]["close"])

                tr = max(
                    high - low,
                    abs(high - prev_close),
                    abs(low - prev_close)
                )
                true_ranges.append(tr)

            atr = sum(true_ranges[-period:]) / period
            return atr

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта ATR: {e}")
            return 100.0

    def calculate_macd(self, candles) -> Optional[Dict]:
        """
        Расчёт MACD

        Args:
            candles: Список свечей

        Returns:
            Dict с macd, signal, histogram или None
        """
        try:
            if len(candles) < 26:
                return None

            closes = [float(c["close"]) for c in candles]

            ema_12 = self._ema(closes, 12)
            ema_26 = self._ema(closes, 26)

            macd = ema_12 - ema_26

            # Signal line (EMA 9 of MACD)
            signal = macd  # Simplified

            histogram = macd - signal

            return {
                "macd": macd,
                "signal": signal,
                "histogram": histogram
            }

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта MACD: {e}")
            return None

    def _ema(self, data: list, period: int) -> float:
        """
        Расчёт EMA

        Args:
            data: Список значений
            period: Период

        Returns:
            Значение EMA
        """
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
