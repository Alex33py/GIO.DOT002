# -*- coding: utf-8 -*-
"""
Тест импорта всех модулей utils
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

print("=" * 70)
print("🧪 Тестирование импортов модуля utils...")
print("=" * 70)

# Тест 1: Health Server (ОБЯЗАТЕЛЬНЫЙ ДЛЯ RAILWAY)
try:
    from utils.health_server import (
        start_health_server,
        stop_health_server,
        HealthCheckServer,
    )

    print("✅ Health Server импортирован")
except ImportError as e:
    print(f"❌ Health Server: {e}")

# Тест 2: Validators (импортируем только DataValidator)
try:
    from utils.validators import DataValidator

    print("✅ Validators (DataValidator) импортирован")
except ImportError as e:
    print(f"⚠️ Validators: {e}")

# Тест 3: Performance Optimizer
try:
    from utils.performance_optimizer import (
        HighPerformanceProcessor,
        OptimizedDataManager,
    )

    print("✅ Performance Optimizer импортирован")
except ImportError as e:
    print(f"⚠️ Performance Optimizer: {e}")

# Тест 4: Cache Manager
try:
    from utils.cache_manager import CacheManager

    print("✅ Cache Manager импортирован")
except ImportError as e:
    print(f"⚠️ Cache Manager: {e}")

# Тест 5: Memory Manager (может не экспортировать MemoryManager класс)
try:
    import utils.memory_manager as memory_manager

    print(f"✅ Memory Manager импортирован (доступны: {dir(memory_manager)})")
except ImportError as e:
    print(f"⚠️ Memory Manager: {e}")

# Тест 6: Rate Limiter
try:
    from utils.rate_limiter import RateLimiter

    print("✅ Rate Limiter импортирован")
except ImportError as e:
    print(f"⚠️ Rate Limiter: {e}")

# Тест 7: WebSocket Manager
try:
    from utils.websocket_manager import WebSocketManager

    print("✅ WebSocket Manager импортирован")
except ImportError as e:
    print(f"⚠️ WebSocket Manager: {e}")

# Тест 8: Error Logger
try:
    from utils.error_logger import ErrorLogger

    print("✅ Error Logger импортирован")
except ImportError as e:
    print(f"⚠️ Error Logger: {e}")

# Тест 9: Helpers
try:
    from utils.helpers import format_number

    print("✅ Helpers импортирован")
except ImportError as e:
    print(f"⚠️ Helpers: {e}")

print("=" * 70)
print("✅ Тестирование завершено")
print("=" * 70)
