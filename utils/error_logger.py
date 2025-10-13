#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Детальное логирование ошибок для GIO Crypto Bot
Сохраняет traceback и контекст в файл errors.log
"""

import traceback
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from config.settings import logger, DATA_DIR


class ErrorLogger:
    """Логирование ошибок с полным контекстом"""

    ERROR_LOG_PATH = DATA_DIR / "errors.log"

    @staticmethod
    def log_error(
        error: Exception,
        context: Dict[str, Any],
        severity: str = "ERROR"
    ):
        """
        Логировать ошибку с полным контекстом

        Args:
            error: Объект исключения
            context: Контекст (модуль, функция, параметры)
            severity: Уровень серьёзности (ERROR, CRITICAL, WARNING)
        """
        try:
            # Получаем traceback
            tb = traceback.format_exception(type(error), error, error.__traceback__)
            tb_str = "".join(tb)

            # Формируем сообщение
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            error_message = f"""
{'='*80}
[{severity}] {timestamp}
{'='*80}

ERROR TYPE: {type(error).__name__}
ERROR MESSAGE: {str(error)}

CONTEXT:
{ErrorLogger._format_context(context)}

TRACEBACK:
{tb_str}
{'='*80}

"""

            # Логируем в консоль
            if severity == "CRITICAL":
                logger.critical(f"💥 CRITICAL ERROR: {error}")
            elif severity == "ERROR":
                logger.error(f"❌ ERROR: {error}")
            else:
                logger.warning(f"⚠️ WARNING: {error}")

            logger.error(f"📍 Context: {ErrorLogger._format_context_short(context)}")

            # Сохраняем в файл
            ErrorLogger._save_to_file(error_message)

        except Exception as e:
            # Если логирование ошибок само упало
            logger.error(f"❌ Ошибка логирования ошибки: {e}")

    @staticmethod
    def _format_context(context: Dict[str, Any]) -> str:
        """Форматирование контекста для файла"""
        lines = []
        for key, value in context.items():
            # Обрезаем слишком длинные значения
            if isinstance(value, str) and len(value) > 200:
                value = value[:200] + "..."
            lines.append(f"  {key}: {value}")
        return "\n".join(lines)

    @staticmethod
    def _format_context_short(context: Dict[str, Any]) -> str:
        """Краткое форматирование контекста для консоли"""
        items = []
        for key, value in context.items():
            if isinstance(value, str) and len(value) > 50:
                value = value[:50] + "..."
            items.append(f"{key}={value}")
        return ", ".join(items)

    @staticmethod
    def _save_to_file(message: str):
        """Сохранить сообщение в errors.log"""
        try:
            # Создаём директорию если нет
            ErrorLogger.ERROR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

            # Дописываем в файл
            with open(ErrorLogger.ERROR_LOG_PATH, "a", encoding="utf-8") as f:
                f.write(message)

            # Ограничиваем размер файла (5 МБ)
            ErrorLogger._rotate_log_if_needed()

        except Exception as e:
            logger.error(f"❌ Ошибка записи в errors.log: {e}")

    @staticmethod
    def _rotate_log_if_needed(max_size_mb: int = 5):
        """Ротация лог-файла если он слишком большой"""
        try:
            if not ErrorLogger.ERROR_LOG_PATH.exists():
                return

            # Проверяем размер
            size_mb = ErrorLogger.ERROR_LOG_PATH.stat().st_size / (1024 * 1024)

            if size_mb > max_size_mb:
                # Переименовываем старый файл
                backup_path = ErrorLogger.ERROR_LOG_PATH.with_suffix(".old.log")
                ErrorLogger.ERROR_LOG_PATH.rename(backup_path)

                logger.info(f"📋 Ротация errors.log: {size_mb:.1f} MB → errors.old.log")

        except Exception as e:
            logger.error(f"❌ Ошибка ротации errors.log: {e}")

    @staticmethod
    def log_api_error(
        api_name: str,
        endpoint: str,
        error: Exception,
        params: Optional[Dict] = None
    ):
        """Специализированное логирование API ошибок"""
        context = {
            "module": "API Connector",
            "api": api_name,
            "endpoint": endpoint,
            "params": params or {},
            "error_type": type(error).__name__
        }

        ErrorLogger.log_error(error, context, severity="ERROR")

    @staticmethod
    def log_calculation_error(
        calculation_name: str,
        input_data: Any,
        error: Exception
    ):
        """Специализированное логирование ошибок расчётов"""
        context = {
            "module": "Analytics",
            "calculation": calculation_name,
            "input_type": type(input_data).__name__,
            "input_preview": str(input_data)[:100] if input_data else "None"
        }

        ErrorLogger.log_error(error, context, severity="WARNING")

    @staticmethod
    def log_validation_error(
        validator_name: str,
        data_type: str,
        error: Exception
    ):
        """Специализированное логирование ошибок валидации"""
        context = {
            "module": "Validation",
            "validator": validator_name,
            "data_type": data_type,
            "error_type": type(error).__name__
        }

        ErrorLogger.log_error(error, context, severity="WARNING")

    @staticmethod
    def log_database_error(
        operation: str,
        table: str,
        error: Exception,
        query: Optional[str] = None
    ):
        """Специализированное логирование ошибок БД"""
        context = {
            "module": "Database",
            "operation": operation,
            "table": table,
            "query": query[:100] if query else "N/A"
        }

        ErrorLogger.log_error(error, context, severity="ERROR")

    @staticmethod
    def log_websocket_error(
        symbol: str,
        stream_type: str,
        error: Exception
    ):
        """Специализированное логирование ошибок WebSocket"""
        context = {
            "module": "WebSocket",
            "symbol": symbol,
            "stream_type": stream_type,
            "error_type": type(error).__name__
        }

        ErrorLogger.log_error(error, context, severity="ERROR")


# Экспорт
__all__ = ['ErrorLogger']
