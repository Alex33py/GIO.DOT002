#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whale Activity Tracker
Отслеживание крупных ордеров (китов) с сохранением в БД
"""

import sqlite3
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Optional
from collections import deque
from config.settings import logger
from connectors.whale_log_batcher import WhaleLogBatcher  # ✅ ПРОВЕРИТЬ ПУТЬ!


class WhaleActivityTracker:
    """
    Отслеживание активности китов (крупных ордеров)
    Критерии "кита":
    - BTC: > $10,000
    - ETH: > $5,000
    - Остальные: > $2,500

    ✅ С ПОДДЕРЖКОЙ БАЗЫ ДАННЫХ SQLite!CVD!
    """

    def __init__(self, window_minutes: int = 15, db_path: Optional[str] = None, enable_batcher: bool = True):
        self.window_minutes = window_minutes
        self.whale_trades = {}

        self.whale_thresholds = {
            "BTCUSDT": 10000,  # $10,000
            "ETHUSDT": 5000,   # $5,000
            "SOLUSDT": 2500,   # $2,500
            "BNBUSDT": 2500,   # $2,500
            "XRPUSDT": 2500,   # $2,500
            "DOGEUSDT": 2500,  # $2,500
            "ADAUSDT": 2500,   # $2,500
            "AVAXUSDT": 2500,  # $2,500
        }
        self.default_threshold = 2500  # $2,500

        # ✅ ДОБАВЛЕНО: Накопление CVD данных
        self.trade_data = {}  # {"BTCUSDT": {"buy_volume": 0, "sell_volume": 0, ...}}

        # ✅ ИНИЦИАЛИЗАЦИЯ BATCHER!
        if enable_batcher:
            try:
                self.whale_log_batcher = WhaleLogBatcher()
                logger.info("✅ WhaleLogBatcher инициализирован (batch_interval=60s)")
            except Exception as e:
                logger.warning(f"⚠️ WhaleLogBatcher не инициализирован: {e}")
                self.whale_log_batcher = None
        else:
            self.whale_log_batcher = None
            logger.info("ℹ️ WhaleLogBatcher отключен")

        # ✅ ДОБАВИТЬ ПОДДЕРЖКУ БД
        self.db_path = db_path
        if self.db_path:
            self._init_database()
            logger.info(f"✅ WhaleActivityTracker с БД: {db_path}")
        else:
            logger.info(f"✅ WhaleActivityTracker БЕЗ БД (только RAM)")


    def _init_database(self):
        """Создать таблицу large_trades"""
        if not self.db_path:
            return
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA journal_mode=WAL")
                cursor.execute("PRAGMA synchronous=NORMAL")
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS large_trades (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL,
                        size REAL NOT NULL,
                        price REAL NOT NULL,
                        size_usd REAL NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_large_trades_timestamp
                    ON large_trades(timestamp)
                """
                )
                cursor.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_large_trades_symbol
                    ON large_trades(symbol)
                """
                )
                conn.commit()
                logger.info("✅ Таблица large_trades готова (WAL режим)")
        except Exception as e:
            logger.error(f"❌ _init_database: {e}", exc_info=True)

    def get_cvd_percent(self, symbol: str) -> float:
        """
        Возвращает CVD % для символа

        Args:
            symbol: Торговая пара (BTCUSDT)

        Returns:
            float: CVD процент (например, +15.5 = покупки доминируют)
        """
        if symbol not in self.trade_data:
            return 0.0

        data = self.trade_data[symbol]
        buy_vol = data.get("buy_volume", 0.0)
        sell_vol = data.get("sell_volume", 0.0)
        total_vol = buy_vol + sell_vol

        if total_vol == 0:
            return 0.0

        cvd_pct = ((buy_vol - sell_vol) / total_vol) * 100
        return cvd_pct

    def get_trade_data(self, symbol: str) -> Dict:
        """
        Возвращает накопленные данные по символу для CVD

        Args:
            symbol: Торговая пара

        Returns:
            Dict с ключами:
                - buy_volume: float
                - sell_volume: float
                - total_trades: int
                - cvd_percent: float
                - last_update: datetime
        """
        if symbol not in self.trade_data:
            return {
                "buy_volume": 0.0,
                "sell_volume": 0.0,
                "total_trades": 0,
                "cvd_percent": 0.0,
                "last_update": None,
            }

        data = self.trade_data[symbol].copy()
        data["cvd_percent"] = self.get_cvd_percent(symbol)
        return data

    def add_trade(self, symbol: str, side: str, size: float, price: float) -> bool:
        """Добавить сделку (проверить кита)"""
        try:
            value = size * price
            threshold = self.whale_thresholds.get(symbol, self.default_threshold)

            if symbol not in self.trade_data:
                self.trade_data[symbol] = {
                    "buy_volume": 0.0,
                    "sell_volume": 0.0,
                    "total_trades": 0,
                    "last_update": datetime.now(UTC),
                }

            # Обновляем объемы для CVD
            if side.upper() == "BUY":
                self.trade_data[symbol]["buy_volume"] += value
            elif side.upper() == "SELL":
                self.trade_data[symbol]["sell_volume"] += value

            self.trade_data[symbol]["total_trades"] += 1
            self.trade_data[symbol]["last_update"] = datetime.now(UTC)

            # === ОСТАЛЬНАЯ ЛОГИКА ДЛЯ КИТОВ (БЕЗ ИЗМЕНЕНИЙ) ===
            if value >= threshold:
                timestamp = datetime.now(UTC)

                # 1. Сохранить в память
                if symbol not in self.whale_trades:
                    self.whale_trades[symbol] = deque(maxlen=1000)

                trade = {
                    "timestamp": timestamp,
                    "side": side.upper(),
                    "size": size,
                    "price": price,
                    "value": value,
                }
                self.whale_trades[symbol].append(trade)

                # 2. ✅ Сохранить в БД
                if self.db_path:
                    self._save_to_database(
                        symbol, side.upper(), size, price, value, timestamp
                    )
                if self.whale_log_batcher:
                    self.whale_log_batcher.add_whale(symbol, side.upper(), value)

                return True

            return False

        except Exception as e:
            logger.error(f"❌ add_trade: {e}", exc_info=True)
            return False

    def _save_to_database(
        self,
        symbol: str,
        side: str,
        size: float,
        price: float,
        size_usd: float,
        timestamp: datetime,
    ):
        """Сохранить в БД"""
        conn = None
        try:
            conn = sqlite3.connect(self.db_path, timeout=10.0)
            cursor = conn.cursor()
            timestamp_local = timestamp.astimezone()
            timestamp_str = timestamp_local.strftime("%Y-%m-%d %H:%M:%S")

            cursor.execute(
                """
                INSERT INTO large_trades (symbol, side, size, price, size_usd, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (symbol, side, size, price, size_usd, timestamp_str),
            )
            conn.commit()

        except Exception as e:
            logger.error(f"❌ _save_to_database: {e}", exc_info=True)
        finally:
            if conn:
                conn.close()

    def get_recent_whales(
        self, symbol: str, minutes: Optional[int] = None
    ) -> List[Dict]:
        """Получить киты из памяти"""
        try:
            if symbol not in self.whale_trades:
                return []

            if minutes is None:
                minutes = self.window_minutes

            cutoff_time = datetime.now(UTC) - timedelta(minutes=minutes)
            recent = [
                trade
                for trade in self.whale_trades[symbol]
                if trade["timestamp"] >= cutoff_time
            ]
            recent.sort(key=lambda x: x["timestamp"], reverse=True)
            return recent

        except Exception as e:
            logger.error(f"❌ get_recent_whales: {e}", exc_info=True)
            return []

    def get_recent_whales_from_db(
        self, symbol: str, minutes: Optional[float] = None
    ) -> List[Dict]:
        """Получить киты из БД"""
        if not self.db_path:
            return []

        try:
            if minutes is None:
                minutes = self.window_minutes

            # ✅ ИСПРАВЛЕНИЕ: Используем STRFTIME БЕЗ TIMEZONE!
            seconds = int(minutes * 60)
            # Используем ЛОКАЛЬНОЕ время, т.к. SQLite не хранит timezone
            cutoff_local = datetime.now() - timedelta(seconds=seconds)
            cutoff_str = cutoff_local.strftime("%Y-%m-%d %H:%M:%S")

            # ✅ ДОБАВИТЬ DEBUG!
            logger.info(f"🔍 [DEBUG] Querying DB for {symbol}")
            logger.info(f"🔍 [DEBUG] DB path: {self.db_path}")  # ✅ ДОБАВИТЬ
            logger.info(f"🔍 [DEBUG] cutoff_str: {cutoff_str}")

            with sqlite3.connect(self.db_path, timeout=10.0) as conn:
                cursor = conn.cursor()

                # ✅ ДОБАВИТЬ: Показать ВСЕ записи в БД (без фильтра symbol)
                cursor.execute("SELECT COUNT(*) FROM large_trades")
                total_all = cursor.fetchone()[0]
                logger.info(f"🔍 [DEBUG] DB TOTAL (all symbols): {total_all} trades")

                # Старый запрос (с фильтром symbol)
                cursor.execute(
                    """
                    SELECT COUNT(*), MIN(timestamp), MAX(timestamp)
                    FROM large_trades
                    WHERE symbol = ?
                """,
                    (symbol,),
                )

                count_row = cursor.fetchone()
                logger.info(f"🔍 [DEBUG] DB total: {count_row[0]} trades")
                logger.info(f"🔍 [DEBUG] DB min timestamp: {count_row[1]}")
                logger.info(f"🔍 [DEBUG] DB max timestamp: {count_row[2]}")

                # ✅ ИСПРАВЛЕНИЕ: Сравниваем DATETIME strings в UTC!
                cursor.execute(
                    """
                    SELECT symbol, side, size, price, size_usd, timestamp
                    FROM large_trades
                    WHERE symbol = ?
                    AND datetime(timestamp) > datetime(?)
                    ORDER BY timestamp DESC
                """,
                    (symbol, cutoff_str),
                )

                rows = cursor.fetchall()
                logger.info(f"🔍 [DEBUG] DB returned {len(rows)} trades")

                trades = []
                for row in rows:
                    trades.append(
                        {
                            "symbol": row[0],
                            "side": row[1],
                            "size": row[2],
                            "price": row[3],
                            "value": row[4],
                            "timestamp": datetime.fromisoformat(row[5]),
                        }
                    )
                return trades

        except Exception as e:
            logger.error(f"❌ get_recent_whales_from_db: {e}", exc_info=True)
            return []

    def get_whale_summary(self, symbol: str, minutes: Optional[int] = None) -> Dict:
        """Получить сводку по китам"""
        try:
            # Сначала из памяти
            whales = self.get_recent_whales(symbol, minutes)

            # Если пусто, из БД
            if not whales and self.db_path:
                whales = self.get_recent_whales_from_db(symbol, minutes)

            if not whales:
                return {
                    "count": 0,
                    "buy_count": 0,
                    "sell_count": 0,
                    "buy_volume": 0,
                    "sell_volume": 0,
                    "net_volume": 0,
                    "largest_trade": None,
                    "sentiment": "NEUTRAL",
                }

            buy_trades = [t for t in whales if t["side"] == "BUY"]
            sell_trades = [t for t in whales if t["side"] == "SELL"]

            buy_volume = sum(t["value"] for t in buy_trades)
            sell_volume = sum(t["value"] for t in sell_trades)
            net_volume = buy_volume - sell_volume

            if net_volume > 0:
                sentiment = (
                    "BULLISH" if buy_volume > sell_volume * 1.5 else "SLIGHTLY_BULLISH"
                )
            elif net_volume < 0:
                sentiment = (
                    "BEARISH" if sell_volume > buy_volume * 1.5 else "SLIGHTLY_BEARISH"
                )
            else:
                sentiment = "NEUTRAL"

            largest = max(whales, key=lambda x: x["value"])

            return {
                "count": len(whales),
                "buy_count": len(buy_trades),
                "sell_count": len(sell_trades),
                "buy_volume": buy_volume,
                "sell_volume": sell_volume,
                "net_volume": net_volume,
                "largest_trade": largest,
                "sentiment": sentiment,
            }

        except Exception as e:
            logger.error(f"❌ get_whale_summary: {e}", exc_info=True)
            return {
                "count": 0,
                "buy_count": 0,
                "sell_count": 0,
                "buy_volume": 0,
                "sell_volume": 0,
                "net_volume": 0,
                "largest_trade": None,
                "sentiment": "NEUTRAL",
            }

    def get_whale_activity(self, symbol: str, timeframe_seconds: int = 300) -> Dict:
        """Получить активность китов за последние N секунд"""
        try:
            minutes = timeframe_seconds / 60

            # Приоритет БД
            if self.db_path:
                whales = self.get_recent_whales_from_db(symbol, minutes=minutes)
            else:
                whales = self.get_recent_whales(symbol, minutes=minutes)

            if not whales:
                return {
                    "trades": 0,
                    "buy_volume": 0,
                    "sell_volume": 0,
                    "net": 0,
                    "dominant_side": "neutral",
                }

            buy_trades = [t for t in whales if t["side"] == "BUY"]
            sell_trades = [t for t in whales if t["side"] == "SELL"]

            buy_volume = sum(t["value"] for t in buy_trades)
            sell_volume = sum(t["value"] for t in sell_trades)
            net = buy_volume - sell_volume

            if buy_volume > sell_volume * 1.2:
                dominant_side = "bullish"
            elif sell_volume > buy_volume * 1.2:
                dominant_side = "bearish"
            else:
                dominant_side = "neutral"

            return {
                "trades": len(whales),
                "buy_volume": buy_volume,
                "sell_volume": sell_volume,
                "net": net,
                "dominant_side": dominant_side,
            }

        except Exception as e:
            logger.error(f"❌ get_whale_activity: {e}", exc_info=True)
            return {
                "trades": 0,
                "buy_volume": 0,
                "sell_volume": 0,
                "net": 0,
                "dominant_side": "neutral",
            }

    def cleanup_old_trades(self):
        """Очистка старых сделок"""
        try:
            cutoff_time = datetime.now(UTC) - timedelta(minutes=self.window_minutes)

            for symbol in list(self.whale_trades.keys()):
                recent = [
                    trade
                    for trade in self.whale_trades[symbol]
                    if trade["timestamp"] >= cutoff_time
                ]

                if recent:
                    self.whale_trades[symbol] = deque(
                        recent, maxlen=1000
                    )  # ⬅️ УВЕЛИЧЕНО ДО 1000!
                else:
                    del self.whale_trades[symbol]

            # Очистка БД (старше 7 дней)
            if self.db_path:
                self._cleanup_old_db_trades()

        except Exception as e:
            logger.error(f"❌ cleanup_old_trades: {e}", exc_info=True)

    def _cleanup_old_db_trades(self, keep_days: int = 7):
        """Удалить старые записи из БД"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM large_trades
                    WHERE timestamp < datetime('now', '-' || ? || ' days')
                """,
                    (keep_days,),
                )
                deleted = cursor.rowcount
                conn.commit()

                if deleted > 0:
                    logger.info(f"🗑️ Удалено {deleted} старых whale trades")

        except Exception as e:
            logger.error(f"❌ _cleanup_old_db_trades: {e}", exc_info=True)

    def format_whale_info(self, symbol: str, minutes: Optional[int] = None) -> str:
        """Форматирование инфо о китах"""
        try:
            summary = self.get_whale_summary(symbol, minutes)

            if summary["count"] == 0:
                return "└─ No whale activity detected"

            lines = []
            lines.append(
                f"├─ Whale Trades: {summary['count']} (🟢{summary['buy_count']} BUY / 🔴{summary['sell_count']} SELL)"
            )

            if summary["buy_volume"] > 0:
                lines.append(f"├─ Buy Volume: ${summary['buy_volume']/1e6:.2f}M")
            if summary["sell_volume"] > 0:
                lines.append(f"├─ Sell Volume: ${summary['sell_volume']/1e6:.2f}M")

            net = summary["net_volume"]
            net_emoji = "🟢" if net > 0 else "🔴" if net < 0 else "⚪"
            lines.append(f"├─ Net Volume: {net_emoji} ${abs(net)/1e6:.2f}M")

            sentiment_emoji = self._get_sentiment_emoji(summary["sentiment"])
            lines.append(f"└─ Sentiment: {sentiment_emoji} {summary['sentiment']}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"❌ format_whale_info: {e}", exc_info=True)
            return "└─ ⚠️ Whale data unavailable"

    def _get_sentiment_emoji(self, sentiment: str) -> str:
        """Emoji для sentiment"""
        mapping = {
            "BULLISH": "🚀",
            "SLIGHTLY_BULLISH": "🟢",
            "NEUTRAL": "⚪",
            "SLIGHTLY_BEARISH": "🔴",
            "BEARISH": "💀",
        }
        return mapping.get(sentiment, "⚪")
