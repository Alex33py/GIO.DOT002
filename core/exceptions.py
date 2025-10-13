# -*- coding: utf-8 -*-
"""
Система исключений для GIO Crypto Bot
Специализированные исключения для различных модулей
"""

from typing import Optional, Any, Dict


class GIOBotError(Exception):
    """Базовое исключение для GIO Crypto Bot"""

    def __init__(self, message: str, error_code: str = None, details: Dict[str, Any] = None):
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self):
        if self.error_code:
            return f"[{self.error_code}] {self.message}"
        return self.message


class BotInitializationError(GIOBotError):
    """Ошибка инициализации бота"""
    pass


class BotRuntimeError(GIOBotError):
    """Ошибка времени выполнения бота"""
    pass


class APIConnectionError(GIOBotError):
    """Ошибка подключения к API"""

    def __init__(self, message: str, api_name: str = None, status_code: int = None, **kwargs):
        self.api_name = api_name
        self.status_code = status_code
        super().__init__(message, **kwargs)


class DataValidationError(GIOBotError):
    """Ошибка валидации данных"""

    def __init__(self, message: str, field_name: str = None, invalid_value: Any = None, **kwargs):
        self.field_name = field_name
        self.invalid_value = invalid_value
        super().__init__(message, **kwargs)


class ConfigurationError(GIOBotError):
    """Ошибка конфигурации"""
    pass


class MemoryError(GIOBotError):
    """Ошибка управления памятью"""

    def __init__(self, message: str, current_usage: float = None, limit: float = None, **kwargs):
        self.current_usage = current_usage
        self.limit = limit
        details = kwargs.get('details', {})
        if current_usage is not None:
            details['current_usage_mb'] = current_usage
        if limit is not None:
            details['limit_mb'] = limit
        kwargs['details'] = details
        super().__init__(message, **kwargs)


class ScenarioError(GIOBotError):
    """Ошибка работы с торговыми сценариями"""

    def __init__(self, message: str, scenario_id: str = None, **kwargs):
        self.scenario_id = scenario_id
        super().__init__(message, **kwargs)


class VetoSystemError(GIOBotError):
    """Ошибка системы вето"""

    def __init__(self, message: str, veto_reason: str = None, **kwargs):
        self.veto_reason = veto_reason
        super().__init__(message, **kwargs)


class SignalGenerationError(GIOBotError):
    """Ошибка генерации торговых сигналов"""

    def __init__(self, message: str, symbol: str = None, scenario_id: str = None, **kwargs):
        self.symbol = symbol
        self.scenario_id = scenario_id
        super().__init__(message, **kwargs)


class NewsAnalysisError(GIOBotError):
    """Ошибка анализа новостей"""

    def __init__(self, message: str, news_source: str = None, **kwargs):
        self.news_source = news_source
        super().__init__(message, **kwargs)


class VolumeProfileError(GIOBotError):
    """Ошибка анализа volume profile"""

    def __init__(self, message: str, symbol: str = None, **kwargs):
        self.symbol = symbol
        super().__init__(message, **kwargs)


class DatabaseError(GIOBotError):
    """Ошибка базы данных"""

    def __init__(self, message: str, table_name: str = None, operation: str = None, **kwargs):
        self.table_name = table_name
        self.operation = operation
        super().__init__(message, **kwargs)


class WebSocketError(GIOBotError):
    """Ошибка WebSocket соединения"""

    def __init__(self, message: str, connection_id: str = None, reconnect_attempts: int = None, **kwargs):
        self.connection_id = connection_id
        self.reconnect_attempts = reconnect_attempts
        super().__init__(message, **kwargs)


# Экспорт всех исключений
__all__ = [
    'GIOBotError',
    'BotInitializationError',
    'BotRuntimeError',
    'APIConnectionError',
    'DataValidationError',
    'ConfigurationError',
    'MemoryError',
    'ScenarioError',
    'VetoSystemError',
    'SignalGenerationError',
    'NewsAnalysisError',
    'VolumeProfileError',
    'DatabaseError',
    'WebSocketError',
]
