# config/logging_config.py
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime


class LogConfig:
    """
    Централізована конфігурація логування з підтримкою dev/prod режимів
    """

    # ДОБАВИТЬ ФУНКЦИЮ ПЕРЕД ENV:
    @staticmethod
    def _get_env(key, default=None):
        """Получить переменную без кавычек"""
        value = os.getenv(key, default)
        if value and isinstance(value, str):
            value = value.strip().strip('"').strip("'")
        return value

    # Визначити середовище з змінної оточення або за замовчуванням
    ENV = _get_env.__func__('ENVIRONMENT', 'development')

    # Рівні логування для різних середовищ
    LOG_LEVELS = {
        'development': logging.DEBUG,   # Повні деталі для відлагодження
        'production': logging.WARNING   # Тільки важливі повідомлення
    }

    # Формати логів
    FORMATS = {
        'detailed': '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(funcName)s() - %(message)s',
        'simple': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'minimal': '%(asctime)s - %(levelname)s - %(message)s'
    }

    @classmethod
    def setup_logger(cls, name='gio_bot', environment=None):
        """
        Налаштувати logger з автоматичним визначенням середовища

        Args:
            name: Ім'я logger (за замовчуванням 'gio_bot')
            environment: 'development' або 'production' (якщо None - з ENV)

        Returns:
            Налаштований logger
        """

        # Визначити середовище
        env = environment or cls.ENV
        log_level = cls.LOG_LEVELS.get(env, logging.DEBUG)

        # Створити директорію для логів
        log_dir = Path('data/logs')
        log_dir.mkdir(parents=True, exist_ok=True)

        # Створити або отримати logger
        logger = logging.getLogger(name)
        logger.handlers.clear()  # Очистити старі handlers
        logger.setLevel(logging.DEBUG)  # Logger приймає всі рівні

        # Визначити формат залежно від середовища
        if env == 'development':
            console_format = cls.FORMATS['detailed']
            file_format = cls.FORMATS['detailed']
            console_level = logging.DEBUG
        else:
            console_format = cls.FORMATS['simple']
            file_format = cls.FORMATS['simple']
            console_level = logging.WARNING

        # === HANDLER 1: Консоль (з кольорами) ===
        console_handler = logging.StreamHandler()
        console_handler.setLevel(console_level)
        console_formatter = ColoredFormatter(console_format)
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)

        # === HANDLER 2: Файл DEBUG (тільки для development) ===
        if env == 'development':
            debug_file = log_dir / 'gio_bot_debug.log'
            debug_handler = RotatingFileHandler(
                debug_file,
                maxBytes=10*1024*1024,  # 10 MB
                backupCount=5,
                encoding='utf-8'
            )
            debug_handler.setLevel(logging.DEBUG)
            debug_formatter = logging.Formatter(cls.FORMATS['detailed'])
            debug_handler.setFormatter(debug_formatter)
            logger.addHandler(debug_handler)

            print(f"📁 Debug log: {debug_file}")

        # === HANDLER 3: Файл WARNING+ (завжди) ===
        error_file = log_dir / f'gio_bot_{env}_errors.log'
        error_handler = RotatingFileHandler(
            error_file,
            maxBytes=5*1024*1024,  # 5 MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.WARNING)
        error_formatter = logging.Formatter(cls.FORMATS['detailed'])
        error_handler.setFormatter(error_formatter)
        logger.addHandler(error_handler)

        # === HANDLER 4: Основний файл (всі події) ===
        main_file = log_dir / f'gio_bot_{env}.log'
        main_handler = RotatingFileHandler(
            main_file,
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=3,
            encoding='utf-8'
        )
        main_handler.setLevel(log_level)
        main_formatter = logging.Formatter(file_format)
        main_handler.setFormatter(main_formatter)
        logger.addHandler(main_handler)

        # Вивести інформацію про налаштування
        print("=" * 70)
        print(f"🚀 GIO Bot Logging: {env.upper()} MODE")
        print(f"📊 Log Level: {logging.getLevelName(log_level)}")
        print(f"📁 Main log: {main_file}")
        print(f"📁 Error log: {error_file}")
        print("=" * 70)

        # Логувати початок сесії
        logger.info("="*70)
        logger.info(f"🚀 Logging initialized: {env.upper()} mode at {datetime.now()}")
        logger.info(f"📊 Log level: {logging.getLevelName(log_level)}")
        logger.info("="*70)

        return logger


class ColoredFormatter(logging.Formatter):
    """
    Formatter з кольорами для консолі (підтримка ANSI)
    """

    # ANSI коди кольорів
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
        'RESET': '\033[0m'        # Reset
    }

    def format(self, record):
        # Додати колір до levelname
        levelname = record.levelname
        if levelname in self.COLORS:
            colored_levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
            record.levelname = colored_levelname

        return super().format(record)


class ModuleLoggerAdapter:
    """
    Адаптер для контролю логування окремих модулів
    """

    @staticmethod
    def set_module_level(module_name: str, level: int):
        """
        Встановити рівень логування для конкретного модуля

        Args:
            module_name: Назва модуля (наприклад 'analytics.mtf_analyzer')
            level: Рівень логування (logging.DEBUG, logging.INFO, тощо)
        """
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(level)

        level_name = logging.getLevelName(level)
        print(f"✅ {module_name} → {level_name}")

    @staticmethod
    def silence_module(module_name: str):
        """
        Повністю вимкнути логування для модуля
        """
        module_logger = logging.getLogger(module_name)
        module_logger.disabled = True
        print(f"🔇 {module_name} DISABLED")

    @staticmethod
    def enable_debug_for(*modules):
        """
        Швидко увімкнути DEBUG для списку модулів

        Args:
            *modules: Назви модулів (без префіксу 'gio_bot.')
        """
        print("\n🔧 ENABLING DEBUG MODE FOR:")
        print("-" * 60)
        for module in modules:
            full_name = f"gio_bot.{module}" if not module.startswith('gio_bot') else module
            ModuleLoggerAdapter.set_module_level(full_name, logging.DEBUG)
        print("-" * 60)

    @staticmethod
    def disable_noisy_modules():
        """
        Вимкнути шумні сторонні модулі
        """
        noisy_modules = [
            'urllib3.connectionpool',
            'asyncio',
            'websocket',
            'httpx',
            'httpcore'
        ]

        print("\n🔇 SILENCING NOISY MODULES:")
        print("-" * 60)
        for module in noisy_modules:
            try:
                logging.getLogger(module).setLevel(logging.WARNING)
                print(f"   {module} → WARNING")
            except:
                pass
        print("-" * 60)

    @staticmethod
    def show_all_loggers():
        """
        Показати всі активні loggers та їх рівні
        """
        loggers = [
            logging.getLogger(name)
            for name in logging.root.manager.loggerDict
        ]

        print("\n📊 ACTIVE LOGGERS:")
        print("-" * 70)
        print(f"{'Logger Name':<45} | {'Level':<10} | Status")
        print("-" * 70)

        for logger in sorted(loggers, key=lambda x: x.name):
            if not isinstance(logger, logging.PlaceHolder):
                level = logging.getLevelName(logger.level)
                disabled = "🔇 DISABLED" if logger.disabled else "✅ ACTIVE"
                print(f"{logger.name:<45} | {level:<10} | {disabled}")

        print("-" * 70)


# Функція для швидкого отримання logger
def get_logger(name='gio_bot'):
    """
    Отримати налаштований logger

    Args:
        name: Ім'я logger

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
