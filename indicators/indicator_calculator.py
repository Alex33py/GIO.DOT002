#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Indicator Calculator - Простой калькулятор индикаторов
"""

from typing import Dict, Optional
import pandas as pd
import numpy as np
from config.settings import logger


class IndicatorCalculator:
    """Калькулятор технических индикаторов"""

    def __init__(self):
        logger.info("✅ IndicatorCalculator инициализирован")

    def calculate_indicators(
        self, symbol: str, timeframe: str = "15m", df: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        Рассчитать индикаторы для символа

        Args:
            symbol: Торговая пара
            timeframe: Таймфрейм
            df: DataFrame с OHLCV данными (опционально)

        Returns:
            Dict с индикаторами
        """
        try:
            # Если нет данных - возвращаем пустой dict
            if df is None or df.empty:
                logger.warning(
                    f"⚠️ Нет данных для расчёта индикаторов {symbol} {timeframe}"
                )
                return {}

            # Простые индикаторы
            indicators = {
                "rsi": self._calculate_rsi(df),
                "macd": self._calculate_macd(df),
                "ema": self._calculate_ema(df),
                "volume_avg": (
                    float(df["volume"].rolling(20).mean().iloc[-1])
                    if "volume" in df.columns
                    else 0
                ),
                "price": float(df["close"].iloc[-1]) if "close" in df.columns else 0,
            }

            return indicators

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта индикаторов {symbol}: {e}")
            return {}

    def _calculate_rsi(self, df: pd.DataFrame, period: int = 14) -> float:
        """Рассчитать RSI"""
        try:
            delta = df["close"].diff()
            gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))
            return float(rsi.iloc[-1])
        except:
            return 50.0  # Нейтральное значение

    def _calculate_macd(self, df: pd.DataFrame) -> Dict:
        """Рассчитать MACD"""
        try:
            ema_12 = df["close"].ewm(span=12, adjust=False).mean()
            ema_26 = df["close"].ewm(span=26, adjust=False).mean()
            macd_line = ema_12 - ema_26
            signal_line = macd_line.ewm(span=9, adjust=False).mean()
            histogram = macd_line - signal_line

            return {
                "macd": float(macd_line.iloc[-1]),
                "signal": float(signal_line.iloc[-1]),
                "histogram": float(histogram.iloc[-1]),
            }
        except:
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}

    def _calculate_ema(self, df: pd.DataFrame, periods: list = [20, 50, 200]) -> Dict:
        """Рассчитать EMA"""
        try:
            emas = {}
            for period in periods:
                ema = df["close"].ewm(span=period, adjust=False).mean()
                emas[f"ema_{period}"] = float(ema.iloc[-1])
            return emas
        except:
            return {f"ema_{p}": 0.0 for p in periods}
    def calculate_rsi(self, df, period: int = 14) -> float:
        """
        Рассчитать RSI

        Args:
            df: DataFrame ИЛИ список словарей с ключом 'close'
            period: Период RSI

        Returns:
            float: Значение RSI (0-100)
        """
        try:
            # ✅ Если передан список словарей - конвертируем в DataFrame
            if isinstance(df, list):
                if not df:
                    return 50.0
                # Создаем DataFrame из списка свечей
                df = pd.DataFrame(df)

            if df is None or df.empty or 'close' not in df.columns:
                return 50.0

            # Конвертируем в числа
            close_prices = pd.to_numeric(df['close'], errors='coerce')

            # Убираем NaN
            close_prices = close_prices.dropna()

            if len(close_prices) < period + 1:
                return 50.0

            # Расчёт изменений цены
            delta = close_prices.diff()

            # Разделяем на прибыль и убыток
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)

            # Сглаживание по Wilder (EMA)
            avg_gain = gain.ewm(span=period, adjust=False).mean()
            avg_loss = loss.ewm(span=period, adjust=False).mean()

            # Избегаем деления на ноль
            rs = avg_gain / avg_loss.replace(0, 0.000001)

            # Формула RSI
            rsi = 100 - (100 / (1 + rs))

            return round(float(rsi.iloc[-1]), 2)

        except Exception as e:
            logger.error(f"❌ calculate_rsi: {e}")
            return 50.0


    def calculate_macd(self, df, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict:
        """
        Рассчитать MACD

        Args:
            df: DataFrame ИЛИ список словарей с ключом 'close'
            fast: Период быстрой EMA
            slow: Период медленной EMA
            signal: Период сигнальной линии

        Returns:
            Dict: {'macd': float, 'signal': float, 'histogram': float}
        """
        try:
            # ✅ Если передан список словарей - конвертируем в DataFrame
            if isinstance(df, list):
                if not df:
                    return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}
                # Создаем DataFrame из списка свечей
                df = pd.DataFrame(df)

            if df is None or df.empty or 'close' not in df.columns:
                return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}

            # Конвертируем в числа
            close_prices = pd.to_numeric(df['close'], errors='coerce')

            # Убираем NaN
            close_prices = close_prices.dropna()

            if len(close_prices) < slow + signal:
                return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}

            # Расчёт EMA
            ema_fast = close_prices.ewm(span=fast, adjust=False).mean()
            ema_slow = close_prices.ewm(span=slow, adjust=False).mean()

            # MACD линия
            macd_line = ema_fast - ema_slow

            # Signal линия
            signal_line = macd_line.ewm(span=signal, adjust=False).mean()

            # Histogram
            histogram = macd_line - signal_line

            return {
                "macd": round(float(macd_line.iloc[-1]), 4),
                "signal": round(float(signal_line.iloc[-1]), 4),
                "histogram": round(float(histogram.iloc[-1]), 4)
            }

        except Exception as e:
            logger.error(f"❌ calculate_macd: {e}")
            return {"macd": 0.0, "signal": 0.0, "histogram": 0.0}

    def calculate_ema(self, df, period: int = 20) -> float:
        """
        Рассчитать EMA (Exponential Moving Average)

        Args:
            df: DataFrame ИЛИ список словарей с ключом 'close'
            period: Период EMA

        Returns:
            float: Значение EMA
        """
        try:
            # ✅ Если передан список словарей - конвертируем в DataFrame
            if isinstance(df, list):
                if not df:
                    return 0.0
                # Создаем DataFrame из списка свечей
                df = pd.DataFrame(df)

            if df is None or df.empty or 'close' not in df.columns:
                return 0.0

            # Конвертируем в числа
            close_prices = pd.to_numeric(df['close'], errors='coerce')

            # Убираем NaN
            close_prices = close_prices.dropna()

            if len(close_prices) < period:
                return float(close_prices.iloc[-1]) if len(close_prices) > 0 else 0.0

            # Расчёт EMA
            ema = close_prices.ewm(span=period, adjust=False).mean()

            return round(float(ema.iloc[-1]), 2)

        except Exception as e:
            logger.error(f"❌ calculate_ema: {e}")
            return 0.0
