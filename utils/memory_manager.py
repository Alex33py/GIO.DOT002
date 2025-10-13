# -*- coding: utf-8 -*-
"""
Продвинутый менеджер памяти для GIO Crypto Bot
Совместим с Python 3.13+
"""

import gc
import psutil
import os
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from collections import deque

from config.settings import logger, MAX_MEMORY_MB
from utils.helpers import current_epoch_ms


@dataclass
class CleanupResult:
    """Результат очистки памяти"""
    success: bool
    freed_mb: float
    before_mb: float
    after_mb: float
    method: str
    timestamp: int


class AdvancedMemoryManager:
    """
    Продвинутый менеджер памяти с автоматической очисткой
    Совместим с Python 3.13+
    """

    def __init__(self, max_memory_mb: float = None):
        """Инициализация менеджера памяти"""
        self.max_memory_mb = max_memory_mb or MAX_MEMORY_MB
        self.process = psutil.Process(os.getpid())

        # Пороги для очистки (процент от максимума)
        self.warning_threshold = 80.0
        self.critical_threshold = 90.0

        # История использования памяти
        self.memory_history = deque(maxlen=100)

        # Счётчики
        self.cleanup_count = 0
        self.last_cleanup_time = 0
        self.emergency_cleanup_count = 0

        logger.info(f"✅ AdvancedMemoryManager инициализирован (лимит: {self.max_memory_mb}MB)")

    def _get_memory_usage(self) -> float:
        """Получение текущего использования памяти в MB"""
        try:
            memory_info = self.process.memory_info()
            return memory_info.rss / (1024 * 1024)  # Конвертируем в MB
        except Exception as e:
            logger.error(f"❌ Ошибка получения использования памяти: {e}")
            return 0.0

    def should_cleanup(self) -> bool:
        """Проверка необходимости очистки памяти"""
        try:
            current_usage = self._get_memory_usage()
            usage_percentage = (current_usage / self.max_memory_mb) * 100

            # Очищаем если превышен порог предупреждения
            return usage_percentage >= self.warning_threshold

        except Exception as e:
            logger.error(f"❌ Ошибка проверки необходимости очистки: {e}")
            return False

    async def cleanup_memory(self, force: bool = False) -> CleanupResult:
        """Очистка памяти"""
        try:
            before_usage = self._get_memory_usage()

            # Принудительная сборка мусора
            collected = gc.collect()

            after_usage = self._get_memory_usage()
            freed_mb = before_usage - after_usage

            self.cleanup_count += 1
            self.last_cleanup_time = current_epoch_ms()

            result = CleanupResult(
                success=True,
                freed_mb=round(freed_mb, 2),
                before_mb=round(before_usage, 2),
                after_mb=round(after_usage, 2),
                method="gc.collect",
                timestamp=self.last_cleanup_time
            )

            logger.debug(f"🧹 Очистка памяти: освобождено {freed_mb:.2f}MB, собрано {collected} объектов")

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка очистки памяти: {e}")
            return CleanupResult(
                success=False,
                freed_mb=0,
                before_mb=0,
                after_mb=0,
                method="error",
                timestamp=current_epoch_ms()
            )

    async def emergency_cleanup(self) -> CleanupResult:
        """Экстренная очистка памяти при критическом состоянии"""
        try:
            logger.warning("🚨 Экстренная очистка памяти...")

            before_usage = self._get_memory_usage()

            # Агрессивная очистка
            gc.collect(2)  # Полная сборка всех поколений
            gc.collect(2)  # Повторная для уверенности

            after_usage = self._get_memory_usage()
            freed_mb = before_usage - after_usage

            self.emergency_cleanup_count += 1

            result = CleanupResult(
                success=True,
                freed_mb=round(freed_mb, 2),
                before_mb=round(before_usage, 2),
                after_mb=round(after_usage, 2),
                method="emergency_gc",
                timestamp=current_epoch_ms()
            )

            logger.warning(f"🚨 Экстренная очистка: освобождено {freed_mb:.2f}MB")

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка экстренной очистки: {e}")
            return CleanupResult(
                success=False,
                freed_mb=0,
                before_mb=0,
                after_mb=0,
                method="emergency_error",
                timestamp=current_epoch_ms()
            )

    def get_health_report(self) -> Dict[str, Any]:
        """Получение отчёта о состоянии памяти"""
        try:
            current_usage = self._get_memory_usage()
            usage_percentage = (current_usage / self.max_memory_mb) * 100

            # Определяем статус
            if usage_percentage >= self.critical_threshold:
                status = "critical"
            elif usage_percentage >= self.warning_threshold:
                status = "warning"
            else:
                status = "healthy"

            # Получаем количество объектов (совместимо с Python 3.13)
            try:
                total_objects = len(gc.get_objects())
            except Exception:
                total_objects = 0

            return {
                "status": status,
                "current_usage_mb": round(current_usage, 2),
                "max_memory_mb": self.max_memory_mb,
                "usage_percentage": round(usage_percentage, 1),
                "available_mb": round(self.max_memory_mb - current_usage, 2),
                "total_objects": total_objects,
                "cleanup_count": self.cleanup_count,
                "emergency_cleanup_count": self.emergency_cleanup_count,
                "last_cleanup": self.last_cleanup_time,
                "warning_threshold": self.warning_threshold,
                "critical_threshold": self.critical_threshold
            }

        except Exception as e:
            logger.error(f"❌ Ошибка получения отчёта о памяти: {e}")
            return {
                "status": "error",
                "error": str(e),
                "current_usage_mb": 0,
                "usage_percentage": 0
            }

    def detect_memory_leaks(self) -> List[Dict[str, Any]]:
        """Обнаружение потенциальных утечек памяти"""
        try:
            leaks = []

            # Получаем текущее использование памяти
            current_usage = self._get_memory_usage()

            # Добавляем в историю
            self.memory_history.append({
                "timestamp": current_epoch_ms(),
                "usage_mb": current_usage
            })

            # Анализируем только если достаточно истории (минимум 10 точек)
            if len(self.memory_history) < 10:
                return leaks

            # Проверяем устойчивый рост памяти
            recent_history = list(self.memory_history)[-10:]
            memory_values = [entry["usage_mb"] for entry in recent_history]

            # Простая проверка: растёт ли память постоянно
            increases = sum(1 for i in range(1, len(memory_values)) if memory_values[i] > memory_values[i-1])

            if increases >= 8:  # 8 из 9 измерений показывают рост
                avg_growth = (memory_values[-1] - memory_values[0]) / len(memory_values)

                if avg_growth > 1.0:  # Рост более 1MB за измерение
                    leaks.append({
                        "type": "sustained_growth",
                        "severity": "high",
                        "growth_rate_mb": round(avg_growth, 2),
                        "total_growth_mb": round(memory_values[-1] - memory_values[0], 2),
                        "recommendation": "Проверьте кэши и большие объекты"
                    })

            # Проверяем количество объектов
            try:
                total_objects = len(gc.get_objects())
                if total_objects > 100000:  # Более 100k объектов
                    leaks.append({
                        "type": "high_object_count",
                        "severity": "medium",
                        "object_count": total_objects,
                        "recommendation": "Рассмотрите очистку неиспользуемых объектов"
                    })
            except Exception:
                pass

            return leaks

        except Exception as e:
            logger.error(f"❌ Ошибка обнаружения утечек памяти: {e}")
            return []

    def get_memory_stats(self) -> Dict[str, Any]:
        """Получение детальной статистики памяти"""
        try:
            memory_info = self.process.memory_info()

            return {
                "rss_mb": round(memory_info.rss / (1024 * 1024), 2),
                "vms_mb": round(memory_info.vms / (1024 * 1024), 2),
                "percent": round(self.process.memory_percent(), 2),
                "cleanup_history": {
                    "total_cleanups": self.cleanup_count,
                    "emergency_cleanups": self.emergency_cleanup_count,
                    "last_cleanup": self.last_cleanup_time
                }
            }

        except Exception as e:
            logger.error(f"❌ Ошибка получения статистики памяти: {e}")
            return {}


# Экспорт классов
__all__ = [
    'AdvancedMemoryManager',
    'CleanupResult',
]
