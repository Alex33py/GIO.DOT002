import aiosqlite
import logging
import os
import json
from typing import List, Dict, Optional, Any
from config.settings import DB_FILE, BATCH_SIZE
from models.data_classes import EnhancedTradingSignal, Alert
from utils.helpers import current_epoch_ms, validate_candle_data, validate_news_data

logger = logging.getLogger(__name__)


class EnhancedDatabase:
    """Расширенная база данных с оптимизированными запросами и аналитикой"""

    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        self.connection_pool = {}

    async def init_database(self):
        """Инициализация базы данных с созданием всех необходимых таблиц"""
        try:
            # Создаем директорию если не существует
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute("PRAGMA synchronous=NORMAL")
                await db.execute("PRAGMA cache_size=10000")
                await db.execute("PRAGMA temp_store=memory")

                # Создание основных таблиц
                await self._create_candles_table(db)
                await self._create_signals_table(db)
                await self._create_news_table(db)
                await self._create_alerts_table(db)
                await self._create_analytics_table(db)
                await self._create_roi_table(db)
                await self._create_volume_profile_table(db)
                await self._create_scenarios_table(db)

                await db.commit()
                logger.info("✅ База данных инициализирована успешно")

        except Exception as e:
            logger.error(f"Ошибка инициализации базы данных: {e}")
            raise

    async def _create_candles_table(self, db):
        """Создание таблицы свечей с оптимизированными индексами"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                volume REAL NOT NULL,
                created_at INTEGER NOT NULL,
                UNIQUE(symbol, timeframe, timestamp)
            )
        """)

        # Создаем индексы для быстрого поиска
        await db.execute("CREATE INDEX IF NOT EXISTS idx_candles_symbol_timeframe ON candles(symbol, timeframe)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_candles_timestamp ON candles(timestamp)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_candles_created_at ON candles(created_at)")

    async def _create_signals_table(self, db):
        """Создание таблицы торговых сигналов"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                scenario_id TEXT NOT NULL,
                status TEXT NOT NULL,
                level TEXT NOT NULL,
                price_entry REAL NOT NULL,
                sl REAL NOT NULL,
                tp1 REAL NOT NULL,
                tp2 REAL NOT NULL,
                tp3 REAL NOT NULL,
                rr1 REAL NOT NULL,
                rr2 REAL NOT NULL,
                rr3 REAL NOT NULL,
                confidence_score REAL DEFAULT 0.0,
                reason TEXT,
                indicators TEXT,
                market_conditions TEXT,
                news_impact TEXT,
                volume_profile_context TEXT,
                veto_reasons TEXT,
                timestamp INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)

        await db.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status)")

    async def _create_news_table(self, db):
        """Создание таблицы новостей с анализом настроений"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                news_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                url TEXT,
                source TEXT,
                published_at INTEGER NOT NULL,
                sentiment_score REAL DEFAULT 0.0,
                importance_score REAL DEFAULT 0.0,
                relevance_score REAL DEFAULT 0.0,
                categories TEXT,
                keywords TEXT,
                processed_at INTEGER NOT NULL,
                market_impact TEXT
            )
        """)

        await db.execute("CREATE INDEX IF NOT EXISTS idx_news_published_at ON news(published_at)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_news_sentiment ON news(sentiment_score)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_news_importance ON news(importance_score)")

    async def _create_alerts_table(self, db):
        """Создание таблицы системных алертов"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                symbol TEXT NOT NULL,
                message TEXT NOT NULL,
                severity TEXT NOT NULL,
                data TEXT,
                resolved BOOLEAN DEFAULT 0,
                timestamp INTEGER NOT NULL
            )
        """)

        await db.execute("CREATE INDEX IF NOT EXISTS idx_alerts_timestamp ON alerts(timestamp)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_alerts_severity ON alerts(severity)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_alerts_resolved ON alerts(resolved)")

    async def _create_analytics_table(self, db):
        """Создание таблицы аналитических данных"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS analytics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                timeframe TEXT NOT NULL,
                indicator_name TEXT NOT NULL,
                indicator_value REAL NOT NULL,
                additional_data TEXT,
                timestamp INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)

        await db.execute("CREATE INDEX IF NOT EXISTS idx_analytics_symbol_indicator ON analytics(symbol, indicator_name)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_analytics_timestamp ON analytics(timestamp)")

    async def _create_roi_table(self, db):
        """Создание таблицы для отслеживания ROI"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS roi_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                signal_id INTEGER,
                entry_price REAL NOT NULL,
                exit_price REAL,
                current_roi REAL DEFAULT 0.0,
                max_profit REAL DEFAULT 0.0,
                max_loss REAL DEFAULT 0.0,
                status TEXT DEFAULT 'active',
                exit_reason TEXT,
                hold_time_minutes INTEGER DEFAULT 0,
                timestamp INTEGER NOT NULL,
                FOREIGN KEY (signal_id) REFERENCES signals (id)
            )
        """)

    async def _create_volume_profile_table(self, db):
        """Создание таблицы объемного профиля"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS volume_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                price_level REAL NOT NULL,
                volume REAL NOT NULL,
                buy_volume REAL DEFAULT 0.0,
                sell_volume REAL DEFAULT 0.0,
                session_start INTEGER NOT NULL,
                session_end INTEGER NOT NULL,
                created_at INTEGER NOT NULL
            )
        """)

    async def _create_scenarios_table(self, db):
        """Создание таблицы сценариев"""
        await db.execute("""
            CREATE TABLE IF NOT EXISTS scenarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scenario_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                conditions TEXT NOT NULL,
                actions TEXT NOT NULL,
                active BOOLEAN DEFAULT 1,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
        """)

    async def save_candles_batch(self, candles_batch: List[Dict]):
        """Пакетное сохранение свечных данных с валидацией"""
        if not candles_batch:
            return 0

        try:
            valid_candles = []
            for candle in candles_batch:
                if validate_candle_data(candle):
                    valid_candles.append((
                        candle["symbol"],
                        candle["timeframe"],
                        candle["timestamp"],
                        candle["open"],
                        candle["high"],
                        candle["low"],
                        candle["close"],
                        candle["volume"],
                        current_epoch_ms()
                    ))

            if not valid_candles:
                logger.warning("Нет валидных свечей для сохранения")
                return 0

            async with aiosqlite.connect(self.db_path) as db:
                await db.executemany("""
                    INSERT OR REPLACE INTO candles
                    (symbol, timeframe, timestamp, open, high, low, close, volume, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, valid_candles)

                await db.commit()

            logger.info(f"✅ Сохранено {len(valid_candles)} свечей из {len(candles_batch)}")
            return len(valid_candles)

        except Exception as e:
            logger.error(f"Ошибка пакетного сохранения свечей: {e}")
            return 0

    async def save_enhanced_signal(self, signal: EnhancedTradingSignal) -> bool:
        """Сохранение расширенного торгового сигнала"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO signals (
                        symbol, side, scenario_id, status, level, price_entry,
                        sl, tp1, tp2, tp3, rr1, rr2, rr3, confidence_score,
                        reason, indicators, market_conditions, news_impact,
                        volume_profile_context, veto_reasons, timestamp, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal.symbol, signal.side, signal.scenario_id, signal.status.value,
                    signal.level.value, signal.price_entry, signal.sl, signal.tp1,
                    signal.tp2, signal.tp3, signal.rr1, signal.rr2, signal.rr3,
                    signal.confidence_score, signal.reason, json.dumps(signal.indicators),
                    json.dumps(signal.market_conditions), json.dumps(signal.news_impact),
                    json.dumps(signal.volume_profile_context),
                    json.dumps([veto.value for veto in signal.veto_reasons]),
                    signal.timestamp, current_epoch_ms()
                ))

                await db.commit()
                return True

        except Exception as e:
            logger.error(f"Ошибка сохранения сигнала: {e}")
            return False

    async def save_news_batch(self, news_batch: List[Dict]) -> int:
        """Пакетное сохранение новостей с анализом настроений"""
        if not news_batch:
            return 0

        try:
            valid_news = []
            for news in news_batch:
                if validate_news_data(news):
                    valid_news.append((
                        news["id"],
                        news["title"],
                        news.get("url", ""),
                        news.get("source", ""),
                        news.get("published_at", current_epoch_ms()),
                        news.get("sentiment_score", 0.0),
                        news.get("importance_score", 0.0),
                        news.get("relevance_score", 0.0),
                        json.dumps(news.get("categories", [])),
                        json.dumps(news.get("keywords", [])),
                        current_epoch_ms(),
                        json.dumps(news.get("market_impact", {}))
                    ))

            if not valid_news:
                return 0

            async with aiosqlite.connect(self.db_path) as db:
                await db.executemany("""
                    INSERT OR REPLACE INTO news
                    (news_id, title, url, source, published_at, sentiment_score,
                     importance_score, relevance_score, categories, keywords,
                     processed_at, market_impact)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, valid_news)

                await db.commit()

            return len(valid_news)

        except Exception as e:
            logger.error(f"Ошибка пакетного сохранения новостей: {e}")
            return 0

    async def save_alert(self, alert: Alert) -> bool:
        """Сохранение системного алерта"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("""
                    INSERT INTO alerts (alert_type, symbol, message, severity, data, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    alert.alert_type.value, alert.symbol, alert.message,
                    alert.severity, json.dumps(alert.data), alert.timestamp
                ))

                await db.commit()
                return True

        except Exception as e:
            logger.error(f"Ошибка сохранения алерта: {e}")
            return False

    async def get_recent_candles(self, symbol: str, timeframe: str, limit: int = 100) -> List[Dict]:
        """Получение последних свечей"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row

                async with db.execute("""
                    SELECT * FROM candles
                    WHERE symbol = ? AND timeframe = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (symbol, timeframe, limit)) as cursor:

                    rows = await cursor.fetchall()
                    return [dict(row) for row in reversed(rows)]

        except Exception as e:
            logger.error(f"Ошибка получения свечей: {e}")
            return []

    async def get_active_signals(self, symbol: str = None) -> List[Dict]:
        """Получение активных сигналов"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row

                query = "SELECT * FROM signals WHERE status IN ('deal', 'risky_entry')"
                params = []

                if symbol:
                    query += " AND symbol = ?"
                    params.append(symbol)

                query += " ORDER BY timestamp DESC"

                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Ошибка получения активных сигналов: {e}")
            return []

    async def get_recent_news(self, hours: int = 24, min_importance: float = 0.0) -> List[Dict]:
        """Получение последних новостей с фильтрацией по важности"""
        try:
            time_threshold = current_epoch_ms() - (hours * 3600 * 1000)

            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row

                async with db.execute("""
                    SELECT * FROM news
                    WHERE published_at > ? AND importance_score >= ?
                    ORDER BY published_at DESC
                """, (time_threshold, min_importance)) as cursor:

                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Ошибка получения новостей: {e}")
            return []

    async def get_unresolved_alerts(self, severity: str = None) -> List[Dict]:
        """Получение нерешенных алертов"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row

                query = "SELECT * FROM alerts WHERE resolved = 0"
                params = []

                if severity:
                    query += " AND severity = ?"
                    params.append(severity)

                query += " ORDER BY timestamp DESC"

                async with db.execute(query, params) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]

        except Exception as e:
            logger.error(f"Ошибка получения алертов: {e}")
            return []

    async def get_performance_stats(self, days: int = 30) -> Dict:
        """Получение статистики производительности"""
        try:
            time_threshold = current_epoch_ms() - (days * 24 * 3600 * 1000)

            async with aiosqlite.connect(self.db_path) as db:
                # Общая статистика сигналов
                async with db.execute("""
                    SELECT
                        COUNT(*) as total_signals,
                        AVG(confidence_score) as avg_confidence,
                        COUNT(CASE WHEN status = 'deal' THEN 1 END) as deal_signals,
                        COUNT(CASE WHEN status = 'vetoed' THEN 1 END) as vetoed_signals
                    FROM signals
                    WHERE timestamp > ?
                """, (time_threshold,)) as cursor:

                    signal_stats = await cursor.fetchone()

                # Статистика новостей
                async with db.execute("""
                    SELECT
                        COUNT(*) as total_news,
                        AVG(sentiment_score) as avg_sentiment,
                        AVG(importance_score) as avg_importance
                    FROM news
                    WHERE processed_at > ?
                """, (time_threshold,)) as cursor:

                    news_stats = await cursor.fetchone()

                # Статистика алертов
                async with db.execute("""
                    SELECT
                        COUNT(*) as total_alerts,
                        COUNT(CASE WHEN resolved = 1 THEN 1 END) as resolved_alerts,
                        COUNT(CASE WHEN severity = 'HIGH' THEN 1 END) as high_severity_alerts
                    FROM alerts
                    WHERE timestamp > ?
                """, (time_threshold,)) as cursor:

                    alert_stats = await cursor.fetchone()

                return {
                    "period_days": days,
                    "signals": dict(signal_stats) if signal_stats else {},
                    "news": dict(news_stats) if news_stats else {},
                    "alerts": dict(alert_stats) if alert_stats else {},
                    "generated_at": current_epoch_ms()
                }

        except Exception as e:
            logger.error(f"Ошибка получения статистики: {e}")
            return {}

    async def cleanup_old_data(self, days_to_keep: int = 90):
        """Очистка старых данных для оптимизации базы"""
        try:
            cutoff_time = current_epoch_ms() - (days_to_keep * 24 * 3600 * 1000)

            async with aiosqlite.connect(self.db_path) as db:
                # Удаляем старые свечи
                await db.execute("DELETE FROM candles WHERE created_at < ?", (cutoff_time,))
                candles_deleted = db.total_changes

                # Удаляем старые новости
                await db.execute("DELETE FROM news WHERE processed_at < ?", (cutoff_time,))
                news_deleted = db.total_changes - candles_deleted

                # Удаляем решенные алерты старше месяца
                month_cutoff = current_epoch_ms() - (30 * 24 * 3600 * 1000)
                await db.execute("""
                    DELETE FROM alerts
                    WHERE resolved = 1 AND timestamp < ?
                """, (month_cutoff,))
                alerts_deleted = db.total_changes - candles_deleted - news_deleted

                await db.commit()

                # Сжатие базы данных
                await db.execute("VACUUM")

                logger.info(f"🧹 Очистка БД: свечи={candles_deleted}, новости={news_deleted}, алерты={alerts_deleted}")

        except Exception as e:
            logger.error(f"Ошибка очистки БД: {e}")
