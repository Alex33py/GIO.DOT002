#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестирование производительности оптимизаций
КРИТЕРИЙ 3.1 - Performance Tests
"""

import asyncio
import time
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from connectors.bybit_connector import EnhancedBybitConnector
from utils.rate_limiter import get_rate_limiter
from utils.cache_manager import get_cache_manager
from config.settings import logger


class PerformanceTester:
    """Тестер производительности оптимизаций"""

    def __init__(self):
        self.connector = None
        self.cache = get_cache_manager()
        self.rate_limiter = get_rate_limiter()

    async def setup(self):
        """Инициализация"""
        self.connector = EnhancedBybitConnector()

        # Создаём HTTP сессию
        if not self.connector.session:
            import aiohttp
            self.connector.session = aiohttp.ClientSession()

        logger.info("✅ Тестер инициализирован")


    async def test_ticker_cache(self, symbol: str = "BTCUSDT", runs: int = 10):
        """Тест кэширования ticker"""
        print("\n" + "="*60)
        print("🧪 ТЕСТ 1: TICKER CACHING")
        print("="*60)

        # Очистим кэш для чистого теста
        await self.cache.clear(namespace="ticker")

        # Первый запрос (без кэша)
        start = time.time()
        ticker1 = await self.connector._get_ticker(symbol)
        time1 = (time.time() - start) * 1000

        await asyncio.sleep(0.1)

        # Последующие запросы (из кэша)
        cache_times = []
        for i in range(runs):
            start = time.time()
            ticker = await self.connector._get_ticker(symbol)
            cache_time = (time.time() - start) * 1000
            cache_times.append(cache_time)
            await asyncio.sleep(0.01)

        avg_cache_time = sum(cache_times) / len(cache_times)

        # Результаты
        print(f"\n📊 Результаты для {symbol}:")
        print(f"├─ Первый запрос (БЕЗ кэша): {time1:.2f}ms")
        print(f"├─ Средний запрос (С кэшем):  {avg_cache_time:.2f}ms")

        # ✅ ИСПРАВЛЕНО: Защита от деления на 0
        if avg_cache_time > 0.01:
            speedup = time1 / avg_cache_time
            print(f"└─ Ускорение: {speedup:.1f}x")
        else:
            speedup = 1000.0  # Считаем что >1000x быстрее
            print(f"└─ Ускорение: >1000x (кэш мгновенный!)")

        # Статистика кэша
        stats = self.cache.get_stats()
        print(f"\n💾 Cache Stats:")
        print(f"├─ Hit Rate:  {stats['hit_rate']:.1f}%")
        print(f"├─ Hits:      {stats['hits']}")
        print(f"├─ Misses:    {stats['misses']}")
        print(f"└─ Cache Size: {stats['cache_size']}")

        return speedup


    async def test_orderbook_optimization(self, symbol: str = "BTCUSDT"):
        """
        Тест оптимизации orderbook (50 vs 200 уровней)

        Args:
            symbol: Тестовый символ
        """
        print("\n" + "="*60)
        print("🧪 ТЕСТ 2: ORDERBOOK OPTIMIZATION")
        print("="*60)

        # Очистим кэш
        await self.cache.clear(namespace="orderbook")

        # Тест с 200 уровнями
        start = time.time()
        ob_200 = await self.connector._get_orderbook(symbol, limit=200)
        time_200 = (time.time() - start) * 1000

        await asyncio.sleep(0.5)
        await self.cache.clear(namespace="orderbook")

        # Тест с 50 уровнями
        start = time.time()
        ob_50 = await self.connector._get_orderbook(symbol, limit=50)
        time_50 = (time.time() - start) * 1000

        # Размеры данных
        import json
        size_200 = len(json.dumps(ob_200)) if ob_200 else 0
        size_50 = len(json.dumps(ob_50)) if ob_50 else 0

        # Результаты
        print(f"\n📊 Результаты для {symbol}:")
        print(f"├─ 200 уровней: {time_200:.2f}ms ({size_200/1024:.1f}KB)")
        print(f"├─ 50 уровней:  {time_50:.2f}ms ({size_50/1024:.1f}KB)")
        print(f"└─ Ускорение: {time_200/time_50:.1f}x")
        print(f"└─ Экономия данных: {(1 - size_50/size_200)*100:.1f}%")

        return time_200 / time_50

    async def test_rate_limiting(self, symbol: str = "BTCUSDT", requests: int = 20):
        """
        Тест Rate Limiting

        Args:
            symbol: Тестовый символ
            requests: Количество запросов
        """
        print("\n" + "="*60)
        print("🧪 ТЕСТ 3: RATE LIMITING")
        print("="*60)

        # Очистим кэш чтобы были реальные API запросы
        await self.cache.clear()

        start_time = time.time()
        errors = 0
        success = 0

        for i in range(requests):
            try:
                ticker = await self.connector._get_ticker(symbol)
                if ticker:
                    success += 1
                else:
                    errors += 1
            except Exception as e:
                errors += 1
                logger.error(f"Ошибка в запросе {i+1}: {e}")

        total_time = time.time() - start_time

        # Статистика Rate Limiter
        rl_stats = self.rate_limiter.get_all_stats()

        print(f"\n📊 Результаты {requests} запросов:")
        print(f"├─ Успешно:    {success}")
        print(f"├─ Ошибки:     {errors}")
        print(f"├─ Общее время: {total_time:.2f}s")
        print(f"└─ Среднее время: {total_time/requests*1000:.2f}ms/запрос")

        print(f"\n⚡ Rate Limiter Stats:")
        for endpoint, stats in rl_stats.items():
            print(f"\n{endpoint}:")
            print(f"├─ Requests/sec: {stats['requests_last_second']}/{stats['limit_per_second']}")
            print(f"└─ Utilization:  {stats['utilization']:.1f}%")

        return errors == 0

    async def test_batch_klines(self, symbol: str = "BTCUSDT"):
        """
        Тест батчинга для klines

        Args:
            symbol: Тестовый символ
        """
        print("\n" + "="*60)
        print("🧪 ТЕСТ 4: BATCH KLINES")
        print("="*60)

        timeframes = ['60', '240', 'D']

        # Последовательные запросы
        start = time.time()
        for tf in timeframes:
            await self.connector.get_klines(symbol, tf, limit=50)
        sequential_time = time.time() - start

        await asyncio.sleep(1)

        # Батчинг (параллельные запросы)
        start = time.time()
        batch_result = await self.connector.get_klines_batch(
            symbol,
            timeframes,
            limits=[50, 50, 50]
        )
        batch_time = time.time() - start

        print(f"\n📊 Результаты для {symbol}:")
        print(f"├─ Последовательно: {sequential_time:.2f}s")
        print(f"├─ Батчинг:         {batch_time:.2f}s")
        print(f"└─ Ускорение:       {sequential_time/batch_time:.1f}x")

        return sequential_time / batch_time

    async def run_all_tests(self):
        """Запустить все тесты"""
        print("\n" + "🚀"*30)
        print("ТЕСТИРОВАНИЕ ОПТИМИЗАЦИЙ - КРИТЕРИЙ 3.1")
        print("🚀"*30)

        try:
            await self.setup()

            # Тест 1: Cache
            speedup_cache = await self.test_ticker_cache()

            # Тест 2: Orderbook
            speedup_orderbook = await self.test_orderbook_optimization()

            # Тест 3: Rate Limiting
            no_errors = await self.test_rate_limiting()

            # Тест 4: Batch
            speedup_batch = await self.test_batch_klines()

            # Итоговые результаты
            print("\n" + "="*60)
            print("📊 ИТОГОВЫЕ РЕЗУЛЬТАТЫ")
            print("="*60)
            print(f"\n✅ Ticker Cache:     {speedup_cache:.1f}x быстрее")
            print(f"✅ Orderbook Opt:    {speedup_orderbook:.1f}x быстрее")
            print(f"✅ Rate Limiting:    {'Без ошибок' if no_errors else 'Есть ошибки'}")
            print(f"✅ Batch Klines:     {speedup_batch:.1f}x быстрее")

            total_speedup = (speedup_cache + speedup_orderbook + speedup_batch) / 3
            print(f"\n🎯 ОБЩЕЕ УСКОРЕНИЕ: ~{total_speedup:.1f}x")

            print("\n" + "="*60)
            print("✅ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ!")
            print("="*60 + "\n")

        except Exception as e:
            logger.error(f"❌ Ошибка в тестировании: {e}")
            import traceback
            traceback.print_exc()

        finally:
            if self.connector:
                await self.connector.close()


async def main():
    """Главная функция"""
    tester = PerformanceTester()
    await tester.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())
