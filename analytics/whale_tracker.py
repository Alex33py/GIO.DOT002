#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Whale Tracker для GIO Crypto Bot v3.0
Отслеживание крупных сделок (>$100K)
"""

import logging
import time
from typing import Dict, List
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class WhaleTrade:
    """Структура whale сделки"""

    timestamp: float
    symbol: str
    price: float
    quantity: float
    size_usd: float
    side: str  # BUY/SELL
    exchange: str


class WhaleTracker:
    """
    Отслеживание крупных сделок (whale trades)

    Features:
    - Детекция сделок >$100K
    - Хранение последних 5 минут активности
    - Подсчёт buy/sell давления китов
    - Алерты на экстремальную активность
    """

    def __init__(self, threshold_usd: float = 100000):
        """
        Args:
            threshold_usd: Порог для whale сделки в USD (по умолчанию $100K)
        """
        self.whale_threshold = threshold_usd
        self.recent_whales = defaultdict(list)  # symbol: [WhaleTrade]
        self.window_seconds = 300  # 5 минут

        # Статистика
        self.stats = {
            "total_whales_detected": 0,
            "total_buy_volume": 0,
            "total_sell_volume": 0,
        }

        logger.info("✅ WhaleTracker инициализирован")
        logger.info(f"   • Порог: ${self.whale_threshold:,.0f}")
        logger.info(f"   • Окно: {self.window_seconds}s")

    async def process_trade(self, symbol: str, trade: Dict, exchange: str = "Unknown"):
        """
        Обработка сделки на предмет whale activity

        Args:
            symbol: Торговая пара (BTCUSDT)
            trade: Словарь с данными сделки
                   {'price': float, 'quantity': float, 'side': 'BUY'/'SELL',
                    'timestamp': float}
            exchange: Биржа (Binance, Bybit, etc.)
        """
        try:
            # Рассчитать размер сделки в USD
            price = float(trade.get("price", 0))
            quantity = float(trade.get("quantity", 0))
            size_usd = price * quantity

            # Проверить порог
            if size_usd >= self.whale_threshold:
                # Это whale trade!
                whale_trade = WhaleTrade(
                    timestamp=trade.get("timestamp", time.time()),
                    symbol=symbol,
                    price=price,
                    quantity=quantity,
                    size_usd=size_usd,
                    side=trade.get("side", "UNKNOWN"),
                    exchange=exchange,
                )

                # Добавить в список
                self.recent_whales[symbol].append(whale_trade)

                # Обновить статистику
                self.stats["total_whales_detected"] += 1

                if whale_trade.side == "BUY":
                    self.stats["total_buy_volume"] += size_usd
                elif whale_trade.side == "SELL":
                    self.stats["total_sell_volume"] += size_usd

                logger.info(
                    f"🐋 WHALE TRADE: {symbol} {whale_trade.side} "
                    f"${size_usd:,.0f} @ ${price:,.2f} ({exchange})"
                )

                # Очистить старые данные
                await self._cleanup_old_trades(symbol)

                return whale_trade

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка в process_trade: {e}", exc_info=True)
            return None

    async def _cleanup_old_trades(self, symbol: str):
        """Удалить сделки старше 5 минут"""
        try:
            if symbol not in self.recent_whales:
                return

            cutoff_time = time.time() - self.window_seconds

            # Фильтровать только недавние
            self.recent_whales[symbol] = [
                trade
                for trade in self.recent_whales[symbol]
                if trade.timestamp > cutoff_time
            ]

            # Удалить ключ если список пустой
            if not self.recent_whales[symbol]:
                del self.recent_whales[symbol]

        except Exception as e:
            logger.error(f"❌ Ошибка в _cleanup_old_trades: {e}")

    def get_whale_activity(self, symbol: str) -> Dict:
        """
        Получить активность китов за последние 5 минут

        Args:
            symbol: Торговая пара

        Returns:
            Dict с данными активности:
            {
                'trades': int,
                'buy_volume': float,
                'sell_volume': float,
                'net': float,
                'dominant_side': str,
                'whale_trades': List[WhaleTrade]
            }
        """
        try:
            # Очистить старые данные
            cutoff_time = time.time() - self.window_seconds

            if symbol in self.recent_whales:
                self.recent_whales[symbol] = [
                    trade
                    for trade in self.recent_whales[symbol]
                    if trade.timestamp > cutoff_time
                ]

            # Если нет данных
            if symbol not in self.recent_whales or not self.recent_whales[symbol]:
                return {
                    "trades": 0,
                    "buy_volume": 0,
                    "sell_volume": 0,
                    "net": 0,
                    "dominant_side": "neutral",
                    "whale_trades": [],
                }

            trades = self.recent_whales[symbol]

            # Подсчитать объёмы
            buy_vol = sum(t.size_usd for t in trades if t.side == "BUY")
            sell_vol = sum(t.size_usd for t in trades if t.side == "SELL")
            net = buy_vol - sell_vol

            # Определить доминирующую сторону
            if abs(net) < (buy_vol + sell_vol) * 0.2:
                dominant_side = "neutral"
            elif net > 0:
                dominant_side = "bullish"
            else:
                dominant_side = "bearish"

            return {
                "trades": len(trades),
                "buy_volume": buy_vol,
                "sell_volume": sell_vol,
                "net": net,
                "dominant_side": dominant_side,
                "whale_trades": trades,
            }

        except Exception as e:
            logger.error(f"❌ Ошибка в get_whale_activity: {e}", exc_info=True)
            return {
                "trades": 0,
                "buy_volume": 0,
                "sell_volume": 0,
                "net": 0,
                "dominant_side": "neutral",
                "whale_trades": [],
            }

    def get_all_activity(self) -> Dict[str, Dict]:
        """Получить активность китов по всем парам"""
        result = {}

        for symbol in list(self.recent_whales.keys()):
            result[symbol] = self.get_whale_activity(symbol)

        return result

    def get_stats(self) -> Dict:
        """Получить общую статистику"""
        total_volume = self.stats["total_buy_volume"] + self.stats["total_sell_volume"]

        return {
            "total_whales_detected": self.stats["total_whales_detected"],
            "total_buy_volume": self.stats["total_buy_volume"],
            "total_sell_volume": self.stats["total_sell_volume"],
            "total_volume": total_volume,
            "buy_dominance": (
                (self.stats["total_buy_volume"] / max(1, total_volume)) * 100
            ),
            "active_symbols": len(self.recent_whales),
        }

    def format_activity_message(self, symbol: str) -> str:
        """Форматировать сообщение об активности для Telegram"""
        activity = self.get_whale_activity(symbol)

        if activity["trades"] == 0:
            return f"🐋 {symbol}: Нет активности китов за последние 5 минут"

        # Эмодзи по доминирующей стороне
        if activity["dominant_side"] == "bullish":
            emoji = "🟢"
            sentiment = "Bullish"
        elif activity["dominant_side"] == "bearish":
            emoji = "🔴"
            sentiment = "Bearish"
        else:
            emoji = "⚪"
            sentiment = "Neutral"

        message = f"""🐋 WHALE ACTIVITY: {symbol}

Trades: {activity['trades']}
Buy Vol: ${activity['buy_volume']:,.0f}
Sell Vol: ${activity['sell_volume']:,.0f}
Net: ${activity['net']:+,.0f}

{emoji} Sentiment: {sentiment}

⏰ Last 5 minutes
"""

        return message


# Пример интеграции в dashboard
def integrate_whale_tracker_to_dashboard():
    """Пример кода для интеграции в /market команду"""

    code_example = """
# В telegram/handlers/dashboard_handler.py

async def cmd_market(self, update, context):
    # ... существующий код ...

    # Получить whale activity
    whale_activity = self.bot.whale_tracker.get_whale_activity(symbol)

    # Форматирование для дашборда
    if whale_activity['trades'] > 0:
        whale_emoji = "🐋"
        whale_sentiment = (
            "🟢 Bullish" if whale_activity['dominant_side'] == 'bullish'
            else "🔴 Bearish" if whale_activity['dominant_side'] == 'bearish'
            else "⚪ Neutral"
        )
    else:
        whale_emoji = "💤"
        whale_sentiment = "⚪ Neutral"

    message += f'''
🐋 WHALE ACTIVITY (5min)
├─ Trades: {whale_activity['trades']}
├─ Buy Vol: ${whale_activity['buy_volume']:,.2f}
├─ Sell Vol: ${whale_activity['sell_volume']:,.2f}
└─ Net: ${whale_activity['net']:+,.2f} {whale_sentiment}
'''

    # ... остальной код ...
"""

    return code_example


if __name__ == "__main__":
    # Тестирование
    import asyncio

    async def test_whale_tracker():
        tracker = WhaleTracker(threshold_usd=100000)

        # Симуляция сделок
        trades = [
            {"price": 113000, "quantity": 1.2, "side": "BUY", "timestamp": time.time()},
            {
                "price": 113000,
                "quantity": 0.5,
                "side": "SELL",
                "timestamp": time.time(),
            },
            {"price": 113100, "quantity": 2.5, "side": "BUY", "timestamp": time.time()},
        ]

        for trade in trades:
            result = await tracker.process_trade("BTCUSDT", trade, "Binance")
            if result:
                print(f"Whale detected: {result.side} ${result.size_usd:,.0f}")

        # Получить активность
        activity = tracker.get_whale_activity("BTCUSDT")
        print(f"\nActivity: {activity}")

        # Получить статистику
        stats = tracker.get_stats()
        print(f"\nStats: {stats}")

        # Форматированное сообщение
        message = tracker.format_activity_message("BTCUSDT")
        print(f"\n{message}")

    asyncio.run(test_whale_tracker())
