# -*- coding: utf-8 -*-
"""
Настройки и конфигурация GIO Crypto Bot
Оптимизировано для Railway deployment
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List
from dotenv import load_dotenv


# === ФУНКЦИЯ ДЛЯ УДАЛЕНИЯ КАВЫЧЕК ===
def get_env(key, default=None):
    """Получить переменную окружения, удаляя кавычки"""
    value = os.getenv(key, default)
    if value and isinstance(value, str):
        value = value.strip().strip('"').strip("'")
    return value


# Определение корневой директории проекта
BASE_DIR = Path(__file__).resolve().parent.parent


# ============================================================================
# ОПРЕДЕЛЕНИЕ ОКРУЖЕНИЯ (ДО load_dotenv!)
# ============================================================================
IS_RAILWAY = os.environ.get('RAILWAY_ENVIRONMENT') is not None
ENVIRONMENT = "PRODUCTION" if IS_RAILWAY else os.getenv("BOT_MODE", "development").upper()
PRODUCTION_MODE = ENVIRONMENT == "PRODUCTION"
DEVELOPMENT_MODE = not PRODUCTION_MODE


# === БАЗА ДАННЫХ (СНАЧАЛА RAILWAY!) ===
DATABASE_URL = os.environ.get("DATABASE_URL")  # Railway передаёт через environ



# Загрузка переменных окружения из .env (только для локальной разработки)
if not IS_RAILWAY:
    load_dotenv()
    # Fallback для локальной разработки
    if not DATABASE_URL:
        DATABASE_URL = f"sqlite:///{str(BASE_DIR / 'data' / 'gio_crypto_bot.db')}"

# Railway Postgres иногда использует postgres://, нужно postgresql://
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Директории данных
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = DATA_DIR / "logs"
SCENARIOS_DIR = DATA_DIR / "scenarios"
CACHE_DIR = DATA_DIR / "cache"

# Путь к базе данных (для совместимости со старым кодом)
DATABASE_PATH = str(DATA_DIR / "gio_crypto_bot.db")



# Создание необходимых директорий
for directory in [DATA_DIR, LOGS_DIR, SCENARIOS_DIR, CACHE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# ============================================================================
# API КЛЮЧИ
# ============================================================================
BYBIT_API_KEY = get_env("BYBIT_API_KEY")
BYBIT_SECRET_KEY = get_env("BYBIT_SECRET_KEY")
CRYPTOPANIC_API_KEY = get_env("CRYPTOPANIC_API_KEY")
CRYPTOCOMPARE_API_KEY = get_env("CRYPTOCOMPARE_API_KEY")
BINANCE_API_KEY = get_env("BINANCE_API_KEY")
BINANCE_API_SECRET = get_env("BINANCE_API_SECRET")
GEMINI_API_KEY = get_env("GEMINI_API_KEY")

# ============================================================================
# TELEGRAM BOT CONFIGURATION
# ============================================================================
TELEGRAM_BOT_TOKEN = get_env("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = get_env("TELEGRAM_CHAT_ID")

# 🔍 DEBUG: Проверка переменных (только в режиме разработки)
if DEVELOPMENT_MODE:
    print("=" * 70)
    print("🔍 DEBUG TELEGRAM CONFIG:")
    print(
        f"   TELEGRAM_BOT_TOKEN = {TELEGRAM_BOT_TOKEN[:20] + '...' if TELEGRAM_BOT_TOKEN else '❌ ПУСТО'}"
    )
    print(
        f"   TELEGRAM_CHAT_ID = {TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else '❌ ПУСТО'}"
    )
    print("=" * 70)

TELEGRAM_CONFIG = {
    "enabled": bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
    "token": TELEGRAM_BOT_TOKEN,
    "chat_id": TELEGRAM_CHAT_ID,
    "auto_signals": True,
    "auto_alerts": True,
    "commands_enabled": True,
}

# ============================================================================
# НАСТРОЙКИ ЛОГИРОВАНИЯ (ОПТИМИЗИРОВАНО ДЛЯ RAILWAY)
# ============================================================================
if PRODUCTION_MODE:
    LOG_LEVEL = logging.WARNING  # Меньше логов в продакшене
    LOG_TO_FILE = False  # Не писать в файл (Railway хранит логи)
    LOG_TO_CONSOLE = True
else:
    LOG_LEVEL = logging.INFO  # Больше логов в режиме разработки
    LOG_TO_FILE = True
    LOG_TO_CONSOLE = True

LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Настройка базового логгера
handlers = [logging.StreamHandler(sys.stdout)] if LOG_TO_CONSOLE else []

if LOG_TO_FILE and DEVELOPMENT_MODE:
    handlers.append(
        logging.FileHandler(
            LOGS_DIR / f"gio_bot_{'production' if PRODUCTION_MODE else 'dev'}.log",
            encoding="utf-8",
        )
    )

logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    datefmt=LOG_DATE_FORMAT,
    handlers=handlers,
)

# Отключаем логи сторонних библиотек
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("urllib3").setLevel(logging.ERROR)
logging.getLogger("websockets").setLevel(logging.ERROR)
logging.getLogger("asyncio").setLevel(logging.WARNING)

# Настройка уровней для модулей бота
logging.getLogger("gio_bot").setLevel(LOG_LEVEL)
logging.getLogger("trading").setLevel(logging.WARNING)
logging.getLogger("connectors").setLevel(logging.WARNING)
logging.getLogger("filters").setLevel(
    logging.INFO if DEVELOPMENT_MODE else logging.WARNING
)
logging.getLogger("database").setLevel(logging.ERROR)

# Создание основного логгера
logger = logging.getLogger("gio_bot")

# Вывод информации о режиме работы
logger.info(f"🚀 ENVIRONMENT: {ENVIRONMENT}")
logger.info(f"🗄️ Database: {'PostgreSQL (Railway)' if DATABASE_URL.startswith('postgresql://') else 'SQLite (local)'}")
if PRODUCTION_MODE:
    logger.info("🚀 PRODUCTION MODE: Запуск с реальными API ключами")
else:
    logger.info("🧪 DEVELOPMENT MODE: Тестовый режим")

# Вывод информации о Telegram bot
logger.info(
    f"📱 Telegram bot: {'✅ Enabled' if TELEGRAM_CONFIG['enabled'] else '❌ Disabled'}"
)

# ============================================================================
# ПРОВЕРКА ОБЯЗАТЕЛЬНЫХ ПЕРЕМЕННЫХ В ПРОДАКШЕНЕ (DEBUG MODE)
# ============================================================================
if PRODUCTION_MODE:
    # DEBUG: Показываем что получили от Railway
    logger.warning("=" * 70)
    logger.warning("🔍 DEBUG: Переменные окружения на Railway:")
    logger.warning(f"   TELEGRAM_BOT_TOKEN: {TELEGRAM_BOT_TOKEN[:30]+'...' if TELEGRAM_BOT_TOKEN else '❌ ПУСТО'}")
    logger.warning(f"   TELEGRAM_CHAT_ID: {TELEGRAM_CHAT_ID if TELEGRAM_CHAT_ID else '❌ ПУСТО'}")
    logger.warning(f"   BYBIT_API_KEY: {BYBIT_API_KEY[:15]+'...' if BYBIT_API_KEY else '❌ ПУСТО'}")
    logger.warning(f"   BYBIT_SECRET_KEY: {BYBIT_SECRET_KEY[:15]+'...' if BYBIT_SECRET_KEY else '❌ ПУСТО'}")
    logger.warning("=" * 70)
    logger.warning("⚠️ Проверка временно отключена - бот запустится в любом случае")

    # ВРЕМЕННО ЗАКОММЕНТИРОВАНО:
    # required_vars = {
    #     "TELEGRAM_BOT_TOKEN": TELEGRAM_BOT_TOKEN,
    #     "TELEGRAM_CHAT_ID": TELEGRAM_CHAT_ID,
    #     "BYBIT_API_KEY": BYBIT_API_KEY,
    #     "BYBIT_SECRET_KEY": BYBIT_SECRET_KEY,
    # }
    # missing_vars = [name for name, value in required_vars.items() if not value]
    # if missing_vars:
    #     error_msg = f"❌ Отсутствуют обязательные переменные окружения: {', '.join(missing_vars)}"
    #     logger.error(error_msg)
    #     raise ValueError(error_msg)
    # logger.info("✅ Все обязательные API ключи загружены")


# ============================================================================
# НАСТРОЙКИ ТОРГОВЛИ
# ============================================================================
TRADING_CONFIG = {
    "max_position_size": float(os.getenv("MAX_POSITION_SIZE", "1000")),
    "risk_per_trade": float(os.getenv("RISK_PER_TRADE", "2.0")),
    "max_open_positions": int(os.getenv("MAX_OPEN_POSITIONS", "5")),
    "min_rr_ratio": float(os.getenv("MIN_RR_RATIO", "1.5")),
}

# ============================================================================
# НАСТРОЙКИ ПАМЯТИ (ОПТИМИЗИРОВАНО ДЛЯ RAILWAY 512MB RAM)
# ============================================================================
MEMORY_CONFIG = {
    "max_memory_mb": int(
        os.getenv("MAX_MEMORY_MB", "400" if PRODUCTION_MODE else "1024")
    ),
    "cleanup_interval": int(
        os.getenv("CLEANUP_INTERVAL", "180" if PRODUCTION_MODE else "300")
    ),
}

# ============================================================================
# НАСТРОЙКИ WEBSOCKET
# ============================================================================
WEBSOCKET_CONFIG = {
    "ping_interval": int(os.getenv("WS_PING_INTERVAL", "30")),
    "ping_timeout": int(os.getenv("WS_PING_TIMEOUT", "10")),
    "reconnect_delay": int(os.getenv("WS_RECONNECT_DELAY", "5")),
}

# ============================================================================
# НАСТРОЙКИ СКАНИРОВАНИЯ
# ============================================================================
SCANNER_CONFIG = {
    "scan_interval_minutes": int(os.getenv("SCAN_INTERVAL", "5")),
    "deal_threshold": float(os.getenv("DEAL_THRESHOLD", "0.75")),
    "risky_threshold": float(os.getenv("RISKY_THRESHOLD", "0.55")),
    "observation_threshold": float(os.getenv("OBSERVATION_THRESHOLD", "0.35")),
}

# ============================================================================
# BINANCE CONFIGURATION
# ============================================================================
BINANCE_CONFIG = {
    "api_key": BINANCE_API_KEY,
    "api_secret": BINANCE_API_SECRET,
    "testnet": DEVELOPMENT_MODE,
    "rate_limit": 1200,
}

# ============================================================================
# TRIGGER SYSTEM CONFIGURATION
# ============================================================================
TRIGGER_CONFIG = {
    "t1_sensitivity": 0.7,
    "t2_sensitivity": 1.5,
    "t3_sensitivity": 0.6,
    "require_all_triggers": False,
}

# MULTI-TIMEFRAME FILTER CONFIGURATION
MULTI_TF_FILTER_CONFIG = {
    "enabled": True,
    "require_all_aligned": False,
    "min_aligned_count": 2,
    "higher_tf_weight": 2.0,
}

# ============================================================================
# PERFORMANCE OPTIMIZATION
# ============================================================================
PERFORMANCE_CONFIG = {
    "process_pool_workers": 2 if PRODUCTION_MODE else 4,  # Меньше workers в продакшене
    "thread_pool_workers": 5 if PRODUCTION_MODE else 10,
    "batch_size": 100,
    "batch_flush_interval": 5.0,
}

# ============================================================================
# TESTING CONFIGURATION
# ============================================================================
TESTING_CONFIG = {
    "enable_tests": DEVELOPMENT_MODE,
    "test_mode": False,
    "mock_api_responses": False,
}

# КОНСТАНТЫ ДЛЯ СОВМЕСТИМОСТИ
MAX_MEMORY_MB = MEMORY_CONFIG["max_memory_mb"]
DB_FILE = str(DATA_DIR / "gio_crypto_bot.db")

# Настройки Volume Profile
VOLUME_PROFILE_LEVELS_COUNT = 50
VOLUME_PROFILE_LOOKBACK = 100
INSTITUTIONAL_VOLUME_THRESHOLD = 1000000
ICEBERG_DETECTION_THRESHOLD = 5

# Пороги сценариев
DEAL_THRESHOLD = SCANNER_CONFIG["deal_threshold"]
RISKY_THRESHOLD = SCANNER_CONFIG["risky_threshold"]
OBSERVATION_THRESHOLD = SCANNER_CONFIG["observation_threshold"]

# Настройки TP/SL
DEFAULT_ATR_SL_MULTIPLIER = 1.5
DEFAULT_TP1_PERCENT = 1.5
DEFAULT_TP2_PERCENT = 3.0
DEFAULT_TP3_PERCENT = 5.0
DEFAULT_TP1_PCT = DEFAULT_TP1_PERCENT
DEFAULT_TP2_PCT = DEFAULT_TP2_PERCENT
DEFAULT_TP3_PCT = DEFAULT_TP3_PERCENT
MIN_RR_RATIO = TRADING_CONFIG["min_rr_ratio"]

# Пороги для Veto системы
FUNDING_RATE_VETO_THRESHOLD = 0.01
LIQUIDITY_VETO_THRESHOLD = 100000
VOLATILITY_VETO_THRESHOLD = 5.0
VOLUME_ANOMALY_VETO_THRESHOLD = 3.0
SPREAD_VETO_THRESHOLD = 0.5
NEWS_SENTIMENT_VETO_THRESHOLD = -0.7
CORRELATION_VETO_THRESHOLD = 0.3
ATR_VETO_MULTIPLIER = 3.0
RSI_OVERBOUGHT_THRESHOLD = 80
RSI_OVERSOLD_THRESHOLD = 20

# Настройки для анализа ликвидаций
LIQUIDATION_CASCADE_VETO_COUNT = 5
LIQUIDATION_VOLUME_THRESHOLD = 1000000

# Алиасы из TRADING_CONFIG
MAX_POSITION_SIZE = TRADING_CONFIG["max_position_size"]
RISK_PER_TRADE = TRADING_CONFIG["risk_per_trade"]

# Настройки стабильности рынка
MARKET_STABILITY_THRESHOLD = 0.8
ORDER_BOOK_IMBALANCE_THRESHOLD = 0.7
BID_ASK_RATIO_THRESHOLD = 0.3
PRICE_IMPACT_THRESHOLD = 0.02

# Настройки временных интервалов
CANDLE_LOOKBACK_PERIOD = 100
INDICATOR_CALCULATION_PERIOD = 14
TREND_CONFIRMATION_CANDLES = 3

# Настройки кэширования
CACHE_EXPIRY_SECONDS = 300
NEWS_CACHE_EXPIRY = 600
ORDERBOOK_CACHE_EXPIRY = 10

# Лимиты API
BINANCE_API_RATE_LIMIT = 1200
BYBIT_API_RATE_LIMIT = 600
NEWS_API_RATE_LIMIT = 100

# Настройки уведомлений
ENABLE_TELEGRAM_NOTIFICATIONS = TELEGRAM_CONFIG["enabled"]
NOTIFICATION_PRIORITY_THRESHOLD = 0.7

logger.info("✅ Все конфигурации загружены успешно")


def load_trading_pairs() -> List[str]:
    """Загружает торговые пары из JSON файла"""
    try:
        TRADING_PAIRS_CONFIG = Path(__file__).parent / "trading_pairs.json"

        if TRADING_PAIRS_CONFIG.exists():
            with open(TRADING_PAIRS_CONFIG, "r", encoding="utf-8") as f:
                config = json.load(f)

            active_pairs = [
                pair["symbol"]
                for pair in config.get("tracked_symbols", [])
                if pair.get("enabled", False)
            ]

            logger.info(f"📋 Загружено {len(active_pairs)} активных пар из JSON")
            return active_pairs
        else:
            logger.warning("⚠️ Файл trading_pairs.json не найден, используем fallback")
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки trading_pairs.json: {e}")

    # Fallback: минимальный набор для продакшена
    default_pairs = ["BTCUSDT"] if PRODUCTION_MODE else ["BTCUSDT", "ETHUSDT"]
    logger.info(f"📋 Fallback: {default_pairs}")
    return default_pairs


# Загрузка торговых пар
TRACKED_SYMBOLS = load_trading_pairs()
logger.info(f"🎯 TRACKED_SYMBOLS: {len(TRACKED_SYMBOLS)} пар")
