# -*- coding: utf-8 -*-
"""
Модуль валидации данных перед сохранением в БД
Проверяет на NaN, None, некорректные значения
"""

import numpy as np
import pandas as pd
from typing import Any, Dict, List, Optional

from config.settings import logger


class DataValidator:
    """Валидация рыночных данных и индикаторов"""

    @staticmethod
    def validate_price(price: Any, field_name: str = "price") -> Optional[float]:
        """
        Валидация цены

        Параметры:
            price: Значение для проверки
            field_name: Название поля для логирования

        Возвращает:
            Валидную цену или None
        """
        try:
            if price is None:
                logger.warning(f"⚠️ {field_name} = None")
                return None

            if isinstance(price, (int, float)):
                if np.isnan(price) or np.isinf(price):
                    logger.warning(f"⚠️ {field_name} = NaN/Inf")
                    return None

                if price <= 0:
                    logger.warning(f"⚠️ {field_name} <= 0: {price}")
                    return None

                return float(price)

            # Попытка конвертации
            price_float = float(price)
            if np.isnan(price_float) or np.isinf(price_float) or price_float <= 0:
                return None

            return price_float

        except (ValueError, TypeError) as e:
            logger.warning(f"⚠️ Ошибка валидации {field_name}: {e}")
            return None

    @staticmethod
    def validate_volume(volume: Any, field_name: str = "volume") -> Optional[float]:
        """Валидация объёма"""
        try:
            if volume is None:
                return None

            if isinstance(volume, (int, float)):
                if np.isnan(volume) or np.isinf(volume):
                    logger.warning(f"⚠️ {field_name} = NaN/Inf")
                    return None

                if volume < 0:
                    logger.warning(f"⚠️ {field_name} < 0: {volume}")
                    return None

                return float(volume)

            volume_float = float(volume)
            if np.isnan(volume_float) or np.isinf(volume_float) or volume_float < 0:
                return None

            return volume_float

        except (ValueError, TypeError):
            return None

    @staticmethod
    def validate_candle(candle: Dict) -> bool:
        """
        Валидация свечи OHLCV

        Параметры:
            candle: Словарь с данными свечи

        Возвращает:
            True если свеча валидна
        """
        try:
            required_fields = ['open', 'high', 'low', 'close', 'volume']

            for field in required_fields:
                if field not in candle:
                    logger.warning(f"⚠️ Свеча: отсутствует поле '{field}'")
                    return False

            # Валидация цен
            open_price = DataValidator.validate_price(candle['open'], 'open')
            high_price = DataValidator.validate_price(candle['high'], 'high')
            low_price = DataValidator.validate_price(candle['low'], 'low')
            close_price = DataValidator.validate_price(candle['close'], 'close')

            if not all([open_price, high_price, low_price, close_price]):
                return False

            # Проверка логичности
            if high_price < low_price:
                logger.warning("⚠️ Свеча: high < low")
                return False

            if high_price < max(open_price, close_price):
                logger.warning("⚠️ Свеча: high < max(open, close)")
                return False

            if low_price > min(open_price, close_price):
                logger.warning("⚠️ Свеча: low > min(open, close)")
                return False

            # Валидация объёма
            volume = DataValidator.validate_volume(candle['volume'], 'volume')
            if volume is None:
                return False

            return True

        except Exception as e:
            logger.warning(f"⚠️ Ошибка валидации свечи: {e}")
            return False

    @staticmethod
    def validate_indicator(value: Any, name: str, min_val: float = None, max_val: float = None) -> Optional[float]:
        """
        Валидация значения индикатора

        Параметры:
            value: Значение индикатора
            name: Название индикатора
            min_val: Минимальное допустимое значение
            max_val: Максимальное допустимое значение

        Возвращает:
            Валидное значение или None
        """
        try:
            if value is None:
                return None

            if isinstance(value, (int, float)):
                if np.isnan(value) or np.isinf(value):
                    logger.warning(f"⚠️ {name} = NaN/Inf")
                    return None

                value_float = float(value)
            else:
                value_float = float(value)
                if np.isnan(value_float) or np.isinf(value_float):
                    return None

            # Проверка диапазона
            if min_val is not None and value_float < min_val:
                logger.warning(f"⚠️ {name} < {min_val}: {value_float}")
                return None

            if max_val is not None and value_float > max_val:
                logger.warning(f"⚠️ {name} > {max_val}: {value_float}")
                return None

            return value_float

        except (ValueError, TypeError) as e:
            logger.warning(f"⚠️ Ошибка валидации {name}: {e}")
            return None

    @staticmethod
    def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """
        Очистка DataFrame от некорректных данных

        Параметры:
            df: Исходный DataFrame

        Возвращает:
            Очищенный DataFrame
        """
        try:
            if df is None or df.empty:
                return df

            # Удаляем строки с NaN в критических полях
            critical_cols = ['open', 'high', 'low', 'close', 'volume']
            existing_cols = [col for col in critical_cols if col in df.columns]

            if existing_cols:
                df = df.dropna(subset=existing_cols)

            # Заменяем inf на NaN и удаляем
            df = df.replace([np.inf, -np.inf], np.nan)
            df = df.dropna()

            # Проверяем логичность OHLC
            if all(col in df.columns for col in ['open', 'high', 'low', 'close']):
                # Удаляем строки где high < low
                df = df[df['high'] >= df['low']]

                # Удаляем строки где high < max(open, close)
                df = df[df['high'] >= df[['open', 'close']].max(axis=1)]

                # Удаляем строки где low > min(open, close)
                df = df[df['low'] <= df[['open', 'close']].min(axis=1)]

            logger.debug(f"✅ DataFrame очищен: {len(df)} валидных строк")

            return df

        except Exception as e:
            logger.error(f"❌ Ошибка очистки DataFrame: {e}")
            return df
    @staticmethod
    def validate_candles_list(candles: List[Dict], min_length: int = 1) -> bool:
        """
        Валидация списка свечей

        Args:
            candles: Список свечей
            min_length: Минимальное количество свечей

        Returns:
            True если все свечи валидны
        """
        try:
            if candles is None:
                logger.error("❌ Candles list is None")
                return False

            if not isinstance(candles, list):
                logger.error(f"❌ Candles должен быть list, получен {type(candles)}")
                return False

            if len(candles) < min_length:
                logger.error(f"❌ Недостаточно свечей: {len(candles)} < {min_length}")
                return False

            # Проверяем каждую свечу
            invalid_count = 0
            for i, candle in enumerate(candles):
                if not DataValidator.validate_candle(candle):
                    invalid_count += 1
                    if invalid_count > len(candles) * 0.1:  # Больше 10% невалидных
                        logger.error(f"❌ Слишком много невалидных свечей: {invalid_count}/{len(candles)}")
                        return False

            if invalid_count > 0:
                logger.warning(f"⚠️ Найдено {invalid_count} невалидных свечей из {len(candles)}")

            return True

        except Exception as e:
            logger.error(f"❌ Ошибка валидации списка свечей: {e}")
            return False

    @staticmethod
    def validate_orderbook(orderbook: Dict) -> bool:
        """
        Валидация orderbook данных

        Args:
            orderbook: Стакан заявок (bids + asks)

        Returns:
            True если данные валидны
        """
        try:
            if orderbook is None:
                logger.error("❌ Orderbook is None")
                return False

            if not isinstance(orderbook, dict):
                logger.error(f"❌ Orderbook должен быть dict, получен {type(orderbook)}")
                return False

            # Проверка наличия bids и asks
            if "bids" not in orderbook or "asks" not in orderbook:
                logger.error("❌ Orderbook должен содержать 'bids' и 'asks'")
                return False

            bids = orderbook["bids"]
            asks = orderbook["asks"]

            # Проверка типов
            if not isinstance(bids, list) or not isinstance(asks, list):
                logger.error("❌ Bids и asks должны быть списками")
                return False

            # Проверка на пустоту
            if len(bids) == 0 or len(asks) == 0:
                logger.error("❌ Bids или asks пустые")
                return False

            # Проверка первых 5 уровней
            for i, bid in enumerate(bids[:5]):
                if not isinstance(bid, (list, tuple)) or len(bid) < 2:
                    logger.error(f"❌ Bid {i} имеет неверную структуру")
                    return False

                price = DataValidator.validate_price(bid[0], f"bid[{i}].price")
                volume = DataValidator.validate_volume(bid[1], f"bid[{i}].volume")

                if price is None or volume is None:
                    return False

            for i, ask in enumerate(asks[:5]):
                if not isinstance(ask, (list, tuple)) or len(ask) < 2:
                    logger.error(f"❌ Ask {i} имеет неверную структуру")
                    return False

                price = DataValidator.validate_price(ask[0], f"ask[{i}].price")
                volume = DataValidator.validate_volume(ask[1], f"ask[{i}].volume")

                if price is None or volume is None:
                    return False

            logger.debug(f"✅ Валидация orderbook успешна (bids={len(bids)}, asks={len(asks)})")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка валидации orderbook: {e}")
            return False

    @staticmethod
    def validate_trades(trades: List[Dict]) -> bool:
        """
        Валидация списка сделок (aggTrades)

        Args:
            trades: Список сделок

        Returns:
            True если данные валидны
        """
        try:
            if trades is None:
                logger.error("❌ Trades is None")
                return False

            if not isinstance(trades, list):
                logger.error(f"❌ Trades должен быть list, получен {type(trades)}")
                return False

            if len(trades) == 0:
                logger.error("❌ Trades пустой")
                return False

            required_fields = ["price", "size", "side", "timestamp"]

            invalid_count = 0
            for i, trade in enumerate(trades):
                if not isinstance(trade, dict):
                    invalid_count += 1
                    continue

                # Проверка обязательных полей
                missing_fields = [f for f in required_fields if f not in trade]
                if missing_fields:
                    logger.warning(f"⚠️ Trade {i}: отсутствуют поля {missing_fields}")
                    invalid_count += 1
                    continue

                # Валидация price и size
                if DataValidator.validate_price(trade["price"]) is None:
                    invalid_count += 1
                    continue

                if DataValidator.validate_volume(trade["size"]) is None:
                    invalid_count += 1
                    continue

            # Допускаем до 5% невалидных trades
            if invalid_count > len(trades) * 0.05:
                logger.error(f"❌ Слишком много невалидных trades: {invalid_count}/{len(trades)}")
                return False

            if invalid_count > 0:
                logger.warning(f"⚠️ Найдено {invalid_count} невалидных trades из {len(trades)}")

            logger.debug(f"✅ Валидация {len(trades)} trades успешна")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка валидации trades: {e}")
            return False

    @staticmethod
    def validate_rsi(rsi: float) -> bool:
        """Валидация RSI (должен быть 0-100)"""
        result = DataValidator.validate_indicator(rsi, "RSI", min_val=0, max_val=100)
        return result is not None

    @staticmethod
    def validate_percentage(value: float, name: str) -> bool:
        """Валидация процента (-100 до 100)"""
        result = DataValidator.validate_indicator(value, name, min_val=-100, max_val=100)
        return result is not None


# Экспорт
__all__ = ['DataValidator']
