#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whale Activity Tracker
Отслеживание крупных ордеров (китов) за последние 15 минут
"""

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
    """

    def __init__(self, window_minutes: int = 15):
        self.window_minutes = window_minutes

        # Хранилище крупных ордеров по символам
        # {symbol: deque([{timestamp, side, size, price, value}, ...])}
        self.whale_trades = {}

        # Пороги для определения "кита" (в USD)
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

        logger.info(f"✅ WhaleActivityTracker инициализирован (window: {window_minutes}m)")

    def add_trade(self, symbol: str, side: str, size: float, price: float) -> bool:
        """
        Добавить сделку и проверить, является ли она "китовой"

        Args:
            symbol: Торговая пара
            side: BUY или SELL
            size: Объём сделки
            price: Цена сделки

        Returns:
            True если это китовая сделка
        """
        try:
            value = size * price
            threshold = self.whale_thresholds.get(symbol, self.default_threshold)

            # Проверяем, является ли сделка "китовой"
            if value >= threshold:
                if symbol not in self.whale_trades:
                    self.whale_trades[symbol] = deque(maxlen=100)  # Храним до 100 последних

                trade = {
                    "timestamp": datetime.now(),
                    "side": side.upper(),
                    "size": size,
                    "price": price,
                    "value": value,
                }

                self.whale_trades[symbol].append(trade)
                logger.info(f"🐋 WHALE DETECTED: {symbol} {side} ${value:,.0f}")
                return True

            return False

        except Exception as e:
            logger.error(f"add_trade error: {e}")
            return False

    def get_recent_whales(self, symbol: str, minutes: Optional[int] = None) -> List[Dict]:
        """
        Получить крупные ордера за последние N минут

        Args:
            symbol: Торговая пара
            minutes: Временной интервал (по умолчанию self.window_minutes)

        Returns:
            Список китовых сделок
        """
        try:
            if symbol not in self.whale_trades:
                return []

            if minutes is None:
                minutes = self.window_minutes

            cutoff_time = datetime.now() - timedelta(minutes=minutes)

            # Фильтруем сделки по времени
            recent = [
                trade for trade in self.whale_trades[symbol]
                if trade["timestamp"] >= cutoff_time
            ]

            # Сортируем по времени (новые сначала)
            recent.sort(key=lambda x: x["timestamp"], reverse=True)

            return recent

        except Exception as e:
            logger.error(f"get_recent_whales error: {e}")
            return []

    def get_whale_summary(self, symbol: str, minutes: Optional[int] = None) -> Dict:
        """
        Получить сводку по китовой активности

        Returns:
            {
                "count": int,
                "buy_count": int,
                "sell_count": int,
                "buy_volume": float,
                "sell_volume": float,
                "net_volume": float,
                "largest_trade": Dict,
                "sentiment": str  # "BULLISH", "BEARISH", "NEUTRAL"
            }
        """
        try:
            whales = self.get_recent_whales(symbol, minutes)

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

            # Определяем sentiment
            if net_volume > 0:
                if buy_volume > sell_volume * 1.5:
                    sentiment = "BULLISH"
                else:
                    sentiment = "SLIGHTLY_BULLISH"
            elif net_volume < 0:
                if sell_volume > buy_volume * 1.5:
                    sentiment = "BEARISH"
                else:
                    sentiment = "SLIGHTLY_BEARISH"
            else:
                sentiment = "NEUTRAL"

            # Находим самую крупную сделку
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
            logger.error(f"get_whale_summary error: {e}")
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
        """Очистка старых сделок (старше window_minutes)"""
        try:
            cutoff_time = datetime.now() - timedelta(minutes=self.window_minutes)

            for symbol in list(self.whale_trades.keys()):
                # Фильтруем только актуальные сделки
                recent = [
                    trade for trade in self.whale_trades[symbol]
                    if trade["timestamp"] >= cutoff_time
                ]

                if recent:
                    self.whale_trades[symbol] = deque(recent, maxlen=100)
                else:
                    # Удаляем символ, если нет актуальных сделок
                    del self.whale_trades[symbol]

        except Exception as e:
            logger.error(f"cleanup_old_trades error: {e}")

    def format_whale_info(self, symbol: str, minutes: Optional[int] = None) -> str:
        """
        Форматирование информации о китах для отображения

        Returns:
            Строка с информацией о китовой активности
        """
        try:
            summary = self.get_whale_summary(symbol, minutes)

            if summary["count"] == 0:
                return "└─ No whale activity detected"

            lines = []

            # Общая статистика
            lines.append(f"├─ Whale Trades: {summary['count']} (🟢{summary['buy_count']} BUY / 🔴{summary['sell_count']} SELL)")

            # Объёмы
            if summary["buy_volume"] > 0:
                lines.append(f"├─ Buy Volume: ${summary['buy_volume']/1e6:.2f}M")
            if summary["sell_volume"] > 0:
                lines.append(f"├─ Sell Volume: ${summary['sell_volume']/1e6:.2f}M")

            # Net Volume
            net = summary["net_volume"]
            net_emoji = "🟢" if net > 0 else "🔴" if net < 0 else "⚪"
            lines.append(f"├─ Net Volume: {net_emoji} ${abs(net)/1e6:.2f}M")

            # Sentiment
            sentiment_emoji = self._get_sentiment_emoji(summary["sentiment"])
            lines.append(f"└─ Sentiment: {sentiment_emoji} {summary['sentiment']}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"format_whale_info error: {e}")
            return "└─ ⚠️ Whale data unavailable"

    def _get_sentiment_emoji(self, sentiment: str) -> str:
        """Получить emoji для sentiment"""
        mapping = {
            "BULLISH": "🚀",
            "SLIGHTLY_BULLISH": "🟢",
            "NEUTRAL": "⚪",
            "SLIGHTLY_BEARISH": "🔴",
            "BEARISH": "💀",
        }
        return mapping.get(sentiment, "⚪")
