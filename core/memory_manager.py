# -*- coding: utf-8 -*-
"""
Менеджер памяти для GIO Crypto Bot
"""

import psutil
from typing import Dict, Any
from datetime import datetime, timedelta
from config.settings import logger

class AdvancedMemoryManager:
    """Управление памятью и кэшированием данных"""

    def __init__(self, max_memory_mb: int = 1024):
        self.max_memory_mb = max_memory_mb
        self.cache = {}
        logger.info(f"✅ AdvancedMemoryManager инициализирован (лимит: {max_memory_mb}MB)")

    def store(self, category: str, key: str, data: Any):
        """Сохранение данных в кэш"""
        if category not in self.cache:
            self.cache[category] = {}
        self.cache[category][key] = {
            'data': data,
            'timestamp': datetime.now()
        }

    def retrieve(self, category: str, key: str) -> Any:
        """Получение данных из кэша"""
        try:
            return self.cache.get(category, {}).get(key, {}).get('data')
        except:
            return None

    def cleanup_old_data(self, max_age_seconds: int = 3600):
        """Очистка старых данных"""
        cutoff = datetime.now() - timedelta(seconds=max_age_seconds)
        for category in list(self.cache.keys()):
            for key in list(self.cache[category].keys()):
                if self.cache[category][key]['timestamp'] < cutoff:
                    del self.cache[category][key]

    def force_cleanup(self):
        """Принудительная очистка кэша"""
        self.cache.clear()
        logger.info("🧹 Кэш очищен принудительно")

    def get_statistics(self) -> Dict:
        """Получение статистики использования памяти"""
        process = psutil.Process()
        memory_info = process.memory_info()
        current_mb = memory_info.rss / 1024 / 1024

        return {
            'current_usage_mb': current_mb,
            'max_memory_mb': self.max_memory_mb,
            'usage_percent': (current_mb / self.max_memory_mb) * 100,
            'cached_categories': len(self.cache)
        }
