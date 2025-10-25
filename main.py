#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIO Crypto Bot  Enhanced Modular
Главная точка входа в систему
"""

import sys
import os
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from db_migration import migrate_database


# === ФУНКЦИЯ ДЛЯ УДАЛЕНИЯ КАВЫЧЕК ИЗ ПЕРЕМЕННЫХ ===
def get_env(key, default=None):
    """Получить переменную окружения, удаляя кавычки если есть"""
    value = os.getenv(key, default)
    if value and isinstance(value, str):
        # Удаляем кавычки с начала и конца
        value = value.strip().strip('"').strip("'")
    return value


# === НАСТРОЙКА ОКРУЖЕНИЯ ===
os.environ["ENVIRONMENT"] = get_env("ENVIRONMENT", "development")

# Принудительно включаем PRODUCTION на Railway
if get_env(
    "RAILWAY_ENVIRONMENT_ID"
):  # Railway автоматически устанавливает эту переменную
    os.environ["ENVIRONMENT"] = "PRODUCTION"
    print("🚀 Detected Railway environment - forcing PRODUCTION mode")

# Добавить корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent))

# Импортировать систему логирования
from config.logging_config import LogConfig, ModuleLoggerAdapter

# Настроить главный logger
logger = LogConfig.setup_logger(name="gio_bot")

# === НАСТРОЙКА УРОВНЕЙ ЛОГИРОВАНИЯ ===
ModuleLoggerAdapter.disable_noisy_modules()

if os.getenv("ENVIRONMENT") == "development":
    logger.info("🔧 Enabling DEBUG mode for critical modules...")
    ModuleLoggerAdapter.enable_debug_for(
        "filters.multi_tf_filter",
        "analytics.mtf_analyzer",
        "analytics.volume_profile",
        "systems.signal_generator",
        "filters.confirm_filter",
    )

# === ИМПОРТ КОМПОНЕНТОВ ===

try:
    # Цвета для консоли
    try:
        from config.constants import Colors
    except ImportError:

        class Colors:
            HEADER = "\033[95m"
            OKBLUE = "\033[94m"
            OKCYAN = "\033[96m"
            OKGREEN = "\033[92m"
            WARNING = "\033[93m"
            FAIL = "\033[91m"
            ENDC = "\033[0m"
            BOLD = "\033[1m"
            UNDERLINE = "\033[4m"

    # Основной класс бота
    from core.bot import GIOCryptoBot

    try:
        from utils.health_server import start_health_server, stop_health_server

        HEALTH_CHECK_AVAILABLE = True
        logger.info("✅ Health Check Server импортирован")
    except ImportError as e:
        HEALTH_CHECK_AVAILABLE = False
        logger.warning(f"⚠️ Health Check Server не найден: {e}")
        logger.warning(
            "   Бот будет работать БЕЗ health check (не рекомендуется для Railway)"
        )

    ROITracker = None
    EnhancedAlertsSystem = None
    WhaleTracker = None
    TradeDataAccumulator = None
    MarketDashboard = None
    try:
        from monitors.roi_tracker import ROITracker  # type: ignore

        logger.info("✅ ROITracker импортирован")
    except ImportError as e:
        logger.warning(f"⚠️ ROITracker не найден: {e}")
        logger.warning("   Бот будет работать БЕЗ автоматического отслеживания TP/SL")

    try:
        from systems.enhanced_alerts_system import EnhancedAlertsSystem  # type: ignore

        logger.info("✅ EnhancedAlertsSystem импортирован")
    except ImportError as e:
        logger.warning(f"⚠️ EnhancedAlertsSystem не найден: {e}")
        logger.warning("   Бот будет работать со старой системой алертов")

    try:
        from analytics.whale_activity_tracker import (
            WhaleActivityTracker as WhaleTracker,
        )

        logger.info("✅ WhaleActivityTracker импортирован")
    except ImportError as e:
        logger.warning(f"⚠️ WhaleActivityTracker не найден: {e}")
        logger.warning("   Whale tracking будет недоступен")

    try:
        from modules.trade_data_accumulator import TradeDataAccumulator

        logger.info("✅ TradeDataAccumulator импортирован")
    except ImportError as e:
        logger.warning(f"⚠️ TradeDataAccumulator не найден: {e}")
        logger.warning("   CVD данные будут недоступны")

    MarketDashboard = None
    try:
        from core.market_dashboard import MarketDashboard  # ✅ ПРАВИЛЬНЫЙ ПУТЬ!

        logger.info("✅ MarketDashboard импортирован")
    except ImportError as e:
        logger.warning(f"⚠️ MarketDashboard не найден: {e}")
        logger.warning("   /market будет использовать старый формат")

    logger.info("✅ Основные модули импортированы успешно")

except ImportError as e:
    logger.critical(f"❌ Критическая ошибка импорта: {e}", exc_info=True)
    sys.exit(1)


def print_banner():
    """Красивый баннер при запуске"""
    env = os.getenv("ENVIRONMENT", "development").upper()
    log_level = logging.getLevelName(logger.level)

    # Определить какие компоненты доступны
    components = []
    components.append("✅ Professional Volume Profile Analysis")
    components.append("✅ Advanced News Sentiment Analysis")
    components.append("✅ Binance + Bybit WebSocket Streams")
    components.append("✅ Auto Scanner (каждые 5 мин)")

    if HEALTH_CHECK_AVAILABLE:
        components.append("✅ Health Check Server (Railway compatible)")
    else:
        components.append("⚠️  Health Check Server (не установлен)")

    if ROITracker:
        components.append("✅ Auto ROI Tracker (TP1/TP2/TP3 + Trailing Stop)")
    else:
        components.append("⚠️  Auto ROI Tracker (не установлен)")

    if EnhancedAlertsSystem:
        components.append("✅ Enhanced Alerts (85-90% порог, cooldown 5 мин)")
    else:
        components.append("⚠️  Enhanced Alerts (используется базовая версия)")

    if WhaleTracker:
        components.append("✅ Whale Tracker (сделки >$100K)")
    else:
        components.append("⚠️  Whale Tracker (не установлен)")
    if MarketDashboard:
        components.append("✅ Market Dashboard (S/R, Volume Profile, Sentiment)")
    else:
        components.append("⚠️  Market Dashboard (базовая версия)")
    components.append("✅ Confirm Filter (CVD + Volume + Candle)")
    components.append("✅ Multi-TF Filter (1H/4H/1D согласование)")
    components.append("✅ Dashboard (/market + /advanced)")

    components_str = "\n║  ".join(components)

    banner = f"""
╔══════════════════════════════════════════════════════════════════╗
║                    🚀 GIO CRYPTO BOT 🚀                     ║
╠══════════════════════════════════════════════════════════════════╣
║  {components_str}
╠══════════════════════════════════════════════════════════════════╣
║  📊 Готовность: {"100%" if all([ROITracker, EnhancedAlertsSystem, WhaleTracker]) else "80%"}                                            ║
║  🔧 Mode: {env:<20} Log Level: {log_level:<10}         ║
║  📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}               ║
╚══════════════════════════════════════════════════════════════════╝

⚠️  ВАЖНО: Это НЕ автоторговый бот!
   • НЕ размещает ордера на биржах
   • НЕ управляет реальными позициями
   • Только отслеживает сигналы и уведомляет о результатах

🎯 Используйте команды:
   /market BTCUSDT - Главный дашборд рынка
   /signal_stats - Статистика сигналов
   /help - Все доступные команды
"""
    print(banner)


async def main():
    """Главная функция"""
    logger.info("🔧 Проверка необходимости миграции БД...")
    migrate_database()
    logger.info("")

    bot = None
    roi_tracker = None
    alerts_system = None
    whale_tracker = None
    trade_accumulator = None
    health_server = None

    try:
        print_banner()

        # ========== ЗАПУСК HEALTH CHECK SERVER (для Railway) ==========
        if HEALTH_CHECK_AVAILABLE:
            logger.info("🏥 Запуск Health Check Server на порту 8080...")
            health_server = await start_health_server(port=8080)
            logger.info("=" * 70)

        # ========== СОЗДАНИЕ И ИНИЦИАЛИЗАЦИЯ БОТА ==========
        logger.info("🚀 Создание экземпляра бота...")
        bot = GIOCryptoBot()

        logger.info("🔧 Инициализация бота...")
        await bot.initialize()

        # Проверяем webhook mode
        webhook_enabled = (
            os.getenv("TELEGRAM_WEBHOOK_ENABLED", "false").lower() == "true"
        )

        if webhook_enabled:
            logger.info("🌐 WEBHOOK MODE DETECTED: Starting webhook server...")
            try:
                from webhook_server import run_webhook_server

                logger.info("   ├─ Импорт webhook_server.py успешен")

                # Запускаем webhook сервер и выходим
                await run_webhook_server(bot)
                return  # Webhook сервер работает бесконечно

            except ImportError as e:
                logger.error(f"❌ Не удалось импортировать webhook_server.py: {e}")
                logger.error("   Переключение на polling mode...")
                webhook_enabled = False

        if not webhook_enabled:
            logger.info("🔄 POLLING MODE: Starting...")

        # Получить tracked_symbols
        if hasattr(bot, "tracked_symbols"):
            tracked_symbols = bot.tracked_symbols
        else:
            try:
                from config.settings import TRACKED_SYMBOLS

                tracked_symbols = TRACKED_SYMBOLS
            except:
                tracked_symbols = ["BTCUSDT", "ETHUSDT"]

        logger.info(f"📊 Отслеживаемые пары: {', '.join(tracked_symbols)}")

        # ========== ИНИЦИАЛИЗАЦИЯ ДОПОЛНИТЕЛЬНЫХ КОМПОНЕНТОВ ==========

        # ✅ НОВОЕ: Trade Data Accumulator (для CVD)
        if TradeDataAccumulator:
            logger.info("📊 Инициализация Trade Data Accumulator...")
            trade_accumulator = TradeDataAccumulator(window_minutes=60)
            bot.trade_accumulator = trade_accumulator
            bot.tradedata = trade_accumulator
            logger.info("✅ Trade Data Accumulator готов (60 мин окно)")

        # Whale Tracker (если доступен)
        if WhaleTracker:
            logger.info("🐋 Инициализация Whale Activity Tracker...")
            from config.settings import DATABASE_PATH

            whale_tracker = WhaleTracker(window_minutes=5, db_path=DATABASE_PATH)
            bot.whale_tracker = whale_tracker
            logger.info(f"✅ Whale Activity Tracker готов с БД: {DATABASE_PATH}")

            # Market Dashboard (если доступен)
        if MarketDashboard:
            logger.info("📊 Инициализация Market Dashboard...")
            bot.market_dashboard = MarketDashboard(bot)
            logger.info("✅ Market Dashboard готов")

        # Enhanced Alerts (если доступен)
        if EnhancedAlertsSystem:
            logger.info("🚨 Инициализация Enhanced Alerts System...")
            telegram_handler = getattr(bot, "telegram_handler", None)

            alerts_system = EnhancedAlertsSystem(
                bot_instance=bot,
                telegram_handler=telegram_handler,
                tracked_symbols=tracked_symbols,
            )
            bot.alerts_system = alerts_system
            logger.info("✅ Enhanced Alerts System готов")

        # ❌ ROI Tracker ОТКЛЮЧЕН (бот не торгует)
        roi_tracker = None
        logger.info("⚠️ ROI Tracker отключён (работает БЕЗ торговли)")

        # ========== ЗАПУСК КОМПОНЕНТОВ ==========
        logger.info("▶️ Запуск бота...")
        logger.info("=" * 70)

        tasks = []
        tasks.append(asyncio.create_task(bot.run(), name="bot_main"))

        if alerts_system:
            tasks.append(
                asyncio.create_task(
                    alerts_system.start_monitoring(), name="alerts_system"
                )
            )
            logger.info("   ✅ Enhanced Alerts запущен")

        logger.info("")
        logger.info("🎯 Бот работает!")
        logger.info("💡 Используйте /help в Telegram для списка команд")
        logger.info("🛑 Нажмите Ctrl+C для остановки")
        logger.info("=" * 70)

        await asyncio.gather(*tasks, return_exceptions=True)

    except KeyboardInterrupt:
        logger.warning(
            f"{Colors.WARNING}⚠️ Получен сигнал остановки (Ctrl+C){Colors.ENDC}"
        )

    except Exception as e:
        logger.critical(
            f"{Colors.FAIL}❌ Критическая ошибка: {e}{Colors.ENDC}", exc_info=True
        )

    finally:
        logger.info("")
        logger.info("🛑 Остановка бота...")

        shutdown_tasks = []

        if health_server and HEALTH_CHECK_AVAILABLE:
            logger.info("   ├─ Остановка Health Check Server...")
            try:
                shutdown_tasks.append(asyncio.create_task(stop_health_server()))
            except Exception as e:
                logger.error(f"   │  ❌ Ошибка: {e}")

        if roi_tracker:
            logger.info("   ├─ Остановка ROI Tracker...")
            try:
                shutdown_tasks.append(asyncio.create_task(roi_tracker.stop()))
            except Exception as e:
                logger.error(f"   │  ❌ Ошибка: {e}")

        if alerts_system:
            logger.info("   ├─ Остановка Enhanced Alerts...")
            try:
                shutdown_tasks.append(asyncio.create_task(alerts_system.stop()))
            except Exception as e:
                logger.error(f"   │  ❌ Ошибка: {e}")

        if bot:
            logger.info("   ├─ Остановка бота...")
            try:
                shutdown_tasks.append(asyncio.create_task(bot.shutdown()))
            except Exception as e:
                logger.error(f"   │  ❌ Ошибка: {e}")

        if shutdown_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*shutdown_tasks, return_exceptions=True),
                    timeout=10.0,
                )
                logger.info("   └─ ✅ Остановлено корректно")
            except asyncio.TimeoutError:
                logger.warning("   └─ ⚠️ Таймаут остановки (10s)")
            except Exception as e:
                logger.error(f"   └─ ❌ Ошибка: {e}")

        logger.info("")
        logger.info(f"{Colors.OKBLUE}👋 GIO Crypto Bot завершён{Colors.ENDC}")

        # Статистика (если компоненты были)
        if roi_tracker:
            try:
                stats = roi_tracker.get_stats()
                logger.info("")
                logger.info("📊 Статистика ROI Tracker:")
                logger.info(
                    f"   • SL: {stats.get('sl_triggered', 0)} | TP1: {stats.get('tp1_triggered', 0)} | TP2: {stats.get('tp2_triggered', 0)} | TP3: {stats.get('tp3_triggered', 0)}"
                )
            except:
                pass

        if alerts_system:
            try:
                stats = alerts_system.get_stats()
                logger.info("")
                logger.info("🚨 Статистика Alerts:")
                logger.info(
                    f"   • Отправлено: {stats.get('total_sent', 0)} | Блокировано: {stats.get('blocked_by_cooldown', 0) + stats.get('blocked_by_threshold', 0)}"
                )
            except:
                pass


if __name__ == "__main__":
    try:
        # Для Windows
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        # Запустить
        asyncio.run(main())

    except KeyboardInterrupt:
        print(f"\n{Colors.WARNING}⚠️ Остановка...{Colors.ENDC}")

    except Exception as e:
        print(f"{Colors.FAIL}❌ Неожиданная ошибка: {e}{Colors.ENDC}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
