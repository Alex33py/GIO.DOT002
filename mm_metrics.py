#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MM Metrics Provider
Получает реальные метрики: CVD, Funding Rate, L/S Ratio
"""

import aiohttp
import asyncio
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)


class MMMetricsProvider:
    """Провайдер MM-метрик из реальных источников"""

    def __init__(self):
        self.binance_futures_url = "https://fapi.binance.com"
        self.coinglass_url = "https://open-api.coinglass.com/public/v2"
        self.session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Получить или создать HTTP-сессию"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Закрыть HTTP-сессию"""
        if self.session and not self.session.closed:
            await self.session.close()

    # ==================== FUNDING RATE ====================
    async def get_funding_rate(self, symbol: str = "BTCUSDT") -> Optional[float]:
        """
        Получить Funding Rate из Binance Futures

        Args:
            symbol: Торговая пара (например, BTCUSDT)

        Returns:
            Funding rate в процентах или None
        """
        try:
            session = await self._get_session()
            url = f"{self.binance_futures_url}/fapi/v1/premiumIndex"
            params = {"symbol": symbol}

            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    funding_rate = float(data.get("lastFundingRate", 0)) * 100
                    logger.info(f"✅ Funding Rate ({symbol}): {funding_rate:.4f}%")
                    return round(funding_rate, 4)
                else:
                    logger.error(f"❌ Binance Futures API error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"❌ Error fetching Funding Rate: {e}")
            return None

    # ==================== L/S RATIO ====================
    async def get_ls_ratio(self, symbol: str = "BTC") -> Optional[float]:
        """
        Получить Long/Short Ratio из Coinglass API

        Args:
            symbol: Символ криптовалюты (например, BTC)

        Returns:
            L/S Ratio или None
        """
        try:
            session = await self._get_session()
            url = f"{self.coinglass_url}/indicator/long_short_accounts_ratio"
            params = {"symbol": symbol, "interval": "0"}  # 0 = latest

            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("success") and data.get("data"):
                        # Получаем последнее значение
                        latest = data["data"][0] if data["data"] else None
                        if latest:
                            ls_ratio = float(latest.get("longShortRatio", 1.0))
                            logger.info(f"✅ L/S Ratio ({symbol}): {ls_ratio:.2f}")
                            return round(ls_ratio, 2)
                    return None
                else:
                    logger.warning(f"⚠️ Coinglass API error: {response.status}")
                    return None
        except Exception as e:
            logger.warning(f"⚠️ Error fetching L/S Ratio: {e}")
            return None

    # ==================== CVD (Cumulative Volume Delta) ====================
    async def calculate_cvd(
        self, symbol: str = "BTCUSDT", limit: int = 500
    ) -> Optional[float]:
        """
        Рассчитать CVD на основе недавних сделок
        CVD = Сумма (Buy Volume - Sell Volume) / Total Volume * 100

        Args:
            symbol: Торговая пара
            limit: Количество недавних сделок для анализа

        Returns:
            CVD в процентах или None
        """
        try:
            session = await self._get_session()
            url = f"{self.binance_futures_url}/fapi/v1/aggTrades"
            params = {"symbol": symbol, "limit": limit}

            async with session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    trades = await response.json()

                    buy_volume = 0
                    sell_volume = 0

                    for trade in trades:
                        qty = float(trade["q"])
                        if trade["m"]:  # m = True означает Market Sell
                            sell_volume += qty
                        else:  # Market Buy
                            buy_volume += qty

                    total_volume = buy_volume + sell_volume
                    if total_volume > 0:
                        cvd = ((buy_volume - sell_volume) / total_volume) * 100
                        logger.info(f"✅ CVD ({symbol}): {cvd:.2f}%")
                        return round(cvd, 2)
                    return 0.0
                else:
                    logger.error(f"❌ Binance Futures API error: {response.status}")
                    return None
        except Exception as e:
            logger.error(f"❌ Error calculating CVD: {e}")
            return None

    # ==================== GET ALL METRICS ====================
    async def get_all_metrics(
        self, symbol: str = "BTCUSDT"
    ) -> Dict[str, Optional[float]]:
        """
        Получить все MM-метрики одновременно

        Args:
            symbol: Торговая пара

        Returns:
            Словарь с метриками: {"cvd": float, "funding": float, "ls_ratio": float}
        """
        tasks = [
            self.calculate_cvd(symbol),
            self.get_funding_rate(symbol),
            self.get_ls_ratio(symbol.replace("USDT", "")),
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            "cvd": results[0] if not isinstance(results[0], Exception) else None,
            "funding": results[1] if not isinstance(results[1], Exception) else None,
            "ls_ratio": results[2] if not isinstance(results[2], Exception) else None,
        }


# ==================== ПРИМЕР ИСПОЛЬЗОВАНИЯ ====================
async def main():
    """Пример использования MMMetricsProvider"""
    provider = MMMetricsProvider()

    try:
        print("🔄 Получаем MM-метрики...")
        metrics = await provider.get_all_metrics("BTCUSDT")

        print(f"\n📊 Результаты:")
        print(f"CVD: {metrics['cvd']}%")
        print(f"Funding Rate: {metrics['funding']}%")
        print(f"L/S Ratio: {metrics['ls_ratio']}")
    finally:
        await provider.close()


if __name__ == "__main__":
    asyncio.run(main())
