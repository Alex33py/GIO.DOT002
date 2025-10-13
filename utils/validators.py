# -*- coding: utf-8 -*-
"""
Валидаторы данных для GIO Crypto Bot
Проверка корректности рыночных данных, свечей, индикаторов
"""

import math  # ✅ ДОБАВЛЕН ИМПОРТ
import pandas as pd
from typing import Dict, List, Optional, Any
from datetime import datetime
from config.settings import logger


class DataValidator:
    """Валидатор рыночных данных"""

    @staticmethod
    def validate_price(price: float, symbol: str, min_price: float = 0.0001) -> bool:
        """
        Валидация цены

        Args:
            price: Цена для проверки
            symbol: Торговая пара
            min_price: Минимальная допустимая цена

        Returns:
            True если цена валидна
        """
        if price is None:
            logger.error(f"❌ {symbol}: Цена = None")
            return False

        if pd.isna(price):
            logger.error(f"❌ {symbol}: Цена = NaN")
            return False

        try:
            price_float = float(price)
        except (TypeError, ValueError):
            logger.error(f"❌ {symbol}: Цена не число: {price}")
            return False

        if price_float <= min_price:
            logger.error(f"❌ {symbol}: Цена <= {min_price}: {price_float}")
            return False

        # Проверка разумных диапазонов для популярных пар
        if symbol == 'BTCUSDT':
            if price_float < 1000 or price_float > 1_000_000:
                logger.error(f"❌ {symbol}: Подозрительная цена: ${price_float:,.2f}")
                return False
        elif symbol == 'ETHUSDT':
            if price_float < 100 or price_float > 50_000:
                logger.error(f"❌ {symbol}: Подозрительная цена: ${price_float:,.2f}")
                return False

        return True

    @staticmethod
    def validate_volume(volume: float, symbol: str) -> bool:
        """
        Валидация объёма

        Args:
            volume: Объём для проверки
            symbol: Торговая пара

        Returns:
            True если объём валиден
        """
        if volume is None:
            logger.warning(f"⚠️ {symbol}: Объём = None")
            return False

        if pd.isna(volume):
            logger.warning(f"⚠️ {symbol}: Объём = NaN")
            return False

        try:
            volume_float = float(volume)
        except (TypeError, ValueError):
            logger.error(f"❌ {symbol}: Объём не число: {volume}")
            return False

        if volume_float < 0:
            logger.error(f"❌ {symbol}: Объём < 0: {volume_float}")
            return False

        return True

    @staticmethod
    def validate_candle(candle: Dict) -> bool:
        """
        Полная валидация свечи

        Args:
            candle: Словарь со свечой {'open', 'high', 'low', 'close', 'volume'}

        Returns:
            True если свеча валидна
        """
        required_fields = ['open', 'high', 'low', 'close', 'volume']

        # Проверка наличия всех полей
        for field in required_fields:
            if field not in candle:
                logger.error(f"❌ Свеча без поля {field}: {candle}")
                return False

            value = candle[field]

            # Проверка None
            if value is None:
                logger.error(f"❌ Свеча с None в {field}")
                return False

            # Проверка NaN
            if pd.isna(value):
                logger.error(f"❌ Свеча с NaN в {field}")
                return False

            # Проверка типа
            try:
                float(value)
            except (TypeError, ValueError):
                logger.error(f"❌ Свеча с некорректным {field}: {value}")
                return False

            # Проверка положительности
            if float(value) <= 0:
                logger.error(f"❌ Свеча с отрицательным {field}: {value}")
                return False

        # Проверка OHLC логики
        try:
            o = float(candle['open'])
            h = float(candle['high'])
            l = float(candle['low'])
            c = float(candle['close'])

            # High должен быть максимумом
            if not (h >= o and h >= c and h >= l):
                logger.error(f"❌ Свеча: High не максимум (O={o}, H={h}, L={l}, C={c})")
                return False

            # Low должен быть минимумом
            if not (l <= o and l <= c and l <= h):
                logger.error(f"❌ Свеча: Low не минимум (O={o}, H={h}, L={l}, C={c})")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка валидации OHLC логики: {e}")
            return False

        return True

    @staticmethod
    def validate_indicator(value: float, name: str, min_val: float = -100, max_val: float = 100) -> bool:
        """
        Валидация индикатора

        Args:
            value: Значение индикатора
            name: Название индикатора
            min_val: Минимальное допустимое значение
            max_val: Максимальное допустимое значение

        Returns:
            True если индикатор валиден
        """
        if value is None:
            logger.warning(f"⚠️ Индикатор {name} = None")
            return False

        if pd.isna(value):
            logger.warning(f"⚠️ Индикатор {name} = NaN")
            return False

        try:
            value_float = float(value)
        except (TypeError, ValueError):
            logger.error(f"❌ Индикатор {name} не число: {value}")
            return False

        if not (min_val <= value_float <= max_val):
            logger.warning(f"⚠️ Индикатор {name} вне диапазона: {value_float} (допустимо {min_val}-{max_val})")
            return False

        return True

    @staticmethod
    def validate_rsi(rsi: float) -> bool:
        """Валидация RSI (0-100)"""
        return DataValidator.validate_indicator(rsi, 'RSI', 0, 100)

    @staticmethod
    def validate_atr(atr: float, min_val: float = 0) -> bool:
        """Валидация ATR (> 0)"""
        if atr is None or pd.isna(atr):
            return False
        try:
            return float(atr) > min_val
        except:
            return False

    @staticmethod
    def validate_market_data(data: Dict, symbol: str = 'UNKNOWN') -> bool:
        """
        Полная валидация рыночных данных

        Args:
            data: Словарь с рыночными данными
            symbol: Торговая пара

        Returns:
            True если все данные валидны
        """
        valid = True

        # Проверка цены
        if 'price' in data:
            if not DataValidator.validate_price(data['price'], symbol):
                valid = False

        # Проверка объёма
        if 'volume_24h' in data:
            if not DataValidator.validate_volume(data['volume_24h'], symbol):
                valid = False

        # Проверка индикаторов
        if 'rsi' in data:
            if not DataValidator.validate_rsi(data['rsi']):
                valid = False

        if 'atr' in data:
            if not DataValidator.validate_atr(data['atr']):
                valid = False

        if 'macd' in data:
            if not DataValidator.validate_indicator(data['macd'], 'MACD', -1000, 1000):
                valid = False

        return valid

    @staticmethod
    def sanitize_candles(candles: List[Dict]) -> List[Dict]:
        """
        Очистка списка свечей от невалидных

        Args:
            candles: Список свечей

        Returns:
            Список валидных свечей
        """
        valid_candles = []
        invalid_count = 0

        for candle in candles:
            if DataValidator.validate_candle(candle):
                valid_candles.append(candle)
            else:
                invalid_count += 1

        if invalid_count > 0:
            logger.warning(f"⚠️ Отброшено {invalid_count} невалидных свечей из {len(candles)}")

        return valid_candles


# ========================================
# ДОПОЛНИТЕЛЬНЫЕ ВАЛИДАТОРЫ
# ========================================

def validate_candle_data(candle: Dict) -> bool:
    """Алиас для обратной совместимости с тестами"""
    return DataValidator.validate_candle(candle)


def validate_news_data(news_item: Dict) -> bool:
    """
    Валидация новостного элемента

    Args:
        news_item: Словарь с новостными данными

    Returns:
        True если данные валидны
    """
    try:
        # Проверяем обязательные поля
        required_fields = ['title', 'source']

        for field in required_fields:
            if field not in news_item:
                logger.warning(f"⚠️ Отсутствует поле {field} в новости")
                return False

        # Проверяем что title не пустой
        if not news_item.get('title') or not isinstance(news_item.get('title'), str):
            return False

        # Проверяем sentiment если есть
        if 'sentiment' in news_item:
            sentiment = news_item['sentiment']
            if not isinstance(sentiment, (int, float)):
                return False
            if not -1.0 <= sentiment <= 1.0:
                return False

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка валидации новостей: {e}")
        return False


def validate_trade_data(trade: Dict) -> bool:
    """
    Валидация данных трейда

    Args:
        trade: Словарь с данными трейда

    Returns:
        True если данные валидны
    """
    try:
        required_fields = ['price', 'quantity']

        for field in required_fields:
            if field not in trade:
                return False

        price = float(trade.get('price', 0))
        quantity = float(trade.get('quantity', 0))

        if price <= 0 or quantity <= 0:
            return False

        return True

    except (ValueError, TypeError):
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка валидации трейда: {e}")
        return False


def validate_orderbook_data(orderbook: Dict) -> bool:
    """
    Валидация данных ордербука

    Args:
        orderbook: Словарь с данными ордербука (bids, asks)

    Returns:
        True если данные валидны
    """
    try:
        if 'bids' not in orderbook or 'asks' not in orderbook:
            return False

        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not isinstance(bids, list) or not isinstance(asks, list):
            return False

        # Проверяем что есть хотя бы один bid и ask
        if len(bids) == 0 or len(asks) == 0:
            return False

        # Проверяем формат первого bid/ask
        for bid in bids[:3]:  # Проверяем первые 3
            if not isinstance(bid, (list, tuple, dict)) or len(bid) < 2:
                return False

            if isinstance(bid, dict):
                price = float(bid.get('price', 0))
                quantity = float(bid.get('size', 0))
            else:
                price = float(bid[0])
                quantity = float(bid[1])

            if price <= 0 or quantity <= 0:
                return False

        for ask in asks[:3]:  # Проверяем первые 3
            if not isinstance(ask, (list, tuple, dict)) or len(ask) < 2:
                return False

            if isinstance(ask, dict):
                price = float(ask.get('price', 0))
                quantity = float(ask.get('size', 0))
            else:
                price = float(ask[0])
                quantity = float(ask[1])

            if price <= 0 or quantity <= 0:
                return False

        return True

    except (ValueError, TypeError):
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка валидации ордербука: {e}")
        return False


def validate_market_data_completeness(market_data: Dict, required_fields: List[str] = None) -> bool:
    """
    Проверка полноты рыночных данных

    Args:
        market_data: Словарь с рыночными данными
        required_fields: Список обязательных полей (опционально)

    Returns:
        True если все обязательные поля присутствуют и валидны
    """
    try:
        if not market_data or not isinstance(market_data, dict):
            return False

        # Если не указаны обязательные поля, используем базовый набор
        if required_fields is None:
            required_fields = ['price', 'volume']

        # Проверяем наличие обязательных полей
        for field in required_fields:
            if field not in market_data:
                logger.warning(f"⚠️ Отсутствует обязательное поле: {field}")
                return False

            value = market_data[field]

            # Проверяем что значение не None и не NaN
            if value is None:
                logger.warning(f"⚠️ Поле {field} = None")
                return False

            # Для числовых полей проверяем на NaN
            if isinstance(value, (int, float)):
                if math.isnan(value) or math.isinf(value):
                    logger.warning(f"⚠️ Поле {field} = NaN/Inf")
                    return False

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка проверки полноты данных: {e}")
        return False


def validate_signal_data(signal: Dict) -> bool:
    """
    Валидация данных торгового сигнала

    Args:
        signal: Словарь с данными сигнала

    Returns:
        True если сигнал валиден
    """
    try:
        # Обязательные поля сигнала
        required_fields = ['symbol', 'direction', 'entry_price', 'stop_loss']

        for field in required_fields:
            if field not in signal:
                logger.warning(f"⚠️ Отсутствует обязательное поле сигнала: {field}")
                return False

        # Проверка направления
        direction = str(signal.get('direction', '')).upper()
        if direction not in ['LONG', 'SHORT']:
            logger.warning(f"⚠️ Некорректное направление: {direction}")
            return False

        # Проверка цен
        entry_price = float(signal.get('entry_price', 0))
        stop_loss = float(signal.get('stop_loss', 0))

        if entry_price <= 0:
            logger.warning(f"⚠️ Некорректная цена входа: {entry_price}")
            return False

        if stop_loss <= 0:
            logger.warning(f"⚠️ Некорректный стоп-лосс: {stop_loss}")
            return False

        # Проверка логики SL
        if direction == 'LONG' and stop_loss >= entry_price:
            logger.warning(f"⚠️ LONG: SL должен быть ниже цены входа")
            return False

        if direction == 'SHORT' and stop_loss <= entry_price:
            logger.warning(f"⚠️ SHORT: SL должен быть выше цены входа")
            return False

        # Проверка TP если есть
        if 'take_profit' in signal:
            tp = float(signal.get('take_profit', 0))

            if tp <= 0:
                logger.warning(f"⚠️ Некорректный take profit: {tp}")
                return False

            if direction == 'LONG' and tp <= entry_price:
                logger.warning(f"⚠️ LONG: TP должен быть выше цены входа")
                return False

            if direction == 'SHORT' and tp >= entry_price:
                logger.warning(f"⚠️ SHORT: TP должен быть ниже цены входа")
                return False

        return True

    except (ValueError, TypeError) as e:
        logger.warning(f"⚠️ Ошибка валидации типов в сигнале: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка валидации сигнала: {e}")
        return False


def validate_indicator_data(indicator: Dict) -> bool:
    """
    Валидация данных индикатора (для обратной совместимости с тестами)

    Args:
        indicator: Словарь с данными индикатора {'name': str, 'value': float}

    Returns:
        True если индикатор валиден
    """
    try:
        if 'name' not in indicator or 'value' not in indicator:
            return False

        name = indicator['name']
        value = indicator['value']

        if not isinstance(name, str) or len(name) == 0:
            return False

        if value is None or pd.isna(value):
            return False

        # Попытка преобразовать в float
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            # Если не число, проверяем что это строка или bool
            return isinstance(value, (str, bool))

    except Exception as e:
        logger.error(f"❌ Ошибка валидации индикатора: {e}")
        return False


def validate_scenario_data(scenario: Dict) -> bool:
    """
    Валидация данных сценария

    Args:
        scenario: Словарь с данными сценария

    Returns:
        True если сценарий валиден
    """
    try:
        # Обязательные поля сценария
        required_fields = ['id', 'name', 'conditions']

        for field in required_fields:
            if field not in scenario:
                logger.warning(f"⚠️ Отсутствует обязательное поле сценария: {field}")
                return False

        # Проверка ID
        scenario_id = scenario.get('id')
        if not scenario_id or not isinstance(scenario_id, (str, int)):
            logger.warning(f"⚠️ Некорректный ID сценария: {scenario_id}")
            return False

        # Проверка имени
        name = scenario.get('name')
        if not name or not isinstance(name, str):
            logger.warning(f"⚠️ Некорректное имя сценария: {name}")
            return False

        # Проверка условий
        conditions = scenario.get('conditions')
        if not isinstance(conditions, dict):
            logger.warning(f"⚠️ Условия сценария должны быть словарём")
            return False

        # Проверка направления если есть
        if 'direction' in scenario:
            direction = scenario.get('direction', '').lower()
            if direction not in ['long', 'short', 'both', 'any']:
                logger.warning(f"⚠️ Некорректное направление сценария: {direction}")
                return False

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка валидации сценария: {e}")
        return False


def validate_json_data(data: Any, expected_type: type = dict) -> bool:
    """
    Валидация JSON данных

    Args:
        data: Данные для проверки
        expected_type: Ожидаемый тип данных (dict, list и т.д.)

    Returns:
        True если данные валидны
    """
    try:
        # Проверка что данные не None
        if data is None:
            logger.warning("⚠️ JSON данные = None")
            return False

        # Проверка типа
        if not isinstance(data, expected_type):
            logger.warning(f"⚠️ Ожидался тип {expected_type.__name__}, получен {type(data).__name__}")
            return False

        # Для словарей и списков проверяем что не пустые
        if isinstance(data, (dict, list)) and len(data) == 0:
            logger.warning("⚠️ JSON данные пустые")
            return False

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка валидации JSON: {e}")
        return False


# Экспорт всех функций
__all__ = [
    'DataValidator',
    'validate_candle_data',
    'validate_news_data',
    'validate_trade_data',
    'validate_orderbook_data',
    'validate_market_data_completeness',
    'validate_signal_data',
    'validate_indicator_data',
    'validate_scenario_data',
    'validate_json_data'
]
