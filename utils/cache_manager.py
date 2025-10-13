#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cache Manager - управление in-memory кэшем с TTL
Уменьшает количество API запросов через кэширование данных
"""

import time
import asyncio
from typing import Dict, Optional, Any, Tuple
from collections import OrderedDict
from dataclasses import dataclass
from config.settings import logger


@dataclass
class CacheEntry:
    """Запись в кэше с metadata"""

    key: str
    value: Any
    timestamp: float
    ttl: float
    hit_count: int = 0

    @property
    def is_expired(self) -> bool:
        """Проверка истечения TTL"""
        return time.time() - self.timestamp > self.ttl

    @property
    def age(self) -> float:
        """Возраст записи (секунды)"""
        return time.time() - self.timestamp


class CacheManager:
    """
    In-Memory кэш менеджер с TTL

    Features:
    - LRU (Least Recently Used) eviction
    - TTL (Time To Live) для автоматической очистки
    - Hit/Miss статистика
    - Namespace support для разделения данных
    """

    def __init__(self, max_size: int = 1000, default_ttl: float = 60.0):
        """
        Args:
            max_size: Максимальное количество записей
            default_ttl: TTL по умолчанию (секунды)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl

        # OrderedDict для LRU
        self.cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # Статистика
        self.stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "expirations": 0,
            "total_requests": 0,
        }

        # Lock для thread-safety
        self.lock = asyncio.Lock()

        logger.info(
            f"✅ CacheManager инициализирован: "
            f"max_size={max_size}, default_ttl={default_ttl}s"
        )

    async def get(self, key: str, namespace: str = "default") -> Optional[Any]:
        """
        Получить значение из кэша

        Args:
            key: Ключ
            namespace: Пространство имён

        Returns:
            Значение или None если не найдено/истекло
        """
        async with self.lock:
            self.stats["total_requests"] += 1
            full_key = f"{namespace}:{key}"

            # Проверяем наличие в кэше
            if full_key not in self.cache:
                self.stats["misses"] += 1
                logger.debug(f"❌ Cache MISS: {full_key}")
                return None

            entry = self.cache[full_key]

            # Проверяем TTL
            if entry.is_expired:
                self.stats["misses"] += 1
                self.stats["expirations"] += 1
                del self.cache[full_key]
                logger.debug(f"⏰ Cache EXPIRED: {full_key} (age: {entry.age:.1f}s)")
                return None

            # Hit! Обновляем статистику и LRU order
            self.stats["hits"] += 1
            entry.hit_count += 1
            self.cache.move_to_end(full_key)

            logger.debug(
                f"✅ Cache HIT: {full_key} "
                f"(age: {entry.age:.1f}s, hits: {entry.hit_count})"
            )

            return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        namespace: str = "default",
    ) -> None:
        """
        Сохранить значение в кэш

        Args:
            key: Ключ
            value: Значение
            ttl: TTL (секунды), если None - использует default_ttl
            namespace: Пространство имён
        """
        async with self.lock:
            full_key = f"{namespace}:{key}"
            ttl = ttl if ttl is not None else self.default_ttl

            # Создаём запись
            entry = CacheEntry(
                key=full_key, value=value, timestamp=time.time(), ttl=ttl
            )

            # Если достигли лимита - удаляем самую старую запись (LRU)
            if len(self.cache) >= self.max_size and full_key not in self.cache:
                oldest_key = next(iter(self.cache))
                del self.cache[oldest_key]
                self.stats["evictions"] += 1
                logger.debug(f"🗑️ Cache EVICTED (LRU): {oldest_key}")

            # Добавляем/обновляем запись
            self.cache[full_key] = entry
            self.cache.move_to_end(full_key)

            logger.debug(f"💾 Cache SET: {full_key} (ttl: {ttl}s)")

    async def delete(self, key: str, namespace: str = "default") -> bool:
        """
        Удалить значение из кэша

        Args:
            key: Ключ
            namespace: Пространство имён

        Returns:
            True если удалено, False если не найдено
        """
        async with self.lock:
            full_key = f"{namespace}:{key}"
            if full_key in self.cache:
                del self.cache[full_key]
                logger.debug(f"🗑️ Cache DELETE: {full_key}")
                return True
            return False

    async def clear(self, namespace: Optional[str] = None) -> int:
        """
        Очистить кэш

        Args:
            namespace: Если указано - очищает только этот namespace

        Returns:
            Количество удалённых записей
        """
        async with self.lock:
            if namespace is None:
                # Очищаем весь кэш
                count = len(self.cache)
                self.cache.clear()
                logger.info(f"🗑️ Cache CLEARED: {count} записей")
                return count
            else:
                # Очищаем только указанный namespace
                prefix = f"{namespace}:"
                keys_to_delete = [k for k in self.cache.keys() if k.startswith(prefix)]
                for key in keys_to_delete:
                    del self.cache[key]
                logger.info(
                    f"🗑️ Cache CLEARED namespace '{namespace}': "
                    f"{len(keys_to_delete)} записей"
                )
                return len(keys_to_delete)

    async def cleanup_expired(self) -> int:
        """
        Удалить все истёкшие записи

        Returns:
            Количество удалённых записей
        """
        async with self.lock:
            expired_keys = [
                key for key, entry in self.cache.items() if entry.is_expired
            ]

            for key in expired_keys:
                del self.cache[key]
                self.stats["expirations"] += 1

            if expired_keys:
                logger.debug(f"🗑️ Cache cleanup: {len(expired_keys)} истёкших записей")

            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """
        Получить статистику кэша

        Returns:
            Dict со статистикой
        """
        total = self.stats["total_requests"]
        hits = self.stats["hits"]
        misses = self.stats["misses"]

        hit_rate = (hits / total * 100) if total > 0 else 0.0
        miss_rate = (misses / total * 100) if total > 0 else 0.0

        return {
            **self.stats,
            "hit_rate": hit_rate,
            "miss_rate": miss_rate,
            "cache_size": len(self.cache),
            "max_size": self.max_size,
            "utilization": (len(self.cache) / self.max_size * 100),
        }

    def get_detailed_stats(self) -> Dict[str, Any]:
        """
        Получить детальную статистику

        Returns:
            Dict с подробной статистикой
        """
        stats = self.get_stats()

        # Топ записей по количеству hits
        top_entries = sorted(
            self.cache.values(), key=lambda e: e.hit_count, reverse=True
        )[:10]

        stats["top_entries"] = [
            {
                "key": entry.key,
                "hits": entry.hit_count,
                "age": entry.age,
                "ttl": entry.ttl,
            }
            for entry in top_entries
        ]

        return stats

    def get_statistics(self) -> Dict[str, Any]:
        """
        Alias для get_stats() - для совместимости

        Returns:
            Dict со статистикой (включая размер в MB)
        """
        stats = self.get_stats()

        # Добавляем размер в MB (примерная оценка)
        stats["total_size_mb"] = stats["cache_size"] * 0.001  # Примерно 1KB на запись
        stats["total_items"] = stats["cache_size"]

        return stats

    async def auto_cleanup_loop(self, interval: float = 60.0):
        """
        Автоматическая очистка истёкших записей

        Args:
            interval: Интервал проверки (секунды)
        """
        logger.info(f"🔄 Запущена автоматическая очистка кэша (каждые {interval}s)")

        while True:
            try:
                await asyncio.sleep(interval)
                expired_count = await self.cleanup_expired()

                if expired_count > 0:
                    logger.debug(
                        f"🗑️ Автоочистка: удалено {expired_count} истёкших записей"
                    )

            except asyncio.CancelledError:
                logger.info("🛑 Остановлена автоматическая очистка кэша")
                break
            except Exception as e:
                logger.error(f"❌ Ошибка в auto_cleanup_loop: {e}")


# Глобальный экземпляр Cache Manager
_global_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Получить глобальный Cache Manager (Singleton)"""
    global _global_cache_manager
    if _global_cache_manager is None:
        _global_cache_manager = CacheManager(
            max_size=1000, default_ttl=10.0  # 10 секунд для ticker data
        )
    return _global_cache_manager


# Экспорт
__all__ = ["CacheManager", "CacheEntry", "get_cache_manager"]
