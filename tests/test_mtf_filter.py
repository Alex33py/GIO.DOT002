#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест Multi-Timeframe Filter для GIO Crypto Bot v3.0
Проверяет работу мультитаймфреймового фильтра
"""

import asyncio
import sys
import os
from typing import Dict, List
import numpy as np

# Добавляем корневую директорию в PATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from filters.multi_tf_filter import MultiTimeframeFilter
from config.settings import logger


class MockMTFAnalyzer:
    """Mock класс для имитации MTFAnalyzer"""

    def __init__(self):
        self.klines_cache = {}

    async def get_klines(self, symbol: str, timeframe: str, limit: int = 200) -> List[Dict]:
        """Возвращает mock данные klines"""
        cache_key = f"{symbol}_{timeframe}"

        if cache_key in self.klines_cache:
            return self.klines_cache[cache_key]

        # Генерируем mock данные
        klines = self._generate_mock_klines(symbol, timeframe, limit)
        self.klines_cache[cache_key] = klines
        return klines

    def _generate_mock_klines(self, symbol: str, timeframe: str, count: int) -> List[Dict]:
        """Генерирует mock klines с трендом"""
        klines = []

        # Базовая цена
        if 'BTC' in symbol:
            base_price = 62000
            volatility = 500
        elif 'ETH' in symbol:
            base_price = 3000
            volatility = 50
        else:
            base_price = 100
            volatility = 5

        # Определяем тренд по таймфрейму
        if timeframe == '1h':
            trend = 1.002  # UP trend
        elif timeframe == '4h':
            trend = 1.003  # Stronger UP trend
        elif timeframe == '1d':
            trend = 0.998  # DOWN trend (для тестирования конфликта)
        else:
            trend = 1.0

        current_price = base_price

        for i in range(count):
            # Добавляем случайную волатильность
            noise = np.random.uniform(-volatility, volatility)
            current_price = current_price * trend + noise

            open_price = current_price
            high_price = current_price + abs(np.random.uniform(0, volatility))
            low_price = current_price - abs(np.random.uniform(0, volatility))
            close_price = current_price + np.random.uniform(-volatility/2, volatility/2)

            klines.append({
                'timestamp': 1728000000000 + i * 60000,
                'open': str(open_price),
                'high': str(high_price),
                'low': str(low_price),
                'close': str(close_price),
                'volume': str(np.random.uniform(100, 1000))
            })

        return klines


class MockBot:
    """Mock класс для имитации GIOCryptoBot"""

    def __init__(self):
        self.mtf_analyzer = MockMTFAnalyzer()
        logger.info("✅ MockBot инициализирован с MockMTFAnalyzer")


def print_separator(text: str = ""):
    """Печатает разделитель"""
    if text:
        print(f"\n{'=' * 70}")
        print(f"{text.center(70)}")
        print(f"{'=' * 70}")
    else:
        print(f"{'=' * 70}")


async def test_1_initialization():
    """Тест 1: Инициализация Multi-Timeframe Filter"""
    print_separator("ТЕСТ 1: Инициализация MTF Filter")

    try:
        bot = MockBot()

        mtf_filter = MultiTimeframeFilter(
            bot=bot,
            require_all_aligned=False,
            min_aligned_count=2,
            higher_tf_weight=2.0
        )

        assert mtf_filter is not None, "MTF Filter не создан!"
        assert mtf_filter.bot is not None, "Bot не передан в MTF Filter!"
        assert mtf_filter.min_aligned_count == 2, "min_aligned_count неправильный!"
        assert hasattr(mtf_filter, 'validate'), "Метод validate() отсутствует!"

        print("✅ MTF Filter успешно инициализирован")
        print(f"   - require_all_aligned: {mtf_filter.require_all_aligned}")
        print(f"   - min_aligned_count: {mtf_filter.min_aligned_count}")
        print(f"   - tf_weights: {mtf_filter.tf_weights}")
        print("\n✅ ТЕСТ 1 ПРОЙДЕН!\n")
        return mtf_filter, bot

    except Exception as e:
        print(f"❌ ТЕСТ 1 ПРОВАЛЕН: {e}")
        import traceback
        traceback.print_exc()
        return None, None


async def test_2_validate_method_signature(mtf_filter: MultiTimeframeFilter):
    """Тест 2: Проверка сигнатуры метода validate()"""
    print_separator("ТЕСТ 2: Проверка метода validate()")

    try:
        import inspect

        # Проверяем наличие метода
        assert hasattr(mtf_filter, 'validate'), "Метод validate() отсутствует!"

        # Проверяем сигнатуру
        sig = inspect.signature(mtf_filter.validate)
        params = list(sig.parameters.keys())

        print(f"📋 Параметры метода validate(): {params}")

        assert 'symbol' in params, "Параметр 'symbol' отсутствует!"
        assert 'direction' in params, "Параметр 'direction' отсутствует!"

        # Проверяем что метод асинхронный
        assert inspect.iscoroutinefunction(mtf_filter.validate), "validate() должен быть async!"

        print("✅ Метод validate() имеет правильную сигнатуру")
        print("✅ Метод validate() является асинхронным")
        print("\n✅ ТЕСТ 2 ПРОЙДЕН!\n")
        return True

    except Exception as e:
        print(f"❌ ТЕСТ 2 ПРОВАЛЕН: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_3_validate_long_signal(mtf_filter: MultiTimeframeFilter):
    """Тест 3: Валидация LONG сигнала"""
    print_separator("ТЕСТ 3: Валидация LONG сигнала")

    try:
        symbol = 'BTCUSDT'
        direction = 'LONG'

        print(f"🔍 Проверка сигнала: {symbol} {direction}")

        # Вызываем метод validate
        is_valid, trends, reason = await mtf_filter.validate(
            symbol=symbol,
            direction=direction,
            timeframes=['1h', '4h', '1d'],
            min_agreement=2
        )

        print(f"\n📊 Результат валидации:")
        print(f"   - Валидность: {is_valid}")
        print(f"   - Тренды: {trends}")
        print(f"   - Причина: {reason}")

        # Проверяем возвращаемые значения
        assert isinstance(is_valid, bool), "is_valid должен быть bool!"
        assert isinstance(trends, dict), "trends должен быть dict!"
        assert isinstance(reason, str), "reason должен быть str!"

        # Проверяем наличие трендов для всех TF
        assert '1h' in trends, "Тренд для 1h отсутствует!"
        assert '4h' in trends, "Тренд для 4h отсутствует!"

        print("\n✅ ТЕСТ 3 ПРОЙДЕН!\n")
        return True

    except Exception as e:
        print(f"❌ ТЕСТ 3 ПРОВАЛЕН: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_4_validate_short_signal(mtf_filter: MultiTimeframeFilter):
    """Тест 4: Валидация SHORT сигнала"""
    print_separator("ТЕСТ 4: Валидация SHORT сигнала")

    try:
        symbol = 'ETHUSDT'
        direction = 'SHORT'

        print(f"🔍 Проверка сигнала: {symbol} {direction}")

        is_valid, trends, reason = await mtf_filter.validate(
            symbol=symbol,
            direction=direction,
            timeframes=['1h', '4h'],
            min_agreement=1
        )

        print(f"\n📊 Результат валидации:")
        print(f"   - Валидность: {is_valid}")
        print(f"   - Тренды: {trends}")
        print(f"   - Причина: {reason}")

        assert isinstance(is_valid, bool), "is_valid должен быть bool!"
        assert isinstance(trends, dict), "trends должен быть dict!"

        print("\n✅ ТЕСТ 4 ПРОЙДЕН!\n")
        return True

    except Exception as e:
        print(f"❌ ТЕСТ 4 ПРОВАЛЕН: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_5_conflicting_trends(mtf_filter: MultiTimeframeFilter):
    """Тест 5: Проверка конфликтующих трендов"""
    print_separator("ТЕСТ 5: Конфликтующие тренды")

    try:
        symbol = 'BTCUSDT'
        direction = 'LONG'

        print(f"🔍 Проверка сигнала с конфликтующими трендами: {symbol} {direction}")
        print("   (1h UP, 4h UP, 1d DOWN - должно быть валидно с min_agreement=2)")

        is_valid, trends, reason = await mtf_filter.validate(
            symbol=symbol,
            direction=direction,
            timeframes=['1h', '4h', '1d'],
            min_agreement=2  # Требуем только 2 из 3
        )

        print(f"\n📊 Результат валидации:")
        print(f"   - Валидность: {is_valid}")
        print(f"   - Тренды: {trends}")
        print(f"   - Причина: {reason}")

        # Подсчитываем UP тренды
        up_count = sum(1 for t in trends.values() if t == 'UP')
        print(f"   - Количество UP трендов: {up_count}/3")

        assert isinstance(is_valid, bool), "is_valid должен быть bool!"

        # Если 2 или больше UP, должно быть валидно
        if up_count >= 2:
            assert is_valid == True, f"Сигнал должен быть валиден при {up_count} UP трендах!"
            print(f"   ✅ Правильно: {up_count} UP тренда >= 2 (min_agreement)")

        print("\n✅ ТЕСТ 5 ПРОЙДЕН!\n")
        return True

    except Exception as e:
        print(f"❌ ТЕСТ 5 ПРОВАЛЕН: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_6_trend_strength(mtf_filter: MultiTimeframeFilter):
    """Тест 6: Расчет силы тренда"""
    print_separator("ТЕСТ 6: Расчет силы тренда")

    try:
        # Получаем MTF данные
        symbol = 'BTCUSDT'
        mtf_data = await mtf_filter._get_mtf_data(symbol, ['1h', '4h', '1d'])

        print(f"📊 MTF данные для {symbol}:")
        for tf, data in mtf_data.items():
            trend = data.get('trend', 'NEUTRAL')
            strength = data.get('strength', 0.0)
            print(f"   - {tf}: {trend} (strength: {strength:.2f})")

        # Рассчитываем общую силу тренда
        overall_strength = mtf_filter.get_trend_strength(mtf_data)

        print(f"\n💪 Общая сила тренда: {overall_strength:.2f}")

        assert isinstance(overall_strength, float), "Сила тренда должна быть float!"
        assert 0.0 <= overall_strength <= 1.0, "Сила тренда должна быть в диапазоне [0, 1]!"

        print("\n✅ ТЕСТ 6 ПРОЙДЕН!\n")
        return True

    except Exception as e:
        print(f"❌ ТЕСТ 6 ПРОВАЛЕН: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_7_cache_functionality(mtf_filter: MultiTimeframeFilter):
    """Тест 7: Проверка кэширования"""
    print_separator("ТЕСТ 7: Кэширование данных")

    try:
        symbol = 'BTCUSDT'

        # Первый вызов - данные должны быть получены из источника
        print("🔄 Первый вызов (без кэша)...")
        is_valid1, trends1, reason1 = await mtf_filter.validate(
            symbol=symbol,
            direction='LONG'
        )

        # Второй вызов - должны использоваться данные из кэша
        print("📦 Второй вызов (с кэшем)...")
        is_valid2, trends2, reason2 = await mtf_filter.validate(
            symbol=symbol,
            direction='LONG'
        )

        print(f"\n📊 Сравнение результатов:")
        print(f"   - Первый вызов: {trends1}")
        print(f"   - Второй вызов: {trends2}")

        # Результаты должны совпадать
        assert trends1 == trends2, "Результаты с кэшем не совпадают!"

        # Проверяем что кэш работает
        assert symbol in mtf_filter.mtf_cache, "Кэш не заполнен!"
        print(f"   ✅ Кэш работает: {symbol} в кэше")

        # Очищаем кэш
        mtf_filter.clear_cache(symbol)
        assert symbol not in mtf_filter.mtf_cache, "Кэш не очищен!"
        print(f"   ✅ Кэш очищен для {symbol}")

        print("\n✅ ТЕСТ 7 ПРОЙДЕН!\n")
        return True

    except Exception as e:
        print(f"❌ ТЕСТ 7 ПРОВАЛЕН: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_8_get_trend_summary(mtf_filter: MultiTimeframeFilter):
    """Тест 8: Получение сводки по трендам"""
    print_separator("ТЕСТ 8: Сводка по трендам")

    try:
        symbol = 'BTCUSDT'

        summary = await mtf_filter.get_trend_summary(symbol)

        print(f"📋 Сводка по трендам для {symbol}:")
        print(f"   - Symbol: {summary.get('symbol')}")
        print(f"   - Trends: {summary.get('trends')}")
        print(f"   - Dominant Trend: {summary.get('dominant_trend')}")
        print(f"   - Agreement Score: {summary.get('agreement_score', 0):.2f}")
        print(f"   - Overall Strength: {summary.get('overall_strength', 0):.2f}")

        assert 'symbol' in summary, "symbol отсутствует в сводке!"
        assert 'trends' in summary, "trends отсутствуют в сводке!"
        assert 'dominant_trend' in summary, "dominant_trend отсутствует в сводке!"

        print("\n✅ ТЕСТ 8 ПРОЙДЕН!\n")
        return True

    except Exception as e:
        print(f"❌ ТЕСТ 8 ПРОВАЛЕН: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_9_invalid_direction(mtf_filter: MultiTimeframeFilter):
    """Тест 9: Неправильное направление сигнала"""
    print_separator("ТЕСТ 9: Неправильное направление")

    try:
        symbol = 'BTCUSDT'
        direction = 'INVALID'  # Неправильное направление

        print(f"🔍 Проверка с неправильным направлением: {direction}")

        is_valid, trends, reason = await mtf_filter.validate(
            symbol=symbol,
            direction=direction
        )

        print(f"\n📊 Результат валидации:")
        print(f"   - Валидность: {is_valid}")
        print(f"   - Причина: {reason}")

        # Должен быть не валиден
        assert is_valid == False, "Сигнал с неправильным направлением должен быть невалиден!"
        assert 'Неверное направление' in reason or 'Invalid' in reason, "Причина должна указывать на ошибку!"

        print("   ✅ Правильно: неправильное направление отклонено")

        print("\n✅ ТЕСТ 9 ПРОЙДЕН!\n")
        return True

    except Exception as e:
        print(f"❌ ТЕСТ 9 ПРОВАЛЕН: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Запуск всех тестов"""
    print_separator("🚀 ТЕСТИРОВАНИЕ MULTI-TIMEFRAME FILTER")

    results = []

    # Тест 1: Инициализация
    mtf_filter, bot = await test_1_initialization()
    if mtf_filter is None:
        print("\n❌ Критическая ошибка: MTF Filter не инициализирован!")
        return
    results.append(mtf_filter is not None)

    # Тест 2: Сигнатура метода validate()
    result = await test_2_validate_method_signature(mtf_filter)
    results.append(result)

    # Тест 3: LONG сигнал
    result = await test_3_validate_long_signal(mtf_filter)
    results.append(result)

    # Тест 4: SHORT сигнал
    result = await test_4_validate_short_signal(mtf_filter)
    results.append(result)

    # Тест 5: Конфликтующие тренды
    result = await test_5_conflicting_trends(mtf_filter)
    results.append(result)

    # Тест 6: Сила тренда
    result = await test_6_trend_strength(mtf_filter)
    results.append(result)

    # Тест 7: Кэширование
    result = await test_7_cache_functionality(mtf_filter)
    results.append(result)

    # Тест 8: Сводка по трендам
    result = await test_8_get_trend_summary(mtf_filter)
    results.append(result)

    # Тест 9: Неправильное направление
    result = await test_9_invalid_direction(mtf_filter)
    results.append(result)

    # Итоговые результаты
    print_separator("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ")

    passed = sum(results)
    total = len(results)

    print(f"\n✅ Пройдено тестов: {passed}/{total}")
    print(f"❌ Провалено тестов: {total - passed}/{total}")
    print(f"📊 Процент успеха: {(passed/total)*100:.1f}%\n")

    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Multi-Timeframe Filter работает корректно!")
    else:
        print("⚠️ Некоторые тесты провалены. Проверьте логи выше.")

    print_separator()


if __name__ == '__main__':
    # Запускаем тесты
    asyncio.run(run_all_tests())
