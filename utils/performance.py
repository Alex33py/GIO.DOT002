# -*- coding: utf-8 -*-
"""
Утилиты для оптимизации производительности
"""

import asyncio
import time
import functools
from typing import Callable, Any
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from config.settings import logger

# Глобальные executor'ы
_process_executor = None
_thread_executor = None

def get_process_executor(max_workers: int = 4) -> ProcessPoolExecutor:
    """Получение ProcessPoolExecutor (для CPU-bound задач)"""
    global _process_executor
    if _process_executor is None:
        _process_executor = ProcessPoolExecutor(max_workers=max_workers)
    return _process_executor

def get_thread_executor(max_workers: int = 10) -> ThreadPoolExecutor:
    """Получение ThreadPoolExecutor (для I/O-bound задач)"""
    global _thread_executor
    if _thread_executor is None:
        _thread_executor = ThreadPoolExecutor(max_workers=max_workers)
    return _thread_executor

def async_timed(func: Callable) -> Callable:
    """Декоратор для измерения времени выполнения async функций"""
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = await func(*args, **kwargs)
        elapsed = time.perf_counter() - start

        logger.debug(f"⏱️ {func.__name__} выполнена за {elapsed:.3f}с")
        return result

    return wrapper

def timed(func: Callable) -> Callable:
    """Декоратор для измерения времени выполнения sync функций"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start

        logger.debug(f"⏱️ {func.__name__} выполнена за {elapsed:.3f}с")
        return result

    return wrapper

async def run_in_executor(func: Callable, *args, use_process: bool = False, **kwargs) -> Any:
    """
    Запуск блокирующей функции в executor

    Args:
        func: Функция для выполнения
        *args: Позиционные аргументы
        use_process: True для CPU-bound (ProcessPoolExecutor), False для I/O-bound
        **kwargs: Именованные аргументы
    """
    loop = asyncio.get_event_loop()

    if use_process:
        executor = get_process_executor()
    else:
        executor = get_thread_executor()

    # functools.partial для передачи kwargs
    partial_func = functools.partial(func, *args, **kwargs)

    return await loop.run_in_executor(executor, partial_func)

class BatchProcessor:
    """Процессор для пакетной обработки данных"""

    def __init__(self, batch_size: int = 100, flush_interval: float = 5.0):
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self.batches = {}
        self.last_flush = {}

    async def add_item(self, key: str, item: Any, processor: Callable):
        """
        Добавление элемента в батч
        Автоматически обрабатывает при достижении batch_size или flush_interval
        """
        if key not in self.batches:
            self.batches[key] = []
            self.last_flush[key] = time.time()

        self.batches[key].append(item)

        # Проверяем условия для flush
        should_flush = (
            len(self.batches[key]) >= self.batch_size or
            (time.time() - self.last_flush[key]) >= self.flush_interval
        )

        if should_flush:
            await self.flush(key, processor)

    async def flush(self, key: str, processor: Callable):
        """Обработка накопленного батча"""
        if key not in self.batches or not self.batches[key]:
            return

        batch = self.batches[key]
        self.batches[key] = []
        self.last_flush[key] = time.time()

        try:
            await processor(batch)
            logger.debug(f"✅ Обработан батч {key}: {len(batch)} элементов")
        except Exception as e:
            logger.error(f"❌ Ошибка обработки батча {key}: {e}")

class RateLimiter:
    """Rate limiter для ограничения частоты вызовов"""

    def __init__(self, max_calls: int, period: float):
        """
        Args:
            max_calls: Максимальное количество вызовов
            period: Период в секундах
        """
        self.max_calls = max_calls
        self.period = period
        self.calls = []

    async def acquire(self):
        """Ожидание возможности выполнить вызов"""
        now = time.time()

        # Удаляем старые вызовы
        self.calls = [call_time for call_time in self.calls if now - call_time < self.period]

        if len(self.calls) >= self.max_calls:
            # Нужно подождать
            sleep_time = self.period - (now - self.calls[0])
            if sleep_time > 0:
                logger.debug(f"⏸️ Rate limit: ожидание {sleep_time:.2f}с")
                await asyncio.sleep(sleep_time)
                return await self.acquire()

        self.calls.append(now)

def rate_limited(max_calls: int, period: float):
    """Декоратор для rate limiting"""
    limiter = RateLimiter(max_calls, period)

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            await limiter.acquire()
            return await func(*args, **kwargs)
        return wrapper
    return decorator

async def shutdown_executors():
    """Корректное завершение работы executor'ов"""
    global _process_executor, _thread_executor

    if _thread_executor:
        _thread_executor.shutdown(wait=True)
        logger.info("🔄 ThreadPoolExecutor закрыт")

    if _process_executor:
        _process_executor.shutdown(wait=True)
        logger.info("🔄 ProcessPoolExecutor закрыт")
