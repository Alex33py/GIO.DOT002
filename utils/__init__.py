# -*- coding: utf-8 -*-
"""
Утилиты для GIO Crypto Bot
"""

# ============================================================================
# HEALTH CHECK SERVER (для Railway)
# ============================================================================
from .health_server import HealthCheckServer, start_health_server, stop_health_server

# ============================================================================
# VALIDATORS (импортируем только DataValidator)
# ============================================================================
try:
    from .validators import DataValidator
except ImportError:
    DataValidator = None

# ============================================================================
# PERFORMANCE OPTIMIZER
# ============================================================================
try:
    from .performance_optimizer import HighPerformanceProcessor, OptimizedDataManager
except ImportError:
    HighPerformanceProcessor = None
    OptimizedDataManager = None

# ============================================================================
# CACHE MANAGER
# ============================================================================
try:
    from .cache_manager import CacheManager
except ImportError:
    CacheManager = None

# ============================================================================
# MEMORY MANAGER
# ============================================================================
try:
    from .memory_manager import MemoryManager
except ImportError:
    MemoryManager = None

# ============================================================================
# RATE LIMITER
# ============================================================================
try:
    from .rate_limiter import RateLimiter
except ImportError:
    RateLimiter = None

# ============================================================================
# WEBSOCKET MANAGER
# ============================================================================
try:
    from .websocket_manager import WebSocketManager
except ImportError:
    WebSocketManager = None

# ============================================================================
# ERROR LOGGER
# ============================================================================
try:
    from .error_logger import ErrorLogger
except ImportError:
    ErrorLogger = None

# ============================================================================
# HELPERS
# ============================================================================
try:
    from .helpers import format_number, calculate_percentage, parse_timeframe
except ImportError:
    format_number = None
    calculate_percentage = None
    parse_timeframe = None

# ============================================================================
# __all__ (экспорт только доступных модулей)
# ============================================================================
__all__ = [
    # Health Check (обязательно для Railway)
    "HealthCheckServer",
    "start_health_server",
    "stop_health_server",
]

# Добавляем в __all__ только то, что успешно импортировалось
if DataValidator is not None:
    __all__.append("DataValidator")

if HighPerformanceProcessor is not None:
    __all__.extend(["HighPerformanceProcessor", "OptimizedDataManager"])

if CacheManager is not None:
    __all__.append("CacheManager")

if MemoryManager is not None:
    __all__.append("MemoryManager")

if RateLimiter is not None:
    __all__.append("RateLimiter")

if WebSocketManager is not None:
    __all__.append("WebSocketManager")

if ErrorLogger is not None:
    __all__.append("ErrorLogger")

if format_number is not None:
    __all__.extend(["format_number", "calculate_percentage", "parse_timeframe"])
