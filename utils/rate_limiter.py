#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rate Limiter - контроль частоты API запросов
Предотвращает превышение лимитов API
"""

import asyncio
import time
from typing import Dict, Optional
from collections import deque
from config.settings import logger


class RateLimiter:
    """
    Rate Limiter для контроля частоты API запросов

    Поддерживает:
    - Sliding window rate limiting
    - Per-endpoint лимиты
    - Exponential backoff при превышении
    """

    def __init__(self, requests_per_second: int = 10, burst_size: int = 20):
        """
        Args:
            requests_per_second: Максимум запросов в секунду
            burst_size: Максимальный burst (мгновенных запросов)
        """
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size

        # Sliding window для каждого endpoint
        self.request_windows: Dict[str, deque] = {}

        # Locks для thread-safety
        self.locks: Dict[str, asyncio.Lock] = {}

        logger.info(
            f"✅ RateLimiter инициализирован: {requests_per_second} req/s, burst={burst_size}"
        )

    async def acquire(self, endpoint: str = "default") -> None:
        """
        Запросить разрешение на API вызов

        Блокирует выполнение если превышен лимит

        Args:
            endpoint: Название API endpoint
        """
        # Инициализация для нового endpoint
        if endpoint not in self.request_windows:
            self.request_windows[endpoint] = deque()
            self.locks[endpoint] = asyncio.Lock()

        async with self.locks[endpoint]:
            current_time = time.time()
            window = self.request_windows[endpoint]

            # Удаляем старые запросы (старше 1 секунды)
            while window and window[0] < current_time - 1.0:
                window.popleft()

            # Проверяем лимиты
            if len(window) >= self.requests_per_second:
                # Превышен лимит - ждём
                sleep_time = window[0] + 1.0 - current_time
                if sleep_time > 0:
                    logger.debug(f"⚠️ Rate limit для {endpoint}: ждём {sleep_time:.2f}s")
                    await asyncio.sleep(sleep_time)
                    # Рекурсивный вызов после ожидания
                    return await self.acquire(endpoint)

            # Burst protection
            if len(window) >= self.burst_size:
                await asyncio.sleep(0.1)  # Небольшая задержка

            # Добавляем текущий запрос в window
            window.append(current_time)

    async def acquire_bulk(self, endpoint: str, count: int) -> None:
        """
        Запросить разрешение на несколько API вызовов

        Args:
            endpoint: Название API endpoint
            count: Количество запросов
        """
        for _ in range(count):
            await self.acquire(endpoint)

    def get_stats(self, endpoint: str = "default") -> Dict:
        """
        Получить статистику использования

        Args:
            endpoint: Название API endpoint

        Returns:
            Dict со статистикой
        """
        if endpoint not in self.request_windows:
            return {"requests_last_second": 0, "endpoint": endpoint}

        current_time = time.time()
        window = self.request_windows[endpoint]

        # Подсчитываем запросы за последнюю секунду
        recent_requests = sum(1 for ts in window if ts >= current_time - 1.0)

        return {
            "endpoint": endpoint,
            "requests_last_second": recent_requests,
            "limit_per_second": self.requests_per_second,
            "burst_size": self.burst_size,
            "utilization": (recent_requests / self.requests_per_second) * 100,
        }

    def get_all_stats(self) -> Dict:
        """
        Получить статистику для всех endpoints

        Returns:
            Dict с общей статистикой и по endpoint
        """
        total_requests = 0
        endpoint_stats = {}

        for endpoint in self.request_windows.keys():
            stats = self.get_stats(endpoint)
            # Считаем ВСЕ запросы (не только за последнюю секунду)
            request_count = len(self.request_windows[endpoint])
            total_requests += request_count
            endpoint_stats[endpoint] = request_count

        # Возвращаем формат для /status
        return {"total_requests": total_requests, **endpoint_stats}


class ExponentialBackoff:
    """
    Exponential Backoff для retry логики

    Увеличивает delay между попытками экспоненциально
    """

    def __init__(
        self, base_delay: float = 1.0, max_delay: float = 60.0, factor: float = 2.0
    ):
        """
        Args:
            base_delay: Начальная задержка (секунды)
            max_delay: Максимальная задержка (секунды)
            factor: Множитель для каждой попытки
        """
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.factor = factor
        self.attempt = 0

    def get_delay(self) -> float:
        """
        Рассчитать delay для текущей попытки

        Returns:
            Delay в секундах
        """
        delay = min(self.base_delay * (self.factor**self.attempt), self.max_delay)
        self.attempt += 1
        return delay

    def reset(self):
        """Сбросить счётчик попыток"""
        self.attempt = 0

    async def sleep(self):
        """Асинхронный sleep с exponential backoff"""
        delay = self.get_delay()
        logger.debug(f"⏱️ Exponential backoff: {delay:.2f}s (attempt {self.attempt})")
        await asyncio.sleep(delay)


# Глобальный экземпляр Rate Limiter
_global_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Получить глобальный Rate Limiter (Singleton)"""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(
            requests_per_second=10, burst_size=20  # Bybit: ~10 req/s
        )
    return _global_rate_limiter


# Экспорт
__all__ = ["RateLimiter", "ExponentialBackoff", "get_rate_limiter"]
