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
