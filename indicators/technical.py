import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Optional, Tuple
from utils.helpers import validate_candle_data

logger = logging.getLogger(__name__)


class AdvancedTechnicalIndicators:
    """Продвинутые технические индикаторы с оптимизацией для криптовалют"""

    @staticmethod
    def calculate_atr(candles: List[Dict], period: int = 14) -> Optional[float]:
        """Расчет Average True Range (ATR)"""
        try:
            if len(candles) < period + 1:
                return None

            df = pd.DataFrame(candles)
            if df.empty or len(df) < period + 1:
                return None

            # Преобразуем в числовой тип
            high = pd.to_numeric(df["high"], errors='coerce')
            low = pd.to_numeric(df["low"], errors='coerce')
            close = pd.to_numeric(df["close"], errors='coerce')

            # Проверяем на NaN
            if high.isna().any() or low.isna().any() or close.isna().any():
                return None

            # True Range
            tr1 = high - low
            tr2 = abs(high - close.shift(1))
            tr3 = abs(low - close.shift(1))

            true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

            # ATR как простая скользящая средняя TR
            atr = true_range.rolling(window=period, min_periods=period).mean().iloc[-1]

            return float(atr) if not pd.isna(atr) else None

        except Exception as e:
            logger.error(f"Ошибка расчета ATR: {e}")
            return None

    @staticmethod
    def calculate_rsi(candles: List[Dict], period: int = 14) -> Optional[float]:
        """Расчет Relative Strength Index (RSI) с правильной обработкой типов"""
        try:
            if len(candles) < period + 1:
                return None

            df = pd.DataFrame(candles)
            if df.empty or len(df) < period + 1:
                return None

            # Преобразуем в числовой тип с проверкой
            close = pd.to_numeric(df["close"], errors='coerce')

            if close.isna().any():
                logger.warning("Найдены NaN значения в данных close")
                return None

            # Вычисляем разности (delta)
            delta = close.diff()

            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: явно преобразуем delta в float64
            delta = pd.to_numeric(delta, errors='coerce')

            # Разделяем прибыли и убытки с правильной обработкой типов
            # Используем numpy операции вместо pandas where для лучшего контроля типов
            gain_values = np.where(delta > 0, delta, 0)
            loss_values = np.where(delta < 0, -delta, 0)

            # Создаем pandas Series с явным указанием типа
            gain = pd.Series(gain_values, index=delta.index, dtype='float64')
            loss = pd.Series(loss_values, index=delta.index, dtype='float64')

            # Рассчитываем скользящие средние
            avg_gain = gain.rolling(window=period, min_periods=period).mean()
            avg_loss = loss.rolling(window=period, min_periods=period).mean()

            # Избегаем деления на ноль
            avg_loss_safe = avg_loss.replace(0, np.nan)
            rs = avg_gain / avg_loss_safe

            # Рассчитываем RSI
            rsi = 100 - (100 / (1 + rs))

            result = rsi.iloc[-1]
            return float(result) if not pd.isna(result) else None

        except Exception as e:
            logger.error(f"Ошибка расчета RSI: {e}")
            return None

    @staticmethod
    def calculate_macd(candles: List[Dict], fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, Optional[float]]:
        """Расчет MACD с сигнальной линией и гистограммой"""
        try:
            if len(candles) < slow + signal:
                return {"macd": None, "signal_line": None, "histogram": None}

            df = pd.DataFrame(candles)
            if df.empty or len(df) < slow + signal:
                return {"macd": None, "signal_line": None, "histogram": None}

            # Преобразуем в числовой тип
            close = pd.to_numeric(df["close"], errors='coerce')

            if close.isna().any():
                return {"macd": None, "signal_line": None, "histogram": None}

            # Экспоненциальные скользящие средние
            ema_fast = close.ewm(span=fast, min_periods=fast).mean()
            ema_slow = close.ewm(span=slow, min_periods=slow).mean()

            # MACD линия
            macd_line = ema_fast - ema_slow

            # Сигнальная линия
            signal_line = macd_line.ewm(span=signal, min_periods=signal).mean()

            # Гистограмма
            histogram = macd_line - signal_line

            return {
                "macd": float(macd_line.iloc[-1]) if not pd.isna(macd_line.iloc[-1]) else None,
                "signal_line": float(signal_line.iloc[-1]) if not pd.isna(signal_line.iloc[-1]) else None,
                "histogram": float(histogram.iloc[-1]) if not pd.isna(histogram.iloc[-1]) else None
            }

        except Exception as e:
            logger.error(f"Ошибка расчета MACD: {e}")
            return {"macd": None, "signal_line": None, "histogram": None}

    # ... остальной код
