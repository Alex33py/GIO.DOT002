# === ФАЙЛ: modules/trade_data_accumulator.py ===

import asyncio
from collections import defaultdict
from typing import Dict, Optional
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class TradeDataAccumulator:
    """
    Накопитель данных о сделках для расчета CVD
    """

    def __init__(self, window_minutes: int = 60):
        self.window_minutes = window_minutes
        self.trade_data: Dict[str, Dict] = defaultdict(lambda: {
            "buy_volume": 0.0,
            "sell_volume": 0.0,
            "total_trades": 0,
            "last_update": datetime.now()
        })
        self._lock = asyncio.Lock()

    async def add_trade(self, symbol: str, side: str, volume: float, timestamp: Optional[datetime] = None):
        """
        Добавляет сделку в накопитель

        Args:
            symbol: Торговая пара (BTCUSDT)
            side: buy или sell
            volume: Объем сделки в USD
            timestamp: Время сделки (default: now)
        """
        async with self._lock:
            if symbol not in self.trade_data:
                self.trade_data[symbol] = {
                    "buy_volume": 0.0,
                    "sell_volume": 0.0,
                    "total_trades": 0,
                    "last_update": datetime.now()
                }

            data = self.trade_data[symbol]

            # Обновляем объемы
            if side.lower() == "buy":
                data["buy_volume"] += volume
            elif side.lower() == "sell":
                data["sell_volume"] += volume

            data["total_trades"] += 1
            data["last_update"] = timestamp or datetime.now()

            logger.debug(f"TradeData updated: {symbol} - {side} vol={volume:.2f} | Total Buy={data['buy_volume']:.2f}, Sell={data['sell_volume']:.2f}")

    def get_trade_data(self, symbol: str) -> Dict:
        """
        Возвращает накопленные данные по символу

        Returns:
            {
                "buy_volume": float,
                "sell_volume": float,
                "total_trades": int,
                "cvd_percent": float,
                "last_update": datetime
            }
        """
        if symbol not in self.trade_data:
            return {
                "buy_volume": 0.0,
                "sell_volume": 0.0,
                "total_trades": 0,
                "cvd_percent": 0.0,
                "last_update": None
            }

        data = self.trade_data[symbol].copy()

        # Расчет CVD %
        total_vol = data["buy_volume"] + data["sell_volume"]
        if total_vol > 0:
            data["cvd_percent"] = ((data["buy_volume"] - data["sell_volume"]) / total_vol) * 100
        else:
            data["cvd_percent"] = 0.0

        return data

    async def cleanup_old_data(self):
        """
        Очищает данные старше window_minutes
        """
        async with self._lock:
            now = datetime.now()
            cutoff_time = now - timedelta(minutes=self.window_minutes)

            symbols_to_remove = []
            for symbol, data in self.trade_data.items():
                if data["last_update"] < cutoff_time:
                    symbols_to_remove.append(symbol)

            for symbol in symbols_to_remove:
                logger.info(f"Cleaning old trade data for {symbol}")
                del self.trade_data[symbol]

    async def reset_symbol(self, symbol: str):
        """
        Сбрасывает данные по символу
        """
        async with self._lock:
            if symbol in self.trade_data:
                self.trade_data[symbol] = {
                    "buy_volume": 0.0,
                    "sell_volume": 0.0,
                    "total_trades": 0,
                    "last_update": datetime.now()
                }
                logger.info(f"Reset trade data for {symbol}")
