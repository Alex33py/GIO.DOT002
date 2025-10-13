# -*- coding: utf-8 -*-
"""
Кросс-биржевой анализатор
Сравнение данных между Binance и Bybit для улучшения точности сигналов
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from config.settings import logger

class CrossExchangeAnalyzer:
    """Анализатор данных между биржами для повышения точности"""

    def __init__(self, binance_connector, bybit_connector):
        self.binance = binance_connector
        self.bybit = bybit_connector

        # Кэш для сравнения
        self.price_diff_history = []
        self.volume_correlation = []

        logger.info("✅ CrossExchangeAnalyzer инициализирован (Binance + Bybit)")

    async def get_cross_exchange_price(self, symbol: str) -> Dict:
        """
        Получить цены с обеих бирж и рассчитать среднюю/спред

        Args:
            symbol: Торговая пара (BTCUSDT)

        Returns:
            Словарь с ценами и статистикой
        """
        try:
            # Получаем цены одновременно
            binance_ticker, bybit_ticker = await asyncio.gather(
                self.binance.get_ticker_24h(symbol),  # ← ИСПРАВЛЕНО
                self.bybit.get_ticker(symbol),
                return_exceptions=True,
            )

            # Обработка ошибок
            binance_price = None
            bybit_price = None

            if not isinstance(binance_ticker, Exception) and binance_ticker:
                # Binance может вернуть lastPrice или last
                price_str = (
                    binance_ticker.get("price")
                    or binance_ticker.get("last")
                    or binance_ticker.get("price")
                )
                if price_str:
                    binance_price = float(price_str)
                    logger.debug(f"✅ Binance цена получена: {binance_price}")
                else:
                    logger.warning(
                        f"⚠️ Binance вернул dict, но без цены: {list(binance_ticker.keys())}"
                    )

            if not isinstance(bybit_ticker, Exception) and bybit_ticker:
                # Bybit возвращает last_price или lastPrice
                price_str = bybit_ticker.get("last_price") or bybit_ticker.get(
                    "lastPrice"
                )
                if price_str:
                    bybit_price = float(price_str)
                    logger.debug(f"✅ Bybit цена получена: {bybit_price}")
                else:
                    logger.warning(
                        f"⚠️ Bybit вернул dict, но без цены: {list(bybit_ticker.keys())}"
                    )

            # Если обе цены доступны
            if binance_price and bybit_price:
                avg_price = (binance_price + bybit_price) / 2
                price_diff = abs(binance_price - bybit_price)
                price_diff_pct = (price_diff / avg_price) * 100

                # Определяем какая биржа дороже
                premium_exchange = "Binance" if binance_price > bybit_price else "Bybit"

                result = {
                    "binance_price": binance_price,
                    "bybit_price": bybit_price,
                    "avg_price": avg_price,
                    "price_diff": price_diff,
                    "price_diff_pct": price_diff_pct,
                    "premium_exchange": premium_exchange,
                    "timestamp": datetime.now().timestamp(),
                    "data_quality": "both_sources",
                }

                # Сохраняем в историю
                self.price_diff_history.append(
                    {"timestamp": result["timestamp"], "diff_pct": price_diff_pct}
                )

                # Ограничиваем историю (последние 100 точек)
                if len(self.price_diff_history) > 100:
                    self.price_diff_history.pop(0)

                logger.debug(
                    f"💱 {symbol}: Binance=${binance_price:.2f}, Bybit=${bybit_price:.2f}, "
                    f"Diff={price_diff_pct:.3f}%, Premium={premium_exchange}"
                )

                return result

            # Если только одна биржа доступна
            elif binance_price:
                logger.warning(f"⚠️ {symbol}: Только Binance доступен")
                return {
                    "binance_price": binance_price,
                    "bybit_price": None,
                    "avg_price": binance_price,
                    "data_quality": "binance_only",
                }

            elif bybit_price:
                logger.warning(f"⚠️ {symbol}: Только Binance доступен")
                return {
                    "binance_price": None,
                    "bybit_price": bybit_price,
                    "avg_price": bybit_price,
                    "data_quality": "bybit_only",
                }

            else:
                logger.error(f"❌ {symbol}: Обе биржи недоступны")
                return {
                    "binance_price": None,
                    "bybit_price": None,
                    "avg_price": None,
                    "data_quality": "no_data",
                }

        except Exception as e:
            logger.error(f"❌ Ошибка кросс-биржевого анализа цен: {e}")
            return {"data_quality": "error"}

    async def detect_arbitrage_opportunity(
        self, symbol: str, threshold_pct: float = 0.5
    ) -> Optional[Dict]:
        """
        Обнаружение арбитражных возможностей

        Args:
            symbol: Торговая пара
            threshold_pct: Минимальная разница в % для сигнала (0.5% по умолчанию)

        Returns:
            Словарь с арбитражной возможностью или None
        """
        try:
            price_data = await self.get_cross_exchange_price(symbol)

            if price_data.get("data_quality") != "both_sources":
                return None

            diff_pct = price_data["price_diff_pct"]

            if diff_pct >= threshold_pct:
                # Арбитраж обнаружен!
                buy_exchange = (
                    "Bybit"
                    if price_data["premium_exchange"] == "Binance"
                    else "Binance"
                )
                sell_exchange = price_data["premium_exchange"]

                opportunity = {
                    "symbol": symbol,
                    "type": "arbitrage",
                    "buy_exchange": buy_exchange,
                    "sell_exchange": sell_exchange,
                    "buy_price": (
                        price_data["bybit_price"]
                        if buy_exchange == "Bybit"
                        else price_data["binance_price"]
                    ),
                    "sell_price": (
                        price_data["binance_price"]
                        if sell_exchange == "Binance"
                        else price_data["bybit_price"]
                    ),
                    "profit_pct": diff_pct,
                    "timestamp": price_data["timestamp"],
                }

                logger.warning(
                    f"🎯 АРБИТРАЖ {symbol}: Купить на {buy_exchange}, Продать на {sell_exchange}, "
                    f"Профит: {diff_pct:.3f}%"
                )

                return opportunity

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка обнаружения арбитража: {e}")
            return None

    async def get_cross_exchange_volume(self, symbol: str) -> Dict:
        """
        Получить объём торгов с обеих бирж

        Args:
            symbol: Торговая пара

        Returns:
            Словарь с объёмами
        """
        try:
            binance_ticker, bybit_ticker = await asyncio.gather(
                self.binance.get_ticker_24h(symbol),  # ← ИСПРАВЛЕНО
                self.bybit.get_ticker(symbol),
                return_exceptions=True,
            )

            binance_volume = 0
            bybit_volume = 0

            if not isinstance(binance_ticker, Exception) and binance_ticker:
                binance_volume = float(binance_ticker.get("volume", 0))

            if not isinstance(bybit_ticker, Exception) and bybit_ticker:
                bybit_volume = float(bybit_ticker.get("volume24h", 0))

            total_volume = binance_volume + bybit_volume

            result = {
                "binance_volume": binance_volume,
                "bybit_volume": bybit_volume,
                "total_volume": total_volume,
                "binance_share": (
                    (binance_volume / total_volume * 100) if total_volume > 0 else 0
                ),
                "bybit_share": (
                    (bybit_volume / total_volume * 100) if total_volume > 0 else 0
                ),
                "timestamp": datetime.now().timestamp(),
            }

            logger.debug(
                f"📊 {symbol} Volume: Total=${total_volume:,.0f}, "
                f"Binance={result['binance_share']:.1f}%, Bybit={result['bybit_share']:.1f}%"
            )

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка анализа объёма: {e}")
            return {}

    async def validate_signal_with_both_exchanges(
        self, symbol: str, signal_price: float, tolerance_pct: float = 0.3
    ) -> bool:
        """
        Валидация торгового сигнала по обеим биржам

        Args:
            symbol: Торговая пара
            signal_price: Цена сигнала
            tolerance_pct: Допустимое отклонение в %

        Returns:
            True если обе биржи подтверждают цену
        """
        try:
            price_data = await self.get_cross_exchange_price(symbol)

            if price_data.get("data_quality") != "both_sources":
                # Если только одна биржа - принимаем сигнал
                logger.warning(f"⚠️ {symbol}: Валидация по одной бирже")
                return True

            avg_price = price_data["avg_price"]
            price_diff = abs(signal_price - avg_price)
            price_diff_pct = (price_diff / avg_price) * 100

            is_valid = price_diff_pct <= tolerance_pct

            if is_valid:
                logger.info(
                    f"✅ {symbol}: Сигнал валиден (цена={signal_price:.2f}, "
                    f"avg={avg_price:.2f}, diff={price_diff_pct:.3f}%)"
                )
            else:
                logger.warning(
                    f"⚠️ {symbol}: Сигнал отклонён (цена={signal_price:.2f}, "
                    f"avg={avg_price:.2f}, diff={price_diff_pct:.3f}% > {tolerance_pct}%)"
                )

            return is_valid

        except Exception as e:
            logger.error(f"❌ Ошибка валидации сигнала: {e}")
            return True  # При ошибке принимаем сигнал

    def get_price_spread_stats(self) -> Dict:
        """
        Получить статистику спреда цен за период

        Returns:
            Словарь со статистикой
        """
        try:
            if not self.price_diff_history:
                return {
                    "avg_spread": 0.0,
                    "max_spread": 0.0,
                    "min_spread": 0.0,
                    "current_spread": 0.0,
                    "samples": 0,
                }

            spreads = [item["diff_pct"] for item in self.price_diff_history]

            stats = {
                "avg_spread": sum(spreads) / len(spreads),
                "max_spread": max(spreads),
                "min_spread": min(spreads),
                "current_spread": spreads[-1] if spreads else 0.0,
                "samples": len(spreads),
            }

            return stats

        except Exception as e:
            logger.error(f"❌ Ошибка статистики спреда: {e}")
            return {}

    async def get_best_execution_exchange(self, symbol: str, side: str) -> str:
        """
        Определить лучшую биржу для исполнения ордера

        Args:
            symbol: Торговая пара
            side: 'buy' или 'sell'

        Returns:
            Название биржи ('Binance' или 'Bybit')
        """
        try:
            price_data = await self.get_cross_exchange_price(symbol)

            if price_data.get("data_quality") != "both_sources":
                # Если только одна доступна - возвращаем её
                if price_data.get("binance_price"):
                    return "Binance"
                else:
                    return "Bybit"

            binance_price = price_data["binance_price"]
            bybit_price = price_data["bybit_price"]

            if side.lower() == "buy":
                # Для покупки выбираем биржу с меньшей ценой
                best_exchange = "Binance" if binance_price < bybit_price else "Bybit"
                saving = abs(binance_price - bybit_price)
            else:
                # Для продажи выбираем биржу с большей ценой
                best_exchange = "Binance" if binance_price > bybit_price else "Bybit"
                saving = abs(binance_price - bybit_price)

            logger.info(
                f"🎯 {symbol}: Лучшая биржа для {side.upper()} = {best_exchange} "
                f"(экономия: ${saving:.2f})"
            )

            return best_exchange

        except Exception as e:
            logger.error(f"❌ Ошибка выбора биржи: {e}")
            return "Bybit"  # Bybit по умолчанию (т.к. есть WebSocket)

# Экспорт
__all__ = ["CrossExchangeAnalyzer"]
