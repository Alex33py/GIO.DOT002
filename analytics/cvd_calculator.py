# -*- coding: utf-8 -*-
"""
CVD Calculator - Cumulative Volume Delta
Отслеживает накопленный дисбаланс покупок/продаж
"""

import asyncio
from collections import deque, defaultdict
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta

from config.settings import logger


class CVDCalculator:
    """
    Калькулятор Cumulative Volume Delta (CVD)

    CVD = Cumulative(BUY_VOLUME - SELL_VOLUME)
    Показывает преобладание покупателей или продавцов
    """

    def __init__(self, window_size: int = 100):
        """
        Args:
            window_size: Размер окна для rolling CVD (количество trades)
        """
        self.window_size = window_size

        # Cumulative CVD (от начала сессии)
        self.cumulative_cvd: Dict[str, float] = defaultdict(float)

        # Rolling CVD (последние N trades)
        self.rolling_trades: Dict[str, deque] = defaultdict(
            lambda: deque(maxlen=window_size)
        )

        # Trade history для анализа
        self.trade_history: Dict[str, list] = defaultdict(list)

        # CVD trend detection
        self.cvd_trend: Dict[str, str] = defaultdict(lambda: "NEUTRAL")

        # Statistics
        self.stats = {
            "total_trades": 0,
            "buy_volume": defaultdict(float),
            "sell_volume": defaultdict(float),
        }

        logger.info("✅ CVDCalculator инициализирован (window: %d)", window_size)

    def update(
        self, symbol: str, side: str, volume: float, price: float, timestamp: int = None
    ) -> float:
        """
        Обновить CVD на основе нового trade

        Args:
            symbol: Символ (BTCUSDT)
            side: BUY или SELL
            volume: Объем сделки
            price: Цена сделки
            timestamp: Unix timestamp (ms)

        Returns:
            Current cumulative CVD
        """
        if timestamp is None:
            timestamp = int(datetime.now().timestamp() * 1000)

        # Delta для этого trade
        delta = volume if side == "BUY" else -volume

        # Update cumulative CVD
        self.cumulative_cvd[symbol] += delta

        # Add to rolling window
        trade_data = {
            "timestamp": timestamp,
            "side": side,
            "volume": volume,
            "price": price,
            "delta": delta,
        }
        self.rolling_trades[symbol].append(trade_data)

        # Add to history (keep last 1000)
        self.trade_history[symbol].append(trade_data)
        if len(self.trade_history[symbol]) > 1000:
            self.trade_history[symbol] = self.trade_history[symbol][-1000:]

        # Update statistics
        self.stats["total_trades"] += 1
        if side == "BUY":
            self.stats["buy_volume"][symbol] += volume
        else:
            self.stats["sell_volume"][symbol] += volume

        # Update trend
        self._update_trend(symbol)

        return self.cumulative_cvd[symbol]

    def get_cvd(self, symbol: str) -> float:
        """Получить текущий cumulative CVD"""
        return self.cumulative_cvd.get(symbol, 0.0)

    def get_rolling_cvd(self, symbol: str) -> float:
        """Получить rolling CVD (последние N trades)"""
        if symbol not in self.rolling_trades:
            return 0.0

        return sum(trade["delta"] for trade in self.rolling_trades[symbol])

    def get_cvd_trend(self, symbol: str, window: int = None) -> Dict:
        """
        Получить CVD trend и силу тренда

        Args:
            symbol: Символ
            window: Количество trades для анализа (по умолчанию self.window_size)

        Returns:
            {
                'trend': 'BULLISH' | 'BEARISH' | 'NEUTRAL',
                'strength': 0-100,
                'cvd': current CVD,
                'rolling_cvd': rolling CVD,
                'delta_ma': moving average of deltas
            }
        """
        if symbol not in self.rolling_trades:
            return {
                "trend": "NEUTRAL",
                "strength": 0,
                "cvd": 0.0,
                "rolling_cvd": 0.0,
                "delta_ma": 0.0,
            }

        window = window or self.window_size
        trades = list(self.rolling_trades[symbol])[-window:]

        if not trades:
            return {
                "trend": "NEUTRAL",
                "strength": 0,
                "cvd": self.get_cvd(symbol),
                "rolling_cvd": 0.0,
                "delta_ma": 0.0,
            }

        # Calculate rolling CVD
        rolling_cvd = sum(t["delta"] for t in trades)

        # Calculate delta moving average
        delta_ma = rolling_cvd / len(trades) if trades else 0.0

        # Determine trend
        cumulative_cvd = self.get_cvd(symbol)

        # Trend logic
        if rolling_cvd > 0 and delta_ma > 0:
            trend = "BULLISH"
            # Strength based on how positive rolling_cvd is
            max_volume = sum(t["volume"] for t in trades)
            strength = (
                min(100, int((rolling_cvd / max_volume) * 100))
                if max_volume > 0
                else 50
            )
        elif rolling_cvd < 0 and delta_ma < 0:
            trend = "BEARISH"
            max_volume = sum(t["volume"] for t in trades)
            strength = (
                min(100, int((abs(rolling_cvd) / max_volume) * 100))
                if max_volume > 0
                else 50
            )
        else:
            trend = "NEUTRAL"
            strength = 50

        return {
            "trend": trend,
            "strength": strength,
            "cvd": cumulative_cvd,
            "rolling_cvd": rolling_cvd,
            "delta_ma": delta_ma,
        }

    def _update_trend(self, symbol: str):
        """Внутренний метод для обновления тренда"""
        trend_data = self.get_cvd_trend(symbol)
        self.cvd_trend[symbol] = trend_data["trend"]

    def get_cvd_divergence(self, symbol: str, price_trend: str) -> Dict:
        """
        Обнаружить дивергенцию между CVD и ценой

        Args:
            symbol: Символ
            price_trend: 'UPTREND' | 'DOWNTREND' | 'NEUTRAL'

        Returns:
            {
                'divergence': bool,
                'type': 'BULLISH' | 'BEARISH' | 'NONE',
                'strength': 0-100
            }
        """
        cvd_data = self.get_cvd_trend(symbol)
        cvd_trend = cvd_data["trend"]

        # Bullish divergence: Price down, CVD up
        if price_trend == "DOWNTREND" and cvd_trend == "BULLISH":
            return {
                "divergence": True,
                "type": "BULLISH",
                "strength": cvd_data["strength"],
            }

        # Bearish divergence: Price up, CVD down
        if price_trend == "UPTREND" and cvd_trend == "BEARISH":
            return {
                "divergence": True,
                "type": "BEARISH",
                "strength": cvd_data["strength"],
            }

        return {"divergence": False, "type": "NONE", "strength": 0}

    def get_buy_sell_ratio(self, symbol: str, window: int = None) -> Dict:
        """
        Получить соотношение BUY/SELL

        Returns:
            {
                'buy_volume': float,
                'sell_volume': float,
                'ratio': float (buy/sell),
                'buy_percent': 0-100,
                'sell_percent': 0-100
            }
        """
        window = window or self.window_size
        trades = (
            list(self.rolling_trades[symbol])[-window:]
            if symbol in self.rolling_trades
            else []
        )

        buy_volume = sum(t["volume"] for t in trades if t["side"] == "BUY")
        sell_volume = sum(t["volume"] for t in trades if t["side"] == "SELL")
        total_volume = buy_volume + sell_volume

        ratio = buy_volume / sell_volume if sell_volume > 0 else float("inf")
        buy_percent = (buy_volume / total_volume * 100) if total_volume > 0 else 0
        sell_percent = (sell_volume / total_volume * 100) if total_volume > 0 else 0

        return {
            "buy_volume": buy_volume,
            "sell_volume": sell_volume,
            "ratio": ratio,
            "buy_percent": buy_percent,
            "sell_percent": sell_percent,
        }

    def reset(self, symbol: str = None):
        """Сбросить CVD для символа или всех символов"""
        if symbol:
            self.cumulative_cvd[symbol] = 0.0
            self.rolling_trades[symbol].clear()
            self.trade_history[symbol].clear()
            self.stats["buy_volume"][symbol] = 0.0
            self.stats["sell_volume"][symbol] = 0.0
        else:
            self.cumulative_cvd.clear()
            self.rolling_trades.clear()
            self.trade_history.clear()
            self.stats["buy_volume"].clear()
            self.stats["sell_volume"].clear()
            self.stats["total_trades"] = 0

        logger.info(f"🔄 CVD reset: {symbol if symbol else 'ALL'}")

    def get_stats(self, symbol: str = None) -> Dict:
        """Получить статистику CVD"""
        if symbol:
            return {
                "symbol": symbol,
                "cumulative_cvd": self.cumulative_cvd.get(symbol, 0.0),
                "rolling_cvd": self.get_rolling_cvd(symbol),
                "trend": self.cvd_trend.get(symbol, "NEUTRAL"),
                "buy_volume": self.stats["buy_volume"].get(symbol, 0.0),
                "sell_volume": self.stats["sell_volume"].get(symbol, 0.0),
                "trades_count": len(self.trade_history.get(symbol, [])),
            }
        else:
            return {
                "total_trades": self.stats["total_trades"],
                "symbols": list(self.cumulative_cvd.keys()),
                "stats_by_symbol": {
                    sym: self.get_stats(sym) for sym in self.cumulative_cvd.keys()
                },
            }


# Экспорт
__all__ = ["CVDCalculator"]
