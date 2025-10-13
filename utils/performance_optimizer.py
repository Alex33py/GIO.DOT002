# utils/performance_optimizer.py
"""
Модуль оптимизации производительности для GIO Bot
"""

import psutil
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass, field


@dataclass
class PerformanceStats:
    """Статистика производительности"""
    batches_processed: int = 0
    total_rows: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    memory_optimizations: int = 0
    start_time: float = field(default_factory=time.time)


class HighPerformanceProcessor:
    """Высокопроизводительный процессор данных"""

    def __init__(self, max_workers: int = 4, chunk_size: int = 10000,
                 cache_size: int = 1000, memory_limit_mb: int = 512):
        self.max_workers = max_workers
        self.chunk_size = chunk_size
        self.cache_size = cache_size
        self.memory_limit_mb = memory_limit_mb
        self.thread_executor = ThreadPoolExecutor(max_workers=max_workers)
        self.stats = PerformanceStats()
        self._lock = threading.Lock()
        self._cache = {}

    def submit_task(self, func: Callable, *args, **kwargs):
        """Отправить задачу на выполнение"""
        return self.thread_executor.submit(func, *args, **kwargs)

    def record_batch(self, rows_processed: int, cache_hit: bool = False,
                     optimized: bool = False):
        """Записать статистику обработанной пачки"""
        with self._lock:
            self.stats.batches_processed += 1
            self.stats.total_rows += rows_processed
            if cache_hit:
                self.stats.cache_hits += 1
            else:
                self.stats.cache_misses += 1
            if optimized:
                self.stats.memory_optimizations += 1

    def get_statistics(self) -> Dict[str, Any]:
        """Получить статистику производительности"""
        with self._lock:
            total_batches = self.stats.batches_processed
            avg_rows = (self.stats.total_rows / total_batches) if total_batches > 0 else 0
            total_cache_ops = self.stats.cache_hits + self.stats.cache_misses
            cache_hit_rate = (self.stats.cache_hits / total_cache_ops * 100) if total_cache_ops > 0 else 0

            memory_info = psutil.virtual_memory()
            try:
                process = psutil.Process()
                process_memory_mb = process.memory_info().rss / 1024 / 1024
            except:
                process_memory_mb = 0

            uptime = time.time() - self.stats.start_time

            return {
                'batches_processed': total_batches,
                'total_rows': self.stats.total_rows,
                'avg_rows_per_batch': avg_rows,
                'cache_hit_rate': cache_hit_rate,
                'cache_hits': self.stats.cache_hits,
                'cache_misses': self.stats.cache_misses,
                'memory_usage_mb': process_memory_mb,
                'memory_percent': memory_info.percent,
                'memory_available_mb': memory_info.available / 1024 / 1024,
                'memory_optimizations': self.stats.memory_optimizations,
                'uptime_seconds': uptime
            }

    def optimize_memory(self):
        """Оптимизировать использование памяти"""
        with self._lock:
            if len(self._cache) > self.cache_size:
                keys_to_remove = list(self._cache.keys())[:len(self._cache) // 2]
                for key in keys_to_remove:
                    del self._cache[key]
                self.stats.memory_optimizations += 1

    def get_memory_usage(self) -> Dict[str, float]:
        """Получить информацию об использовании памяти"""
        memory_info = psutil.virtual_memory()
        try:
            process = psutil.Process()
            process_mb = process.memory_info().rss / 1024 / 1024
        except:
            process_mb = 0

        return {
            'total_mb': memory_info.total / 1024 / 1024,
            'available_mb': memory_info.available / 1024 / 1024,
            'used_mb': memory_info.used / 1024 / 1024,
            'percent': memory_info.percent,
            'process_mb': process_mb
        }

    async def cleanup(self):
        """Асинхронная очистка ресурсов"""
        self.thread_executor.shutdown(wait=True)
        with self._lock:
            self._cache.clear()


class OptimizedDataManager:
    """Менеджер оптимизированного управления данными"""

    def __init__(self, performance_processor: HighPerformanceProcessor):
        self.processor = performance_processor
        self._cache = {}
        self._lock = threading.Lock()

    def store(self, key: str, value: Any):
        """Сохранить данные в кеш"""
        with self._lock:
            self._cache[key] = {
                'value': value,
                'timestamp': time.time()
            }

    def retrieve(self, key: str, default: Any = None) -> Optional[Any]:
        """Получить данные из кеша"""
        with self._lock:
            if key in self._cache:
                self.processor.record_batch(0, cache_hit=True)
                return self._cache[key]['value']
            else:
                self.processor.record_batch(0, cache_hit=False)
                return default

    def cleanup_cache(self, max_age_seconds: Optional[int] = None):
        """Очистить кеш"""
        with self._lock:
            if max_age_seconds is None:
                self._cache.clear()
            else:
                current_time = time.time()
                keys_to_remove = [
                    key for key, data in self._cache.items()
                    if current_time - data['timestamp'] > max_age_seconds
                ]
                for key in keys_to_remove:
                    del self._cache[key]

    def get_cache_size(self) -> int:
        """Получить размер кеша"""
        with self._lock:
            return len(self._cache)

    def get_cache_stats(self) -> Dict[str, Any]:
        """Получить статистику кеша"""
        with self._lock:
            return {
                'size': len(self._cache),
                'keys': list(self._cache.keys())
            }

