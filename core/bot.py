#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIO Crypto Bot v3.0 Enhanced Modular - Main Bot Class
"""

import pytz
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime
import asyncio
import time

# Базовые импорты
from config.settings import (
    logger,
    PRODUCTION_MODE,
    DATA_DIR,
    SCENARIOS_DIR,
    DATABASE_PATH,
    TRACKED_SYMBOLS,
    SCANNER_CONFIG,
)
from config.constants import TrendDirectionEnum, Colors

# Исключения
from core.exceptions import (
    BotInitializationError,
    BotRuntimeError,
    APIConnectionError,
)
from utils.validators import DataValidator
from utils.helpers import ensure_directory_exists, current_epoch_ms, safe_float
from utils.performance import async_timed, get_process_executor

# Коннекторы
from connectors.bybit_connector import EnhancedBybitConnector
from connectors.binance_connector import BinanceConnector
from connectors.binance_orderbook_websocket import BinanceOrderbookWebSocket
from connectors.news_connector import UnifiedNewsConnector

# Core модули
from core.memory_manager import AdvancedMemoryManager
from core.scenario_manager import ScenarioManager
from core.scenario_matcher import UnifiedScenarioMatcher
from core.veto_system import EnhancedVetoSystem
from core.alerts import AlertSystem
from core.decision_matrix import DecisionMatrix
from core.triggers import TriggerSystem
from core.simple_alerts import SimpleAlertsSystem
from alerts.enhanced_alerts_system import EnhancedAlertsSystem

# Trading
from trading.signal_generator import AdvancedSignalGenerator
from trading.risk_calculator import DynamicRiskCalculator
from trading.signal_recorder import SignalRecorder
from trading.position_tracker import PositionTracker

# from trading.roi_tracker import ROITracker as AutoROITracker
from trading.unified_auto_scanner import UnifiedAutoScanner

# Analytics
from analytics.mtf_analyzer import MultiTimeframeAnalyzer
from analytics.volume_profile import EnhancedVolumeProfileCalculator
from analytics.enhanced_sentiment_analyzer import UnifiedSentimentAnalyzer
from analytics.cluster_detector import ClusterDetector

# Filters
from filters.multi_tf_filter import MultiTimeframeFilter
from filters.confirm_filter import ConfirmFilter


# Telegram
from telegram_bot.telegram_handler import TelegramBotHandler
from telegram_bot.roi_tracker import ROITracker as TelegramROITracker
from telegram_bot.patches import apply_analyze_batching_all_patch

# Scheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler


class GIOCryptoBot:
    """GIO Crypto Bot - Главный класс торгового бота"""

    def __init__(self):
        """Инициализация бота"""
        import time

        self.start_time = time.time()
        logger.info(
            f"{Colors.HEADER}🚀 Инициализация GIOCryptoBot v3.0...{Colors.ENDC}"
        )

        # Флаги состояния
        self.is_running = False
        self.initialization_complete = False
        self.shutdown_event = asyncio.Event()

        # Данные
        self.market_data = {}
        self.news_cache = []
        self._last_log_time = 0

        # Компоненты
        self.memory_manager = None
        self.bybit_connector = None
        self.binance_connector = None
        self.okx_connector = None
        self.coinbase_connector = None
        self.news_connector = None
        self.orderbook_ws = None
        self.scenario_manager = None
        self.scenario_matcher = None
        self.veto_system = None
        self.alert_system = None
        self.decision_matrix = None
        self.trigger_system = None
        self.mtf_analyzer = None
        self.volume_calculator = None
        self.signal_generator = None
        self.risk_calculator = None
        self.signal_recorder = None
        self.position_tracker = None
        self.roi_tracker = None
        self.telegram_bot = None
        self.scheduler = None

        # Объединённые модули
        self.auto_scanner = None
        self.auto_roi_tracker = None
        self.simple_alerts = None
        self.enhanced_sentiment = None
        self.ml_sentiment = None
        self.enhanced_alerts = None
        self.cluster_detector = None

        logger.info("✅ Базовая инициализация завершена")

        # Миграция БД
        self._migrate_database()

    def _migrate_database(self):
        """Миграция базы данных"""
        try:
            import sqlite3
            import os

            db_path = os.path.join(DATA_DIR, "gio_bot.db")

            if not os.path.exists(db_path):
                logger.warning("⚠️ База данных ещё не создана")
                return

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            cursor.execute("PRAGMA table_info(signals)")
            columns = [row[1] for row in cursor.fetchall()]

            if "updated_at" not in columns:
                logger.info("📊 Миграция БД: добавление колонки updated_at...")
                cursor.execute(
                    """
                    ALTER TABLE signals
                    ADD COLUMN updated_at TEXT DEFAULT NULL
                """
                )
                conn.commit()
                logger.info("✅ Колонка updated_at добавлена!")

            cursor.execute("SELECT COUNT(*) FROM signals WHERE updated_at IS NULL")
            null_count = cursor.fetchone()[0]

            if null_count > 0:
                logger.info(f"📊 Найдено {null_count} сигналов с updated_at = NULL")
                cursor.execute(
                    """
                    UPDATE signals
                    SET updated_at = datetime('now')
                    WHERE updated_at IS NULL
                """
                )
                conn.commit()
                logger.info(f"✅ Обновлено {cursor.rowcount} сигналов!")

            conn.close()

        except Exception as e:
            logger.error(f"❌ Ошибка миграции БД: {e}", exc_info=True)

    async def initialize(self):
        """Полная инициализация всех компонентов"""
        try:
            logger.info(
                f"{Colors.OKBLUE}🔧 Начало инициализации компонентов...{Colors.ENDC}"
            )

            # 1. Memory Manager
            logger.info("1️⃣ Инициализация Memory Manager...")
            self.memory_manager = AdvancedMemoryManager(max_memory_mb=1024)

            # 1️⃣.5 Инициализация LogBatcher
            logger.info("1️⃣.5 Инициализация LogBatcher...")
            from utils.log_batcher import log_batcher

            self.log_batcher = log_batcher
            await self.log_batcher.start()
            logger.info("   ✅ LogBatcher инициализирован (сводки каждые 30s)")

            # 2. Коннекторы
            logger.info("2️⃣ Инициализация коннекторов...")

            # Bybit
            self.bybit_connector = EnhancedBybitConnector()
            await self.bybit_connector.initialize()
            logger.info("   ✅ Bybit connector initialized")

            # 2️⃣.2 Инициализация Binance Orderbook WebSocket
            logger.info("2️⃣.2 Инициализация Binance Orderbook WebSocket...")
            self.binance_orderbook_ws = BinanceOrderbookWebSocket(
                symbols=TRACKED_SYMBOLS,  # ["BTCUSDT", "XRPUSDT"]
                depth=20,  # 20 уровней orderbook
            )
            logger.info("   ✅ Binance Orderbook WebSocket инициализирован")

            # ⭐ Binance (REST + WebSocket)
            binance_symbols = ["btcusdt", "ethusdt", "solusdt"]

            self.binance_connector = BinanceConnector(
                symbols=binance_symbols, enable_websocket=True
            )

            # Установить callbacks
            self.binance_connector.set_callbacks(
                {
                    "on_orderbook_update": self.handle_binance_orderbook,
                    "on_trade": self.handle_binance_trade,
                    "on_kline": self.handle_binance_kline,
                }
            )

            # Инициализация REST API
            if await self.binance_connector.initialize():
                logger.info("   ✅ Binance connector initialized (REST + WebSocket)")
            else:
                logger.warning("   ⚠️ Binance initialization failed")

            # News
            self.news_connector = UnifiedNewsConnector()

            # ⭐ 2.3 OKX (REST + WebSocket) - ВСТАВИТЬ ЗДЕСЬ!
            logger.info("2️⃣.3 Инициализация OKX Connector...")
            from connectors.okx_connector import OKXConnector

            okx_symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT"]

            self.okx_connector = OKXConnector(
                api_key=None,  # Public data only
                api_secret=None,
                passphrase=None,
                symbols=okx_symbols,
                enable_websocket=True,
                demo_mode=False,
            )

            # Установить callbacks
            self.okx_connector.set_callbacks(
                {
                    "on_orderbook_update": self.handle_okx_orderbook,
                    "on_trade": self.handle_okx_trade,
                }
            )

            if await self.okx_connector.initialize():
                logger.info("   ✅ OKX connector initialized (REST + WebSocket)")
            else:
                logger.warning("   ⚠️ OKX initialization failed")

            # ⭐ 2.4 Coinbase (REST + WebSocket) - ВСТАВИТЬ СЮДА!
            logger.info("2️⃣.4 Инициализация Coinbase Connector...")
            from connectors.coinbase_connector import CoinbaseConnector

            coinbase_symbols = ["BTC-USD", "ETH-USD", "SOL-USD"]

            self.coinbase_connector = CoinbaseConnector(
                api_key=None,  # Public data only
                api_secret=None,
                symbols=coinbase_symbols,
                enable_websocket=True,
            )

            # Установить callbacks
            self.coinbase_connector.set_callbacks(
                {
                    "on_orderbook_update": self.handle_coinbase_orderbook,
                    "on_trade": self.handle_coinbase_trade,
                    "on_ticker": self.handle_coinbase_ticker,
                }
            )

            if await self.coinbase_connector.initialize():
                logger.info("   ✅ Coinbase connector initialized (REST + WebSocket)")
            else:
                logger.warning("   ⚠️ Coinbase initialization failed")

            # 2.5. WebSocket Orderbook для Bybit L2 данных
            logger.info("2️⃣.5 Инициализация Bybit WebSocket Orderbook...")
            from connectors.bybit_orderbook_ws import BybitOrderbookWebSocket

            self.orderbook_ws = BybitOrderbookWebSocket("BTCUSDT", depth=200)

            async def process_orderbook(orderbook):
                """Обработка L2 стакана заявок"""
                try:
                    current_time = time.time()
                    bids = orderbook.get("bids", [])[:50]
                    asks = orderbook.get("asks", [])[:50]

                    if not bids or not asks:
                        return

                    bid_volume = sum(float(q) for p, q in bids if q)
                    ask_volume = sum(float(q) for p, q in asks if q)
                    total_volume = bid_volume + ask_volume

                    if total_volume > 0:
                        imbalance = (bid_volume - ask_volume) / total_volume

                        if "BTCUSDT" not in self.market_data:
                            self.market_data["BTCUSDT"] = {}

                        self.market_data["BTCUSDT"]["orderbook_imbalance"] = imbalance
                        self.market_data["BTCUSDT"]["bid_volume"] = bid_volume
                        self.market_data["BTCUSDT"]["ask_volume"] = ask_volume
                        self.market_data["BTCUSDT"]["orderbook_full"] = {
                            "bids": orderbook.get("bids", [])[:200],
                            "asks": orderbook.get("asks", [])[:200],
                            "timestamp": current_time,
                            "depth": 200,
                        }

                        # Сохраняем дисбаланс для Cluster Detector
                        if hasattr(self, "l2_imbalances"):
                            if "BTCUSDT" not in self.l2_imbalances:
                                self.l2_imbalances["BTCUSDT"] = []

                            self.l2_imbalances["BTCUSDT"].append(
                                {
                                    "imbalance": imbalance,
                                    "timestamp": datetime.now(),
                                    "direction": "BUY" if imbalance > 0 else "SELL",
                                }
                            )

                            # Храним только последние 100 дисбалансов
                            if len(self.l2_imbalances["BTCUSDT"]) > 100:
                                self.l2_imbalances["BTCUSDT"] = self.l2_imbalances[
                                    "BTCUSDT"
                                ][-100:]

                        if (
                            abs(imbalance) > 0.75
                            and (current_time - self._last_log_time) > 30
                        ):
                            direction = (
                                "📈 BUY pressure"
                                if imbalance > 0
                                else "📉 SELL pressure"
                            )
                            logger.info(
                                f"📊 L2 дисбаланс BTCUSDT: {imbalance:.2%} {direction}"
                            )
                            self._last_log_time = current_time

                except Exception as e:
                    logger.error(f"❌ Ошибка обработки orderbook: {e}")

            self.orderbook_ws.add_callback(process_orderbook)
            await self.orderbook_ws.start()
            logger.info("   ✅ Bybit WebSocket Orderbook запущен (depth=200)")

            # 3. Сценарии и VETO
            logger.info("3️⃣ Инициализация сценариев и VETO...")
            self.scenario_manager = ScenarioManager(db_path=DATABASE_PATH)

            try:
                scenarios_loaded = await self.scenario_manager.load_scenarios_from_json(
                    filename="gio_scenarios_100_with_features_v3.json"
                )
                if scenarios_loaded:
                    logger.info(
                        f"✅ Загружено {len(self.scenario_manager.scenarios)} сценариев"
                    )
            except Exception as e:
                logger.error(f"❌ Ошибка загрузки сценариев: {e}")

            self.veto_system = EnhancedVetoSystem()

            # 4. Аналитика
            logger.info("4️⃣ Инициализация аналитики...")
            self.mtf_analyzer = MultiTimeframeAnalyzer(self.bybit_connector)
            self.volume_calculator = EnhancedVolumeProfileCalculator()

            logger.info("🔍 DEBUG: Попытка импорта ClusterDetector...")

            # Cluster Detector
            try:
                from analytics.cluster_detector import ClusterDetector

                logger.info("🔍 DEBUG: ClusterDetector импортирован успешно")

                logger.info("🔍 DEBUG: Создание экземпляра ClusterDetector...")
                self.cluster_detector = ClusterDetector(self)
                logger.info("🔍 DEBUG: Экземпляр ClusterDetector создан")

                logger.info("   ✅ Cluster Detector инициализирован")

                # Данные для Cluster Detector
                self.l2_imbalances = {}
                self.large_trades = {}
                logger.info("🔍 DEBUG: Данные для Cluster Detector созданы")

            except Exception as e:
                logger.error(f"   ❌ Ошибка инициализации Cluster Detector: {e}")
                logger.error(f"   ❌ Traceback: ", exc_info=True)
                self.cluster_detector = None

            logger.info("🔍 DEBUG: Завершение инициализации Cluster Detector")

            # 5. Системы принятия решений
            logger.info("5️⃣ Инициализация систем принятия решений...")
            self.alert_system = AlertSystem()
            self.decision_matrix = DecisionMatrix()
            self.trigger_system = TriggerSystem()

            # 6. Объединённые модули
            logger.info("6️⃣ Инициализация ОБЪЕДИНЁННЫХ модулей...")
            self.scenario_matcher = UnifiedScenarioMatcher()
            self.scenario_matcher.scenarios = self.scenario_manager.scenarios
            self.enhanced_sentiment = UnifiedSentimentAnalyzer()

            # ⭐ ML Sentiment Analyzer
            logger.info("6️⃣.2 Инициализация ML Sentiment Analyzer...")
            from analytics.ml_sentiment_analyzer import MLSentimentAnalyzer

            self.ml_sentiment = MLSentimentAnalyzer(use_gpu=False)
            ml_initialized = await self.ml_sentiment.initialize()

            if ml_initialized:
                logger.info(
                    "   ✅ ML Sentiment Analyzer инициализирован (FinBERT + CryptoBERT)"
                )
            else:
                logger.warning("   ⚠️ ML models недоступны, используем fallback")

            # 6️⃣.3 Инициализация Cross-Exchange Validator
            logger.info("6️⃣.3 Инициализация Cross-Exchange Validator...")
            from analytics.cross_exchange_validator import CrossExchangeValidator

            self.cross_validator = CrossExchangeValidator(
                price_deviation_threshold=0.001,  # 0.1%
                volume_spike_threshold=3.0,
                min_exchanges_required=2,
            )
            logger.info("   ✅ Cross-Exchange Validator инициализирован")

            # 7. Торговая логика
            logger.info("7️⃣ Инициализация торговой логики...")
            self.risk_calculator = DynamicRiskCalculator(
                min_rr=1.5,
                default_sl_atr_multiplier=1.5,
                default_tp1_percent=1.5,
                use_trailing_stop=True,
            )
            self.signal_recorder = SignalRecorder(db_path=DATABASE_PATH)
            self.position_tracker = PositionTracker(
                signal_recorder=self.signal_recorder
            )

            self.auto_scanner = UnifiedAutoScanner(
                bot_instance=self,
                scenario_matcher=self.scenario_matcher,
                risk_calculator=self.risk_calculator,
                signal_recorder=self.signal_recorder,
                position_tracker=self.position_tracker,
            )

            logger.info(
                "   ⚪ AutoROITracker отключен (используется TelegramROITracker)"
            )
            self.simple_alerts = SimpleAlertsSystem(self)

            # ========== ИНИЦИАЛИЗАЦИЯ ФИЛЬТРОВ ==========
            logger.info("6️⃣.5 Инициализация фильтров...")

            # Импорт конфигурации фильтров (если есть)
            try:
                from config.filters_config import (
                    CONFIRM_FILTER_CONFIG,
                    MULTI_TF_FILTER_CONFIG,
                )

                use_config = True
            except ImportError:
                logger.info(
                    "ℹ️ filters_config не найден, используем дефолтные параметры"
                )
                use_config = False
                CONFIRM_FILTER_CONFIG = {
                    "enabled": True,
                    "cvd_threshold": 0.5,
                    "volume_threshold_multiplier": 1.5,
                    "require_candle_confirmation": False,
                    "min_large_trade_value": 10000,
                }
                MULTI_TF_FILTER_CONFIG = {
                    "enabled": True,
                    "require_all_aligned": False,
                    "min_aligned_count": 1,
                    "higher_tf_weight": 2.0,
                }

            # ========== CONFIRM FILTER ==========
            self.confirm_filter = None
            if CONFIRM_FILTER_CONFIG.get("enabled", True):
                try:
                    from filters.confirm_filter import ConfirmFilter

                    self.confirm_filter = ConfirmFilter(
                        bot_instance=self,  # ✅ Передаем self
                        cvd_threshold=CONFIRM_FILTER_CONFIG.get("cvd_threshold", 0.2),
                        volume_multiplier=CONFIRM_FILTER_CONFIG.get(
                            "volume_threshold_multiplier", 1.3
                        ),
                        candle_check=CONFIRM_FILTER_CONFIG.get(
                            "require_candle_confirmation", True
                        ),
                        min_large_trade_value=CONFIRM_FILTER_CONFIG.get(
                            "min_large_trade_value", 10000
                        ),
                    )
                    logger.info(
                        f"   ✅ Confirm Filter инициализирован (CVD≥{CONFIRM_FILTER_CONFIG.get('cvd_threshold', 0.5)}%)"
                    )
                except ImportError as e:
                    logger.warning(f"   ⚠️ Confirm Filter не найден: {e}")
                    self.confirm_filter = None
                except Exception as e:
                    logger.error(f"   ❌ Ошибка инициализации Confirm Filter: {e}")
                    self.confirm_filter = None
            else:
                logger.info("   ℹ️ Confirm Filter отключён в конфиге")

            # ========== MULTI-TIMEFRAME FILTER ==========
            self.multi_tf_filter = None
            if MULTI_TF_FILTER_CONFIG.get("enabled", True):
                try:
                    from filters.multi_tf_filter import MultiTimeframeFilter

                    self.multi_tf_filter = MultiTimeframeFilter(
                        bot=self,
                        require_all_aligned=MULTI_TF_FILTER_CONFIG.get(
                            "require_all_aligned", False
                        ),
                        min_aligned_count=MULTI_TF_FILTER_CONFIG.get(
                            "min_aligned_count", 2
                        ),
                        higher_tf_weight=MULTI_TF_FILTER_CONFIG.get(
                            "higher_tf_weight", 2.0
                        ),
                    )
                    logger.info(
                        f"   ✅ Multi-TF Filter инициализирован "
                        f"(min_aligned={MULTI_TF_FILTER_CONFIG.get('min_aligned_count', 2)})"
                    )
                # MTF работает синхронно через get_mtf_status()

                except ImportError as e:
                    logger.warning(f"   ⚠️ Multi-TF Filter не найден: {e}")
                    self.multi_tf_filter = None
                except Exception as e:
                    logger.error(f"   ❌ Ошибка инициализации Multi-TF Filter: {e}")
                    self.multi_tf_filter = None
            else:
                logger.info("   ℹ️ Multi-TF Filter отключён в конфиге")

            logger.info("✅ Фильтры инициализированы")

            # ========== SIGNAL GENERATOR ==========
            logger.info("7️⃣.5 Инициализация Signal Generator...")

            self.signal_generator = AdvancedSignalGenerator(
                bot=self,  # ✅ ДОБАВЛЕНО: Передаем self
                veto_system=self.veto_system,
                confirm_filter=self.confirm_filter,
                multi_tf_filter=self.multi_tf_filter,
            )

            logger.info("✅ AdvancedSignalGenerator инициализирован")

            # Логирование интеграции фильтров
            if self.confirm_filter:
                logger.info("   ├─ Confirm Filter: интегрирован ✅")
            else:
                logger.info("   ├─ Confirm Filter: отключён ⚪")

            if self.multi_tf_filter:
                logger.info("   └─ Multi-TF Filter: интегрирован ✅")
            else:
                logger.info("   └─ Multi-TF Filter: отключён ⚪")

            # 8. Telegram Bot
            logger.info("8️⃣ Инициализация Telegram Bot...")
            self.telegram_handler = TelegramBotHandler(self)
            logger.info("   ✅ Telegram Bot инициализирован")

            # 8️⃣.3 Применение патча /analyze_batching ALL
            logger.info("8️⃣.3 Применение патча /analyze_batching ALL...")
            apply_analyze_batching_all_patch(self.telegram_handler)
            logger.info("   ✅ Патч применён")

            # 8️⃣.5 Инициализация Telegram ROITracker для уведомлений с кешированием цен
            logger.info("8️⃣.5 Инициализация Telegram ROITracker...")
            self.telegram_roi_tracker = TelegramROITracker(
                bot=self,  # ✅ ИЗМЕНЕНО: bot вместо bot_instance
                telegram_handler=self.telegram_handler,
            )
            logger.info("   ✅ Telegram ROITracker инициализирован с кешированием цен")

            self.roi_tracker = self.telegram_roi_tracker
            logger.info(
                "   ✅ ROI Tracker установлен (TelegramROITracker + price caching)"
            )

            self.enhanced_alerts = EnhancedAlertsSystem(
                bot_instance=self,
            )

            # 8️⃣.6 Инициализация Market Dashboard
            logger.info("8️⃣.6 Инициализация Market Dashboard...")
            try:
                from telegram_bot.market_dashboard import MarketDashboard
                from telegram_bot.dashboard_commands import DashboardCommands

                # Market Dashboard
                self.market_dashboard = MarketDashboard(self)
                logger.info("   ✅ Market Dashboard инициализирован")

                # Dashboard Commands (регистрация /market)
                if hasattr(self, "telegram_handler"):
                    # Получаем бот из telegram_handler (может быть bot или telegram_bot)
                    telegram_bot_instance = getattr(
                        self.telegram_handler,
                        "bot",
                        getattr(self.telegram_handler, "telegram_bot", None),
                    )

                    if telegram_bot_instance:
                        self.dashboard_commands = DashboardCommands(
                            telegram_bot_instance, self  # AsyncTeleBot instance
                        )
                        logger.info(
                            "   ✅ Dashboard Commands зарегистрированы (/market)"
                        )
                    else:
                        logger.warning(
                            "   ⚠️ Telegram bot instance не найден в telegram_handler"
                        )
                else:
                    logger.warning(
                        "   ⚠️ telegram_handler не найден, пропускаем регистрацию /market"
                    )

            except ImportError as e:
                logger.warning(f"   ⚠️ Dashboard модули не найдены: {e}")
            except Exception as e:
                logger.error(
                    f"   ❌ Ошибка инициализации Dashboard: {e}", exc_info=True
                )

            # 9. Планировщик
            # logger.info("9️⃣ Настройка планировщика...")
            self.setup_scheduler()
            # self.news_connector.update_cache,
            # "interval",
            # minutes=15,
            # id="update_news",
            # name="Обновление новостей",
            # replace_existing=True,
            # )
            logger.info("✅ Планировщик настроен")

            logger.info(
                f"{Colors.OKGREEN}✅ Все компоненты инициализированы (100%)!{Colors.ENDC}"
            )

            self.initialization_complete = True
            logger.info("🚀 GIOCryptoBot v3.0 готов к запуску!")

        except Exception as e:
            logger.error(f"❌ Ошибка инициализации: {e}", exc_info=True)
            raise BotInitializationError(f"Не удалось инициализировать бота: {e}")

    # ⭐ ДОБАВЛЕНО: Binance WebSocket Callback Handlers

    async def handle_binance_orderbook(self, symbol: str, orderbook: Dict):
        """Обработка Binance orderbook обновлений"""
        try:
            ba = self.binance_connector.get_best_bid_ask(symbol)
            if ba:
                spread = self.binance_connector.get_spread(symbol)
                if hasattr(self, "log_batcher"):
                    self.log_batcher.log_orderbook_update("Binance", symbol)

                # Сохраняем в market_data
                if symbol not in self.market_data:
                    self.market_data[symbol] = {}

                self.market_data[symbol]["binance_bid"] = ba[0]
                self.market_data[symbol]["binance_ask"] = ba[1]
                self.market_data[symbol]["binance_spread"] = spread

        except Exception as e:
            logger.error(f"❌ Binance orderbook handler error: {e}", exc_info=True)

    async def handle_binance_trade(self, symbol: str, trade: Dict):
        """Обработка Binance real-time trades"""
        try:
            side = "SELL" if trade["is_buyer_maker"] else "BUY"
            value = trade["quantity"] * trade["price"]

            # Логируем только ОЧЕНЬ крупные сделки > $50k
            if value > 50000:
                logger.info(
                    f"💰 Binance {symbol.upper()} Large Trade: "
                    f"{side} {trade['quantity']:.4f} @ ${trade['price']:,.2f} "
                    f"(${value:,.0f})"
                )

                # ✅ ИСПРАВЛЕНО: Сохраняем в large_trades_cache для Whale Tracking
                if not hasattr(self, "large_trades_cache"):
                    self.large_trades_cache = {}

                symbol_normalized = symbol.replace("-", "")  # BTC-USDT -> BTCUSDT

                if symbol_normalized not in self.large_trades_cache:
                    self.large_trades_cache[symbol_normalized] = []

                self.large_trades_cache[symbol_normalized].append(
                    {
                        "timestamp": time.time(),
                        "side": side.lower(),  # "buy" или "sell"
                        "volume": value,  # USD value
                        "price": trade["price"],
                        "quantity": trade["quantity"],
                    }
                )

                # Ограничиваем размер кеша (последние 100 сделок)
                if len(self.large_trades_cache[symbol_normalized]) > 100:
                    self.large_trades_cache[symbol_normalized] = (
                        self.large_trades_cache[symbol_normalized][-100:]
                    )

        except Exception as e:
            logger.error(f"❌ Binance trade handler error: {e}", exc_info=True)

    async def handle_binance_kline(self, symbol: str, kline: Dict):
        """Обработка Binance klines (свечей)"""
        try:
            # Обрабатываем только закрытые свечи
            if kline["is_closed"]:
                logger.info(
                    f"🕯️ Binance {symbol.upper()} {kline['interval']} closed: "
                    f"O:{kline['open']:.2f} H:{kline['high']:.2f} "
                    f"L:{kline['low']:.2f} C:{kline['close']:.2f} "
                    f"V:{kline['volume']:.2f}"
                )

        except Exception as e:
            logger.error(f"❌ Binance kline handler error: {e}", exc_info=True)

    async def handle_okx_orderbook(self, symbol: str, orderbook: Dict):
        """Обработка OKX orderbook обновлений"""
        try:
            ba = self.okx_connector.get_best_bid_ask(symbol)
            if ba:
                spread = self.okx_connector.get_spread(symbol)
                if hasattr(self, "log_batcher"):
                    self.log_batcher.log_orderbook_update("OKX", symbol)

                # Сохраняем в market_data
                symbol_normalized = symbol.replace("-", "")  # BTC-USDT -> BTCUSDT
                if symbol_normalized not in self.market_data:
                    self.market_data[symbol_normalized] = {}

                self.market_data[symbol_normalized]["okx_bid"] = ba[0]
                self.market_data[symbol_normalized]["okx_ask"] = ba[1]
                self.market_data[symbol_normalized]["okx_spread"] = spread

        except Exception as e:
            logger.error(f"❌ OKX orderbook handler error: {e}", exc_info=True)

    async def handle_okx_trade(self, symbol: str, trade: Dict):
        """Обработка OKX real-time trades"""
        try:
            value = trade["quantity"] * trade["price"]

            # Логируем крупные сделки > $50k
            if value > 50000:
                logger.info(
                    f"💰 OKX {symbol} Large Trade: "
                    f"{trade['side'].upper()} {trade['quantity']:.4f} @ ${trade['price']:,.2f} "
                    f"(${value:,.0f})"
                )
                # Сохраняем крупную сделку для Cluster Detector
                if hasattr(self, "large_trades"):
                    symbol_normalized = symbol.replace("-", "")  # BTC-USDT -> BTCUSDT

                    if symbol_normalized not in self.large_trades:
                        self.large_trades[symbol_normalized] = []

                    self.large_trades[symbol_normalized].append(
                        {
                            "price": trade["price"],
                            "quantity": trade["quantity"],
                            "side": trade["side"],
                            "timestamp": datetime.now(),
                        }
                    )

                    # Храним только последние 200 сделок
                    if len(self.large_trades[symbol_normalized]) > 200:
                        self.large_trades[symbol_normalized] = self.large_trades[
                            symbol_normalized
                        ][-200:]

        except Exception as e:
            logger.error(f"❌ OKX trade handler error: {e}", exc_info=True)

    async def handle_coinbase_orderbook(self, symbol: str, orderbook: Dict):
        """Обработка Coinbase orderbook обновлений"""
        try:
            ba = self.coinbase_connector.get_best_bid_ask(symbol)
            if ba:
                spread = self.coinbase_connector.get_spread(symbol)
                if hasattr(self, "log_batcher"):
                    self.log_batcher.log_orderbook_update("Coinbase", symbol)

                # Сохраняем в market_data
                symbol_normalized = symbol.replace("-", "")  # BTC-USD -> BTCUSD
                if symbol_normalized not in self.market_data:
                    self.market_data[symbol_normalized] = {}

                self.market_data[symbol_normalized]["coinbase_bid"] = ba[0]
                self.market_data[symbol_normalized]["coinbase_ask"] = ba[1]
                self.market_data[symbol_normalized]["coinbase_spread"] = spread

        except Exception as e:
            logger.error(f"❌ Coinbase orderbook handler error: {e}", exc_info=True)

    async def handle_coinbase_trade(self, symbol: str, trade: Dict):
        """Обработка Coinbase real-time trades"""
        try:
            value = trade["size"] * trade["price"]

            # Логируем крупные сделки > $50k
            if value > 50000:
                logger.info(
                    f"💰 Coinbase {symbol} Large Trade: "
                    f"{trade['side'].upper()} {trade['size']:.4f} @ ${trade['price']:,.2f} "
                    f"(${value:,.0f})"
                )

                # Сохраняем крупную сделку для Cluster Detector
                if hasattr(self, "large_trades"):  # ← 12 ПРОБЕЛОВ!
                    symbol_normalized = symbol.replace("-", "")  # ← 16 ПРОБЕЛОВ!

                    if symbol_normalized not in self.large_trades:  # ← 16 ПРОБЕЛОВ!
                        self.large_trades[symbol_normalized] = []  # ← 20 ПРОБЕЛОВ!

                    self.large_trades[symbol_normalized].append(
                        {  # ← 16 ПРОБЕЛОВ!
                            "price": trade["price"],
                            "quantity": trade["size"],
                            "side": trade["side"],
                            "timestamp": datetime.now(),
                        }
                    )

                    # Храним только последние 200 сделок
                    if len(self.large_trades[symbol_normalized]) > 200:
                        self.large_trades[symbol_normalized] = self.large_trades[
                            symbol_normalized
                        ][-200:]

        except Exception as e:
            logger.error(f"❌ Coinbase trade handler error: {e}", exc_info=True)

    async def handle_coinbase_ticker(self, symbol: str, ticker: Dict):
        """Обработка Coinbase ticker updates"""
        try:
            logger.debug(
                f"📊 Coinbase {symbol} Ticker: ${ticker['price']:,.2f} "
                f"24h Vol: ${ticker['volume_24h']:,.0f}"
            )
        except Exception as e:
            logger.error(f"❌ Coinbase ticker handler error: {e}", exc_info=True)

    async def get_volume_profile(self, symbol: str) -> Optional[Dict]:
        """
        Получение Volume Profile с приоритетом L2 Orderbook

        Args:
            symbol: Торговая пара

        Returns:
            Volume Profile данные или None
        """
        try:
            logger.debug(f"📊 Получение Volume Profile для {symbol}...")

            # Даём WebSocket время загрузиться (только при первом вызове)
            if not hasattr(self, "_orderbook_ready"):
                logger.debug("⏳ Ожидание загрузки L2 orderbook (3 сек)...")
                await asyncio.sleep(3)
                self._orderbook_ready = True

            # ПРИОРИТЕТ 1: Bybit L2 Orderbook (для BTCUSDT)
            if (
                symbol == "BTCUSDT"
                and self.orderbook_ws
                and hasattr(self.orderbook_ws, "_orderbook")
                and self.orderbook_ws._orderbook
                and len(self.orderbook_ws._orderbook.get("bids", [])) > 0
            ):
                logger.debug("📊 Используем Bybit L2 Orderbook для Volume Profile")

                volume_profile = await self.volume_calculator.calculate_from_orderbook(
                    self.orderbook_ws._orderbook,
                    price_levels=200,
                )

                if volume_profile:
                    logger.debug(
                        f"   ✅ L2 Orderbook Volume Profile получен (200 levels)"
                    )
                    return volume_profile
                else:
                    logger.warning("   ⚠️ L2 orderbook расчёт не удался")

            # ПРИОРИТЕТ 2: Binance WebSocket Orderbook (для других символов)
            if self.binance_connector:
                binance_orderbook = self.binance_connector.get_ws_orderbook(
                    symbol.lower(), depth=200
                )

                if (
                    binance_orderbook
                    and binance_orderbook["bids"]
                    and binance_orderbook["asks"]
                ):
                    logger.debug(
                        f"📊 Используем Binance WebSocket Orderbook для {symbol}"
                    )

                    # Преобразуем в формат для volume_calculator
                    orderbook_formatted = {
                        "bids": binance_orderbook["bids"],
                        "asks": binance_orderbook["asks"],
                        "timestamp": binance_orderbook.get(
                            "timestamp", datetime.utcnow()
                        ),
                    }

                    volume_profile = (
                        await self.volume_calculator.calculate_from_orderbook(
                            orderbook_formatted,
                            price_levels=200,
                        )
                    )

                    if volume_profile:
                        logger.debug(f"   ✅ Binance Orderbook Volume Profile получен")
                        return volume_profile

            # ПРИОРИТЕТ 3: Fallback на aggTrades (REST API)
            logger.debug(f"📊 Используем aggTrades для {symbol} (fallback)")

            try:
                # Пробуем Bybit
                trades = await self.bybit_connector.get_trades(symbol, limit=1000)

                if trades:
                    logger.debug(f"   ✅ Получено {len(trades)} trades из Bybit")
                    return {
                        "data_source": "bybit_aggTrades",
                        "trades": trades,
                        "symbol": symbol,
                    }

                # Если Bybit не сработал, пробуем Binance REST
                if self.binance_connector:
                    binance_trades = await self.binance_connector.get_agg_trades(
                        symbol=symbol.upper(), limit=1000
                    )

                    if binance_trades:
                        logger.debug(
                            f"   ✅ Получено {len(binance_trades)} trades из Binance"
                        )
                        return {
                            "data_source": "binance_aggTrades",
                            "trades": binance_trades,
                            "symbol": symbol,
                        }

                logger.warning(f"⚠️ Не удалось получить trades для {symbol}")
                return None

            except Exception as e:
                logger.error(f"❌ Ошибка получения trades: {e}")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка получения Volume Profile: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return None

    async def analyze_symbol_with_batching(self, symbol: str) -> Dict:
        """
        Wrapper для UnifiedAutoScanner с MTF Alignment

        Перенаправляет анализ на UnifiedAutoScanner для полной проверки:
        - MTF Alignment
        - Сценарии
        - Volume Profile
        - News Sentiment
        - VETO checks
        - TP/SL calculation

        Args:
            symbol: Символ (например, "BTCUSDT")

        Returns:
            Dict с результатами анализа
        """
        logger.info(f"🔀 Перенаправление {symbol} на UnifiedAutoScanner...")
        analysis_start = time.time()

        try:
            # ✅ Используем UnifiedAutoScanner с полным MTF анализом!
            signal_data = await self.auto_scanner.scan_symbol(symbol)

            analysis_time = time.time() - analysis_start

            if signal_data:  # ← Dict вместо int!
                logger.info(
                    f"✅ {symbol}: Сигнал #{signal_data['signal_id']} создан за {analysis_time:.2f}s"
                )
                return {
                    "symbol": symbol,
                    "status": "success",
                    "signal_id": signal_data["signal_id"],
                    "score": signal_data.get("quality_score", 0),
                    "entry_price": signal_data.get("entry_price", 0),
                    "direction": signal_data.get("direction", "LONG"),
                    "analysis_time": analysis_time,
                    "timestamp": datetime.now().isoformat(),
                }

            else:
                logger.info(
                    f"ℹ️ {symbol}: Подходящих сигналов не найдено за {analysis_time:.2f}s"
                )
                return {
                    "symbol": symbol,
                    "status": "success",
                    "signal_id": None,
                    "score": 0,
                    "analysis_time": analysis_time,
                    "timestamp": datetime.now().isoformat(),
                }

        except Exception as e:
            analysis_time = time.time() - analysis_start
            logger.error(f"❌ Ошибка analyze_symbol_with_batching {symbol}: {e}")
            import traceback

            logger.error(traceback.format_exc())

            return {
                "symbol": symbol,
                "status": "error",
                "error": str(e),
                "score": 0,
                "analysis_time": analysis_time,
                "timestamp": datetime.now().isoformat(),
            }

    def setup_scheduler(self):
        """Настройка планировщика задач"""
        try:
            self.scheduler = AsyncIOScheduler(timezone=pytz.UTC)
            self.scheduler.add_job(
                self.update_news,
                "interval",
                minutes=5,
                id="update_news",
                name="Обновление новостей",
                max_instances=1,
            )
            logger.info("✅ Планировщик настроен")
        except Exception as e:
            logger.error(f"❌ Ошибка настройки scheduler: {e}")
            raise

    async def analyze_symbol_with_validation(self, symbol: str):
        """Анализ символа с кросс-валидацией между биржами"""
        try:
            from analytics.cross_exchange_validator import PriceData

            # 1. Сбор данных с всех бирж
            prices = {}

            # Bybit
            if self.bybit_connector:
                try:
                    bybit_price = await self.bybit_connector.get_current_price(symbol)
                    if bybit_price:
                        prices["Bybit"] = PriceData(
                            exchange="Bybit",
                            symbol=symbol,
                            price=float(bybit_price),
                            timestamp=datetime.utcnow(),
                        )
                except Exception as e:
                    logger.debug(f"⚠️ Bybit price unavailable: {e}")

            # Binance
            if self.binance_connector:
                try:
                    binance_orderbook = self.binance_connector.orderbooks.get(
                        symbol.lower()
                    )
                    if binance_orderbook and "last_price" in binance_orderbook:
                        prices["Binance"] = PriceData(
                            exchange="Binance",
                            symbol=symbol,
                            price=float(binance_orderbook["last_price"]),
                            timestamp=datetime.utcnow(),
                            volume_24h=binance_orderbook.get("volume_24h"),
                        )
                except Exception as e:
                    logger.debug(f"⚠️ Binance price unavailable: {e}")

            # OKX
            if self.okx_connector:
                try:
                    okx_symbol = f"{symbol[:3]}-{symbol[3:]}"  # BTCUSDT -> BTC-USDT
                    okx_orderbook = self.okx_connector.orderbooks.get(okx_symbol)
                    if okx_orderbook and "last_price" in okx_orderbook:
                        prices["OKX"] = PriceData(
                            exchange="OKX",
                            symbol=symbol,
                            price=float(okx_orderbook["last_price"]),
                            timestamp=datetime.utcnow(),
                        )
                except Exception as e:
                    logger.debug(f"⚠️ OKX price unavailable: {e}")

            # Coinbase
            if self.coinbase_connector:
                try:
                    cb_symbol = f"{symbol[:3]}-USD"  # BTCUSDT -> BTC-USD
                    cb_orderbook = self.coinbase_connector.orderbooks.get(cb_symbol)
                    if cb_orderbook and "last_price" in cb_orderbook:
                        prices["Coinbase"] = PriceData(
                            exchange="Coinbase",
                            symbol=symbol,
                            price=float(cb_orderbook["last_price"]),
                            timestamp=datetime.utcnow(),
                        )
                except Exception as e:
                    logger.debug(f"⚠️ Coinbase price unavailable: {e}")

            # 2. Валидация
            if self.cross_validator and len(prices) >= 2:
                validation = await self.cross_validator.validate_price(symbol, prices)

                logger.info(
                    f"🔄 Cross-validation {symbol}: "
                    f"Status={validation.status.value}, "
                    f"Confidence={validation.confidence:.1f}%, "
                    f"Deviation={validation.price_deviation:.2%}, "
                    f"Exchanges={validation.exchanges_count}"
                )

                # Логирование аномалий
                if validation.anomalies:
                    for anomaly in validation.anomalies:
                        logger.warning(f"⚠️ {symbol} Anomaly: {anomaly.value}")

                        # Arbitrage opportunity
                        if anomaly.value == "arbitrage":
                            details = validation.details
                            exchange_prices = details.get("prices", {})
                            if exchange_prices:
                                cheapest = min(exchange_prices, key=exchange_prices.get)
                                expensive = max(
                                    exchange_prices, key=exchange_prices.get
                                )
                                logger.info(
                                    f"💰 ARBITRAGE: {symbol} "
                                    f"Buy on {cheapest} (${exchange_prices[cheapest]:,.2f}) → "
                                    f"Sell on {expensive} (${exchange_prices[expensive]:,.2f}) | "
                                    f"Spread: {validation.price_deviation:.2%}"
                                )

                # Telegram alert если критично
                if validation.status.value in ["warning", "invalid"]:
                    if self.telegram_bot:
                        await self.telegram_bot.send_message(
                            f"⚠️ **Cross-Validation Alert**\n\n"
                            f"Symbol: {symbol}\n"
                            f"Status: {validation.status.value.upper()}\n"
                            f"Confidence: {validation.confidence:.1f}%\n"
                            f"Price Deviation: {validation.price_deviation:.2%}\n"
                            f"Exchanges: {validation.exchanges_count}\n"
                            f"Anomalies: {', '.join([a.value for a in validation.anomalies])}"
                        )

                return validation

            else:
                logger.debug(
                    f"⚠️ {symbol}: Insufficient data for validation ({len(prices)} exchanges)"
                )
                return None

        except Exception as e:
            logger.error(f"❌ Error in cross-validation for {symbol}: {e}")
            return None

    async def run(self):
        """Запуск главного цикла бота"""
        try:
            if not self.initialization_complete:
                raise BotRuntimeError("Бот не инициализирован")

            logger.info(
                f"{Colors.HEADER}🎯 Запуск главного цикла GIO Crypto Bot{Colors.ENDC}"
            )
            self.is_running = True

            self.scheduler.start()
            logger.info("✅ Планировщик запущен")

            # Запуск Telegram Bot
            if self.telegram_handler:
                await self.telegram_handler.initialize()  # ← Сначала инициализация
                await self.telegram_handler.start()  # ← Потом запуск
                logger.info("✅ Telegram Bot запущен")

            if self.auto_scanner:
                asyncio.create_task(self.auto_scanner.start())
                logger.info("✅ AutoScanner запущен")

            if self.auto_roi_tracker:
                asyncio.create_task(self.auto_roi_tracker.start())
                logger.info("✅ AutoROITracker запущен")

            # ⭐ Запуск Binance WebSocket
            if self.binance_connector:
                asyncio.create_task(self.binance_connector.start_websocket())
                logger.info("✅ Binance WebSocket запущен")

            # ⭐ Запуск Binance Orderbook WebSocket
            if self.binance_orderbook_ws:
                asyncio.create_task(self.binance_orderbook_ws.start())
                logger.info("✅ Binance Orderbook WebSocket запущен")

            # ⭐ Запуск OKX WebSocket
            if self.okx_connector:
                asyncio.create_task(self.okx_connector.start_websocket())
                logger.info("✅ OKX WebSocket запущен")

            # ⭐ Запуск Coinbase WebSocket - ДОБАВИТЬ ЗДЕСЬ!
            if self.coinbase_connector:
                asyncio.create_task(self.coinbase_connector.start_websocket())
                logger.info("✅ Coinbase WebSocket запущен")

            if self.enhanced_alerts:
                asyncio.create_task(self.enhanced_alerts.start_monitoring())
                logger.info("✅ Enhanced Alerts запущен")

            # Запуск ROI мониторинга с кешированием цен
            if self.roi_tracker:
                try:
                    # Запускаем ROI Tracker (включает price_updater)
                    await self.roi_tracker.start()
                    logger.info("✅ ROI мониторинг запущен с кешированием цен")

                    # Запускаем мониторинг активных сигналов
                    await self.roi_tracker.start_monitoring()
                    logger.info("✅ ROI мониторинг активных сигналов запущен")
                except Exception as e:
                    logger.error(f"❌ Ошибка запуска ROI мониторинга: {e}")

            await self.update_news()

            if self.enhanced_sentiment and self.news_connector:
                try:
                    news = await self.news_connector.fetch_unified_news(
                        symbols=["BTC", "ETH"], max_age_hours=24
                    )
                    if news:
                        self.enhanced_sentiment.update_news_cache(news)
                        logger.info("✅ Кэш новостей обновлён")
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось обновить кэш новостей: {e}")

            logger.info(f"{Colors.OKGREEN}🔄 Главный цикл запущен{Colors.ENDC}")

            while self.is_running:
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"{Colors.FAIL}❌ Критическая ошибка: {e}{Colors.ENDC}")
            import traceback

            traceback.print_exc()
            raise BotRuntimeError(f"Ошибка главного цикла: {e}")

    async def update_news(self):
        """Обновление новостей"""
        try:
            logger.info("📰 Обновление новостей...")
            news = await self.news_connector.fetch_unified_news(
                symbols=["BTC", "ETH"], max_age_hours=24
            )

            if news:
                self.news_cache = news
                if self.enhanced_sentiment:
                    self.enhanced_sentiment.update_news_cache(news)
                logger.info(f"✅ Загружено {len(news)} новостей")

        except Exception as e:
            logger.error(f"❌ Ошибка обновления новостей: {e}")

    async def shutdown(self):
        """Корректная остановка бота"""
        try:
            logger.info(f"{Colors.WARNING}🛑 Начало остановки бота...{Colors.ENDC}")
            self.is_running = False

            # Остановить LogBatcher ПЕРВЫМ
            if hasattr(self, "log_batcher"):
                await self.log_batcher.stop()
                logger.info("✅ LogBatcher остановлен")

            if self.auto_scanner:
                await self.auto_scanner.stop()

            if self.auto_roi_tracker:
                await self.auto_roi_tracker.stop()

            # Остановить ROI Tracker ПЕРЕД закрытием бирж
            if self.roi_tracker:
                logger.info("🛑 Остановка ROI Tracker...")
                await self.roi_tracker.stop()
                logger.info("✅ ROI Tracker остановлен")

            if self.telegram_bot:
                await self.telegram_bot.stop()

            if self.scheduler and self.scheduler.running:
                self.scheduler.shutdown(wait=False)

            if self.bybit_connector:
                await self.bybit_connector.close()

            # ⭐ Закрытие Binance
            if self.binance_connector:
                await self.binance_connector.close()
                logger.info("✅ Binance connector закрыт")

            # ⭐ Закрытие Binance Orderbook WebSocket
            if self.binance_orderbook_ws:
                await self.binance_orderbook_ws.stop()
                logger.info("✅ Binance Orderbook WebSocket закрыт")

            # ⭐ Закрытие OKX
            if self.okx_connector:
                await self.okx_connector.close()
                logger.info("✅ OKX connector закрыт")

            # ⭐ Закрытие Coinbase - ДОБАВИТЬ ЗДЕСЬ!
            if self.coinbase_connector:
                await self.coinbase_connector.close()
                logger.info("✅ Coinbase connector закрыт")

            if self.news_connector:
                await self.news_connector.close()

            if self.orderbook_ws:
                await self.orderbook_ws.stop()

            logger.info(f"{Colors.OKGREEN}✅ Бот успешно остановлен{Colors.ENDC}")

        except Exception as e:
            logger.error(f"❌ Ошибка при остановке: {e}")
