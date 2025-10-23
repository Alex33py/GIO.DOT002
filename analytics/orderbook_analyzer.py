#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OrderbookAnalyzer — Анализ orderbook и CVD
"""

from datetime import datetime
from typing import Dict
from config.settings import logger


class OrderbookAnalyzer:
    """
    Анализирует orderbook и вычисляет CVD (Cumulative Volume Delta)
    """

    def __init__(self, bot=None):
        self.bot = bot
        self.cvd_cache = {}  # {symbol: {'cvd': 0, 'buy_volume': 0, 'sell_volume': 0, 'timestamp': ''}}
        self._trade_counter = {}
        logger.info("✅ OrderbookAnalyzer инициализирован")

    async def process_trade(self, symbol: str, trade_data: Dict):
        """
        Обработать сделку и обновить CVD

        Args:
            trade_data: {
                'side': 'BUY' | 'SELL',
                'volume': float,  # или 'qty', 'size', 'quantity'
                'price': float,
                'timestamp': int
            }
        """
        try:
            side = trade_data.get("side", "").upper()

            # ✅ Обработка разных форматов объёма (Binance, OKX, Bybit, Coinbase)
            volume = (
                float(trade_data.get("volume", 0)) or
                float(trade_data.get("qty", 0)) or
                float(trade_data.get("size", 0)) or
                float(trade_data.get("quantity", 0))
            )

            if volume == 0:
                return  # Убираем warning, т.к. это спамит логи

            # Инициализируем кэш для символа
            if symbol not in self.cvd_cache:
                self.cvd_cache[symbol] = {
                    "cvd": 0,
                    "buy_volume": 0,
                    "sell_volume": 0,
                    "timestamp": datetime.now().isoformat(),
                }
                logger.info(f"[CVD] 🎯 Инициализирован кэш для {symbol}")

            # Обновляем объемы
            if side == "BUY":
                self.cvd_cache[symbol]["buy_volume"] += volume
                self.cvd_cache[symbol]["cvd"] += volume
            elif side == "SELL":
                self.cvd_cache[symbol]["sell_volume"] += volume
                self.cvd_cache[symbol]["cvd"] -= volume
            else:
                # Тихо пропускаем неизвестные стороны
                return

            self.cvd_cache[symbol]["timestamp"] = datetime.now().isoformat()

            # Логируем каждые 50 сделок
            if symbol not in self._trade_counter:
                self._trade_counter[symbol] = 0

            self._trade_counter[symbol] += 1

            if self._trade_counter[symbol] % 500 == 0:
                cvd_value = self.cvd_cache[symbol]["cvd"]
                buy_vol = self.cvd_cache[symbol]["buy_volume"]
                sell_vol = self.cvd_cache[symbol]["sell_volume"]
                total_vol = buy_vol + sell_vol

                cvd_pct = (
                    ((buy_vol - sell_vol) / total_vol) * 100 if total_vol > 0 else 0
                )

                logger.info(
                    f"📊 [CVD] {symbol}: {cvd_pct:+.2f}% | "
                    f"Buy: ${buy_vol:,.0f} | Sell: ${sell_vol:,.0f} | "
                    f"Trades: {self._trade_counter[symbol]}"
                )

        except Exception as e:
            logger.error(f"[CVD ERROR] process_trade для {symbol}: {e}", exc_info=True)

    async def get_cvd(self, symbol: str) -> Dict:
        """
        Получить CVD данные для символа

        Returns:
            Dict: {
                'cvd': float,
                'cvd_pct': float,
                'buy_volume': float,
                'sell_volume': float,
                'timestamp': str
            }
        """
        try:
            if symbol not in self.cvd_cache:
                logger.debug(f"[CVD] ⚠️ Данные для {symbol} отсутствуют в кэше")
                return {
                    "cvd": 0,
                    "cvd_pct": 0.0,
                    "buy_volume": 0,
                    "sell_volume": 0,
                    "timestamp": datetime.now().isoformat(),
                }

            data = self.cvd_cache[symbol]

            cvd_absolute = data.get("cvd", 0)
            buy_vol = data.get("buy_volume", 0)
            sell_vol = data.get("sell_volume", 0)
            total_vol = buy_vol + sell_vol

            # Рассчитываем CVD в процентах
            if total_vol > 0:
                cvd_pct = ((buy_vol - sell_vol) / total_vol) * 100
            else:
                cvd_pct = 0.0

            result = {
                "cvd": cvd_absolute,
                "cvd_pct": round(cvd_pct, 2),
                "buy_volume": buy_vol,
                "sell_volume": sell_vol,
                "timestamp": data.get("timestamp", datetime.now().isoformat()),
            }

            logger.debug(
                f"[CVD] ✅ get_cvd({symbol}): {cvd_pct:.2f}% (Buy: {buy_vol:.0f}, Sell: {sell_vol:.0f})"
            )

            return result

        except Exception as e:
            logger.error(f"[CVD ERROR] get_cvd для {symbol}: {e}", exc_info=True)
            return {
                "cvd": 0,
                "cvd_pct": 0.0,
                "buy_volume": 0,
                "sell_volume": 0,
                "timestamp": datetime.now().isoformat(),
            }
    async def get_cvd_summary(self, symbol: str, minutes: int = 15) -> Dict:
        """Алиас для get_cvd() — для совместимости"""
        return await self.get_cvd(symbol)
