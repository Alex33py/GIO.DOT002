# -*- coding: utf-8 -*-
"""
Fallback значения и безопасный расчёт индикаторов
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from config.settings import logger

# Fallback значения для индикаторов
INDICATOR_DEFAULTS = {
    'rsi': 50.0,  # Нейтральный RSI
    'macd': 0.0,
    'macd_signal': 0.0,
    'macd_histogram': 0.0,
    'atr': 0.0,
    'ema_12': None,  # None = вычислить из цены
    'ema_26': None,
    'ema_50': None,
    'ema_200': None,
    'bb_upper': None,
    'bb_middle': None,
    'bb_lower': None,
    'volume_sma': 0.0,
}


def safe_calculate_rsi(prices: List[float], period: int = 14) -> float:
    """
    Безопасный расчёт RSI с fallback
    
    Args:
        prices: Список цен
        period: Период RSI
    
    Returns:
        RSI значение или fallback (50.0)
    """
    try:
        if not prices or len(prices) < period + 1:
            logger.warning(f"⚠️ Недостаточно данных для RSI (нужно {period+1}, есть {len(prices)})")
            return INDICATOR_DEFAULTS['rsi']
        
        # Проверка на NaN
        if any(pd.isna(p) or p is None for p in prices):
            logger.warning("⚠️ RSI: обнаружены NaN в ценах")
            return INDICATOR_DEFAULTS['rsi']
        
        # Расчёт через pandas
        df = pd.DataFrame({'close': prices})
        delta = df['close'].diff()
        
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        result = float(rsi.iloc[-1])
        
        # Проверка валидности
        if pd.isna(result) or not (0 <= result <= 100):
            logger.warning(f"⚠️ RSI некорректен: {result}, использован fallback")
            return INDICATOR_DEFAULTS['rsi']
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Ошибка расчёта RSI: {e}, использован fallback")
        return INDICATOR_DEFAULTS['rsi']


def safe_calculate_macd(prices: List[float], 
                        fast: int = 12, 
                        slow: int = 26, 
                        signal: int = 9) -> Dict[str, float]:
    """
    Безопасный расчёт MACD с fallback
    
    Args:
        prices: Список цен
        fast: Быстрая EMA
        slow: Медленная EMA
        signal: Сигнальная линия
    
    Returns:
        Словарь с MACD, signal, histogram
    """
    try:
        if not prices or len(prices) < slow + signal:
            logger.warning(f"⚠️ Недостаточно данных для MACD (нужно {slow+signal}, есть {len(prices)})")
            return {
                'macd': INDICATOR_DEFAULTS['macd'],
                'macd_signal': INDICATOR_DEFAULTS['macd_signal'],
                'macd_histogram': INDICATOR_DEFAULTS['macd_histogram']
            }
        
        # Проверка на NaN
        if any(pd.isna(p) or p is None for p in prices):
            logger.warning("⚠️ MACD: обнаружены NaN в ценах")
            return {
                'macd': INDICATOR_DEFAULTS['macd'],
                'macd_signal': INDICATOR_DEFAULTS['macd_signal'],
                'macd_histogram': INDICATOR_DEFAULTS['macd_histogram']
            }
        
        # Расчёт через pandas
        df = pd.DataFrame({'close': prices})
        
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        result = {
            'macd': float(macd_line.iloc[-1]),
            'macd_signal': float(signal_line.iloc[-1]),
            'macd_histogram': float(histogram.iloc[-1])
        }
        
        # Проверка валидности
        if any(pd.isna(v) for v in result.values()):
            logger.warning("⚠️ MACD содержит NaN, использован fallback")
            return {
                'macd': INDICATOR_DEFAULTS['macd'],
                'macd_signal': INDICATOR_DEFAULTS['macd_signal'],
                'macd_histogram': INDICATOR_DEFAULTS['macd_histogram']
            }
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Ошибка расчёта MACD: {e}, использован fallback")
        return {
            'macd': INDICATOR_DEFAULTS['macd'],
            'macd_signal': INDICATOR_DEFAULTS['macd_signal'],
            'macd_histogram': INDICATOR_DEFAULTS['macd_histogram']
        }


def safe_calculate_atr(candles: List[Dict], period: int = 14) -> float:
    """
    Безопасный расчёт ATR с fallback
    
    Args:
        candles: Список свечей (high, low, close)
        period: Период ATR
    
    Returns:
        ATR значение или fallback (0.0)
    """
    try:
        if not candles or len(candles) < period + 1:
            logger.warning(f"⚠️ Недостаточно данных для ATR (нужно {period+1}, есть {len(candles)})")
            return INDICATOR_DEFAULTS['atr']
        
        # Проверка структуры данных
        required_fields = ['high', 'low', 'close']
        if not all(field in candles[0] for field in required_fields):
            logger.warning(f"⚠️ ATR: отсутствуют обязательные поля")
            return INDICATOR_DEFAULTS['atr']
        
        # Извлекаем данные
        highs = [c['high'] for c in candles]
        lows = [c['low'] for c in candles]
        closes = [c['close'] for c in candles]
        
        # Проверка на NaN
        if any(pd.isna(v) or v is None for arr in [highs, lows, closes] for v in arr):
            logger.warning("⚠️ ATR: обнаружены NaN в данных")
            return INDICATOR_DEFAULTS['atr']
        
        # Расчёт через pandas
        df = pd.DataFrame({
            'high': highs,
            'low': lows,
            'close': closes
        })
        
        # True Range
        df['tr1'] = df['high'] - df['low']
        df['tr2'] = abs(df['high'] - df['close'].shift())
        df['tr3'] = abs(df['low'] - df['close'].shift())
        df['tr'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
        
        # ATR
        atr = df['tr'].rolling(window=period).mean()
        
        result = float(atr.iloc[-1])
        
        # Проверка валидности
        if pd.isna(result) or result < 0:
            logger.warning(f"⚠️ ATR некорректен: {result}, использован fallback")
            return INDICATOR_DEFAULTS['atr']
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Ошибка расчёта ATR: {e}, использован fallback")
        return INDICATOR_DEFAULTS['atr']


def safe_calculate_ema(prices: List[float], period: int) -> Optional[float]:
    """
    Безопасный расчёт EMA с fallback
    
    Args:
        prices: Список цен
        period: Период EMA
    
    Returns:
        EMA значение или None (использовать текущую цену)
    """
    try:
        if not prices or len(prices) < period:
            logger.warning(f"⚠️ Недостаточно данных для EMA{period} (нужно {period}, есть {len(prices)})")
            return None
        
        # Проверка на NaN
        if any(pd.isna(p) or p is None for p in prices):
            logger.warning(f"⚠️ EMA{period}: обнаружены NaN в ценах")
            return None
        
        # Расчёт через pandas
        df = pd.DataFrame({'close': prices})
        ema = df['close'].ewm(span=period, adjust=False).mean()
        
        result = float(ema.iloc[-1])
        
        # Проверка валидности
        if pd.isna(result) or result <= 0:
            logger.warning(f"⚠️ EMA{period} некорректна: {result}, использован fallback")
            return None
        
        return result
        
    except Exception as e:
        logger.error(f"❌ Ошибка расчёта EMA{period}: {e}, использован fallback")
        return None


def validate_and_fix_indicators(indicators: Dict[str, Any]) -> Dict[str, Any]:
    """
    Валидация и исправление индикаторов
    
    Args:
        indicators: Словарь индикаторов
    
    Returns:
        Исправленный словарь индикаторов
    """
    try:
        fixed = {}
        
        for key, value in indicators.items():
            # Проверка на NaN/None
            if pd.isna(value) or value is None:
                # Используем fallback если есть
                if key in INDICATOR_DEFAULTS:
                    fallback = INDICATOR_DEFAULTS[key]
                    fixed[key] = fallback
                    logger.warning(f"⚠️ Индикатор {key} заменён на fallback: {fallback}")
                else:
                    # Для неизвестных индикаторов используем 0
                    fixed[key] = 0.0
                    logger.warning(f"⚠️ Индикатор {key} заменён на 0.0")
            
            # Проверка на бесконечность
            elif isinstance(value, (int, float)) and np.isinf(value):
                fixed[key] = 0.0
                logger.warning(f"⚠️ Индикатор {key} был бесконечным, заменён на 0.0")
            
            # Валидные значения
            else:
                fixed[key] = value
        
        return fixed
        
    except Exception as e:
        logger.error(f"❌ Ошибка валидации индикаторов: {e}")
        return indicators


def get_indicator_quality_score(indicators: Dict[str, Any]) -> float:
    """
    Оценка качества индикаторов (0.0 - 1.0)
    
    Args:
        indicators: Словарь индикаторов
    
    Returns:
        Качество индикаторов (0.0 - 1.0)
    """
    try:
        if not indicators:
            return 0.0
        
        score = 0.0
        total_weight = 0.0
        
        # Веса индикаторов
        weights = {
            'rsi': 1.0,
            'macd': 1.0,
            'macd_histogram': 0.8,
            'atr': 1.0,
            'ema_12': 0.5,
            'ema_26': 0.5,
            'ema_50': 0.7,
            'ema_200': 0.7,
        }
        
        for key, weight in weights.items():
            if key in indicators:
                value = indicators[key]
                total_weight += weight
                
                # Проверяем что значение не fallback
                if value != INDICATOR_DEFAULTS.get(key):
                    score += weight
        
        if total_weight == 0:
            return 0.0
        
        quality = score / total_weight
        
        logger.debug(f"📊 Качество индикаторов: {quality:.1%}")
        
        return quality
        
    except Exception as e:
        logger.error(f"❌ Ошибка оценки качества индикаторов: {e}")
        return 0.0


# Экспорт
__all__ = [
    'safe_calculate_rsi',
    'safe_calculate_macd',
    'safe_calculate_atr',
    'safe_calculate_ema',
    'validate_and_fix_indicators',
    'get_indicator_quality_score',
    'INDICATOR_DEFAULTS'
]
