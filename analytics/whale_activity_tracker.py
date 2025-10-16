#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whale Activity Tracker
Отслеживание крупных ордеров (китов) с сохранением в БД
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import deque
from config.settings import logger


class WhaleActivityTracker:
    """
    Отслеживание активности китов (крупных ордеров)
    Критерии "кита":
    - BTC: > $100,000
    - ETH: > $50,000
    - Остальные: > $25,000

    ✅ С ПОДДЕРЖКОЙ БАЗЫ ДАННЫХ SQLite!
    """

    def __init__(self, window_minutes: int = 15, db_path: Optional[str] = None):
        self.window_minutes = window_minutes
        self.whale_trades = {}

        self.whale_thresholds = {
            "BTCUSDT": 100000,
            "ETHUSDT": 50000,
            "SOLUSDT": 25000,
            "BNBUSDT": 25000,
            "XRPUSDT": 25000,
            "DOGEUSDT": 25000,
            "ADAUSDT": 25000,
            "AVAXUSDT": 25000,
        }
        self.default_threshold = 25000

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
                logger.info("✅ Таблица large_trades готова")
        except Exception as e:
            logger.error(f"❌ _init_database: {e}", exc_info=True)

    def add_trade(self, symbol: str, side: str, size: float, price: float) -> bool:
        """Добавить сделку (проверить кита)"""
        try:
            value = size * price
            threshold = self.whale_thresholds.get(symbol, self.default_threshold)

            if value >= threshold:
                timestamp = datetime.now()

                # 1. Сохранить в память
                if symbol not in self.whale_trades:
                    self.whale_trades[symbol] = deque(maxlen=100)

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

                logger.info(f"🐋 WHALE: {symbol} {side} ${value:,.0f}")
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
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO large_trades
                    (symbol, side, size, price, size_usd, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (symbol, side, size, price, size_usd, timestamp),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"❌ _save_to_database: {e}", exc_info=True)

    def get_recent_whales(
        self, symbol: str, minutes: Optional[int] = None
    ) -> List[Dict]:
        """Получить киты из памяти"""
        try:
            if symbol not in self.whale_trades:
                return []

            if minutes is None:
                minutes = self.window_minutes

            cutoff_time = datetime.now() - timedelta(minutes=minutes)
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
        self, symbol: str, minutes: Optional[int] = None
    ) -> List[Dict]:
        """Получить киты из БД"""
        if not self.db_path:
            return []

        try:
            if minutes is None:
                minutes = self.window_minutes

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT symbol, side, size, price, size_usd, timestamp
                    FROM large_trades
                    WHERE symbol = ?
                      AND timestamp > datetime('now', '-' || ? || ' minutes')
                    ORDER BY timestamp DESC
                """,
                    (symbol, minutes),
                )

                rows = cursor.fetchall()
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

    def cleanup_old_trades(self):
        """Очистка старых сделок"""
        try:
            cutoff_time = datetime.now() - timedelta(minutes=self.window_minutes)

            for symbol in list(self.whale_trades.keys()):
                recent = [
                    trade
                    for trade in self.whale_trades[symbol]
                    if trade["timestamp"] >= cutoff_time
                ]

                if recent:
                    self.whale_trades[symbol] = deque(recent, maxlen=100)
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
