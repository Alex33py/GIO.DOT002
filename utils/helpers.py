# -*- coding: utf-8 -*-
"""
Вспомогательные функции и утилиты для GIO Crypto Bot
Содержит общие функции, форматирование и работу с данными
"""

import os
import json
import time
import asyncio
import signal
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from pathlib import Path

from config.constants import Colors, TIME_FORMATS
from config.settings import logger, DATA_DIR


def current_epoch_ms() -> int:
    """Получение текущего времени в миллисекундах"""
    return int(time.time() * 1000)


def datetime_to_epoch_ms(dt_string: str) -> int:
    """Конвертация строки даты в миллисекунды epoch"""
    try:
        # Пробуем различные форматы
        for fmt in TIME_FORMATS:
            try:
                dt = datetime.strptime(dt_string, fmt)
                # Если timezone не указана, считаем UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return int(dt.timestamp() * 1000)
            except ValueError:
                continue

        # Если не удалось распарсить, возвращаем текущее время
        logger.warning(f"⚠️ Не удалось распарсить дату: {dt_string}")
        return current_epoch_ms()

    except Exception as e:
        logger.error(f"❌ Ошибка конвертации даты {dt_string}: {e}")
        return current_epoch_ms()


def epoch_ms_to_datetime(timestamp_ms: int, format_str: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Конвертация миллисекунд epoch в строку даты"""
    try:
        dt = datetime.fromtimestamp(timestamp_ms / 1000, tz=timezone.utc)
        return dt.strftime(format_str)
    except Exception as e:
        logger.error(f"❌ Ошибка конвертации timestamp {timestamp_ms}: {e}")
        return "Invalid Date"


def safe_float(value: Any, default: float = 0.0) -> float:
    """Безопасная конвертация в float"""
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Безопасная конвертация в int"""
    try:
        if value is None or value == "":
            return default
        return int(float(value))  # Через float для случаев как "123.0"
    except (ValueError, TypeError):
        return default


def format_number(value: Union[int, float], decimals: int = 2) -> str:
    """Форматирование числа с разделителями тысяч"""
    try:
        if isinstance(value, (int, float)):
            return f"{value:,.{decimals}f}"
        return str(value)
    except Exception:
        return "N/A"


def format_percentage(value: float, decimals: int = 2, show_sign: bool = True) -> str:
    """Форматирование процентов с цветами"""
    try:
        percentage = value * 100 if abs(value) <= 1 else value
        sign = "+" if percentage > 0 and show_sign else ""
        color = Colors.BULLISH if percentage > 0 else Colors.BEARISH if percentage < 0 else Colors.NEUTRAL

        return f"{color}{sign}{percentage:.{decimals}f}%{Colors.END}"
    except Exception:
        return "N/A"


def format_currency(value: float, symbol: str = "$", decimals: int = 2) -> str:
    """Форматирование валютных сумм"""
    try:
        if abs(value) >= 1_000_000:
            return f"{symbol}{value/1_000_000:.1f}M"
        elif abs(value) >= 1_000:
            return f"{symbol}{value/1_000:.1f}K"
        else:
            return f"{symbol}{value:.{decimals}f}"
    except Exception:
        return f"{symbol}N/A"


def format_volume(value: float) -> str:
    """Форматирование объёма торгов"""
    try:
        if value >= 1_000_000_000:
            return f"{value/1_000_000_000:.2f}B"
        elif value >= 1_000_000:
            return f"{value/1_000_000:.2f}M"
        elif value >= 1_000:
            return f"{value/1_000:.2f}K"
        else:
            return f"{value:.2f}"
    except Exception:
        return "N/A"


def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """Расчёт процентного изменения"""
    try:
        if old_value == 0:
            return 100.0 if new_value > 0 else -100.0 if new_value < 0 else 0.0
        return ((new_value - old_value) / old_value) * 100
    except Exception:
        return 0.0


def truncate_string(text: str, max_length: int, suffix: str = "...") -> str:
    """Обрезка строки с добавлением суффикса"""
    try:
        if len(text) <= max_length:
            return text
        return text[:max_length - len(suffix)] + suffix
    except Exception:
        return str(text)


def clean_filename(filename: str) -> str:
    """Очистка имени файла от недопустимых символов"""
    try:
        import re
        # Заменяем недопустимые символы на подчёркивание
        clean_name = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Убираем лишние подчёркивания
        clean_name = re.sub(r'_+', '_', clean_name)
        return clean_name.strip('_')
    except Exception:
        return "unnamed_file"


def ensure_directory_exists(directory_path: Union[str, Path]) -> bool:
    """Создание директории если не существует"""
    try:
        path = Path(directory_path)
        path.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"❌ Не удалось создать директорию {directory_path}: {e}")
        return False


def save_json_file(data: Any, file_path: Union[str, Path], indent: int = 2) -> bool:
    """Сохранение данных в JSON файл"""
    try:
        path = Path(file_path)
        ensure_directory_exists(path.parent)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)

        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения JSON файла {file_path}: {e}")
        return False


def load_json_file(file_path: Union[str, Path], default: Any = None) -> Any:
    """Загрузка данных из JSON файла"""
    try:
        path = Path(file_path)
        if not path.exists():
            return default

        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    except Exception as e:
        logger.error(f"❌ Ошибка загрузки JSON файла {file_path}: {e}")
        return default


def merge_dicts(dict1: Dict, dict2: Dict, deep: bool = True) -> Dict:
    """Слияние словарей с поддержкой глубокого слияния"""
    try:
        if not deep:
            result = dict1.copy()
            result.update(dict2)
            return result

        result = dict1.copy()

        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = merge_dicts(result[key], value, deep=True)
            else:
                result[key] = value

        return result
    except Exception as e:
        logger.error(f"❌ Ошибка слияния словарей: {e}")
        return dict1


def filter_dict_by_keys(data: Dict, allowed_keys: List[str]) -> Dict:
    """Фильтрация словаря по разрешённым ключам"""
    try:
        return {key: value for key, value in data.items() if key in allowed_keys}
    except Exception as e:
        logger.error(f"❌ Ошибка фильтрации словаря: {e}")
        return {}


def deep_get(data: Dict, key_path: str, default: Any = None, separator: str = '.') -> Any:
    """Получение значения по вложенному пути ключей"""
    try:
        keys = key_path.split(separator)
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default

        return current
    except Exception:
        return default


def flatten_dict(data: Dict, parent_key: str = '', separator: str = '_') -> Dict:
    """Преобразование вложенного словаря в плоский"""
    try:
        items = []

        for key, value in data.items():
            new_key = f"{parent_key}{separator}{key}" if parent_key else key

            if isinstance(value, dict):
                items.extend(flatten_dict(value, new_key, separator).items())
            else:
                items.append((new_key, value))

        return dict(items)
    except Exception as e:
        logger.error(f"❌ Ошибка преобразования словаря: {e}")
        return {}


class GracefulShutdownHandler:
    """Обработчик корректного завершения работы"""

    def __init__(self):
        self.shutdown_event = asyncio.Event()
        self.shutdown_callbacks = []
        self._setup_signal_handlers()

    def _setup_signal_handlers(self):
        """Настройка обработчиков сигналов"""
        try:
            if os.name != 'nt':  # Unix-like системы
                signal.signal(signal.SIGINT, self._signal_handler)
                signal.signal(signal.SIGTERM, self._signal_handler)
            else:  # Windows
                signal.signal(signal.SIGINT, self._signal_handler)
        except Exception as e:
            logger.warning(f"⚠️ Не удалось установить обработчики сигналов: {e}")

    def _signal_handler(self, signum, frame):
        """Обработчик системных сигналов"""
        logger.info(f"🔄 Получен сигнал {signum}, инициируем graceful shutdown...")
        self.shutdown_event.set()

    def add_shutdown_callback(self, callback):
        """Добавление callback для выполнения при завершении"""
        if asyncio.iscoroutinefunction(callback):
            self.shutdown_callbacks.append(callback)

    async def wait_for_shutdown(self):
        """Ожидание сигнала завершения"""
        await self.shutdown_event.wait()

    async def execute_shutdown_callbacks(self):
        """Выполнение всех shutdown callback'ов"""
        try:
            for callback in self.shutdown_callbacks:
                try:
                    await callback()
                except Exception as e:
                    logger.error(f"❌ Ошибка выполнения shutdown callback: {e}")
        except Exception as e:
            logger.error(f"❌ Ошибка выполнения shutdown callbacks: {e}")

    async def save_state(self, state_data: Dict):
        """Сохранение состояния при завершении"""
        try:
            state_file = DATA_DIR / "shutdown_state.json"
            save_json_file(state_data, state_file)
            logger.info(f"💾 Состояние сохранено в {state_file}")
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения состояния: {e}")


class AsyncTimer:
    """Асинхронный таймер для выполнения задач по расписанию"""

    def __init__(self, interval: float, callback, *args, **kwargs):
        self.interval = interval
        self.callback = callback
        self.args = args
        self.kwargs = kwargs
        self.is_running = False
        self.task = None

    async def start(self):
        """Запуск таймера"""
        if self.is_running:
            return

        self.is_running = True
        self.task = asyncio.create_task(self._run())

    async def stop(self):
        """Остановка таймера"""
        self.is_running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass

    async def _run(self):
        """Основной цикл таймера"""
        try:
            while self.is_running:
                await asyncio.sleep(self.interval)
                if self.is_running:
                    if asyncio.iscoroutinefunction(self.callback):
                        await self.callback(*self.args, **self.kwargs)
                    else:
                        self.callback(*self.args, **self.kwargs)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"❌ Ошибка в AsyncTimer: {e}")


def create_progress_bar(current: int, total: int, width: int = 50, fill_char: str = "█") -> str:
    """Создание текстового прогресс-бара"""
    try:
        if total <= 0:
            return f"[{'?' * width}] 0/0 (0.0%)"

        percentage = min(100.0, (current / total) * 100)
        filled_length = int(width * current // total)

        bar = fill_char * filled_length + '-' * (width - filled_length)
        return f"[{bar}] {current}/{total} ({percentage:.1f}%)"

    except Exception:
        return f"[{'?' * width}] ?/? (?%)"


def retry_async(max_attempts: int = 3, delay: float = 1.0, exponential_backoff: bool = True):
    """Декоратор для повторных попыток выполнения асинхронных функций"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if attempt < max_attempts - 1:  # Не последняя попытка
                        wait_time = delay * (2 ** attempt) if exponential_backoff else delay
                        logger.warning(f"⚠️ Попытка {attempt + 1} неудачна для {func.__name__}: {e}. Повтор через {wait_time}с")
                        await asyncio.sleep(wait_time)
                    else:
                        logger.error(f"❌ Все {max_attempts} попыток неудачны для {func.__name__}")

            raise last_exception

        return wrapper
    return decorator


def measure_time(func):
    """Декоратор для измерения времени выполнения функций"""
    if asyncio.iscoroutinefunction(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.debug(f"⏱️ {func.__name__} выполнено за {execution_time:.3f}с")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"❌ {func.__name__} упало за {execution_time:.3f}с: {e}")
                raise
        return async_wrapper
    else:
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                execution_time = time.time() - start_time
                logger.debug(f"⏱️ {func.__name__} выполнено за {execution_time:.3f}с")
                return result
            except Exception as e:
                execution_time = time.time() - start_time
                logger.error(f"❌ {func.__name__} упало за {execution_time:.3f}с: {e}")
                raise
        return sync_wrapper


# Экспорт основных функций
__all__ = [
    'current_epoch_ms',
    'datetime_to_epoch_ms',
    'epoch_ms_to_datetime',
    'safe_float',
    'safe_int',
    'format_number',
    'format_percentage',
    'format_currency',
    'format_volume',
    'calculate_percentage_change',
    'truncate_string',
    'clean_filename',
    'ensure_directory_exists',
    'save_json_file',
    'load_json_file',
    'merge_dicts',
    'filter_dict_by_keys',
    'deep_get',
    'flatten_dict',
    'GracefulShutdownHandler',
    'AsyncTimer',
    'create_progress_bar',
    'retry_async',
    'measure_time',
]
