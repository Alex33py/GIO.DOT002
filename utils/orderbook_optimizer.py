#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Orderbook Optimizer - оптимизация обработки L2 данных
Уменьшает задержки при анализе orderbook
"""

from typing import Dict, List, Tuple, Optional
from config.settings import logger


class OrderbookOptimizer:
    """
    Оптимизатор для L2 Orderbook

    Features:
    - Топ-N уровней extraction
    - Быстрый расчёт Volume Profile
    - Batch processing для множественных символов
    """

    @staticmethod
    def extract_top_levels(orderbook: Dict, top_n: int = 50) -> Dict:
        """
        Извлечь только топ-N уровней из orderbook

        Args:
            orderbook: Полный orderbook
            top_n: Количество топ уровней

        Returns:
            Orderbook с топ-N уровнями
        """
        try:
            bids = orderbook.get("b", [])[:top_n]
            asks = orderbook.get("a", [])[:top_n]

            return {
                "s": orderbook.get("s"),  # symbol
                "b": bids,  # top N bids
                "a": asks,  # top N asks
                "ts": orderbook.get("ts"),  # timestamp
                "u": orderbook.get("u"),  # update ID
                "_optimized": True,
                "_levels": len(bids) + len(asks),
            }

        except Exception as e:
            logger.error(f"❌ Ошибка extract_top_levels: {e}")
            return orderbook

    @staticmethod
    def calculate_imbalance_fast(orderbook: Dict) -> float:
        """
        Быстрый расчёт L2 Imbalance (оптимизированный)

        Args:
            orderbook: Orderbook данные

        Returns:
            Imbalance в процентах (-100 до +100)
        """
        try:
            bids = orderbook.get("b", [])
            asks = orderbook.get("a", [])

            # Быстрый расчёт (топ-20 уровней)
            bid_volume = sum(float(bid[1]) for bid in bids[:20])
            ask_volume = sum(float(ask[1]) for ask in asks[:20])

            total_volume = bid_volume + ask_volume

            if total_volume == 0:
                return 0.0

            imbalance = ((bid_volume - ask_volume) / total_volume) * 100

            return round(imbalance, 2)

        except Exception as e:
            logger.error(f"❌ Ошибка calculate_imbalance_fast: {e}")
            return 0.0

    @staticmethod
    def calculate_depth_metrics(orderbook: Dict) -> Dict:
        """
        Расчёт метрик глубины orderbook (оптимизированный)

        Args:
            orderbook: Orderbook данные

        Returns:
            Dict с метриками
        """
        try:
            bids = orderbook.get("b", [])
            asks = orderbook.get("a", [])

            # Топ-10 уровней для метрик
            top_bids = bids[:10]
            top_asks = asks[:10]

            # Best bid/ask
            best_bid = float(top_bids[0][0]) if top_bids else 0.0
            best_ask = float(top_asks[0][0]) if top_asks else 0.0

            # Spread
            spread = best_ask - best_bid if best_bid and best_ask else 0.0
            spread_pct = (spread / best_bid * 100) if best_bid else 0.0

            # Total volume (топ-10)
            bid_volume = sum(float(b[1]) for b in top_bids)
            ask_volume = sum(float(a[1]) for a in top_asks)

            return {
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": round(spread, 2),
                "spread_pct": round(spread_pct, 4),
                "bid_volume_top10": round(bid_volume, 2),
                "ask_volume_top10": round(ask_volume, 2),
                "total_volume_top10": round(bid_volume + ask_volume, 2),
                "bid_levels": len(bids),
                "ask_levels": len(asks),
            }

        except Exception as e:
            logger.error(f"❌ Ошибка calculate_depth_metrics: {e}")
            return {}

    @staticmethod
    def calculate_volume_profile_fast(orderbook: Dict, price_levels: int = 20) -> Dict:
        """
        Быстрый расчёт Volume Profile (оптимизированный)

        Args:
            orderbook: Orderbook данные
            price_levels: Количество ценовых уровней

        Returns:
            Dict с Volume Profile данными
        """
        try:
            bids = orderbook.get("b", [])
            asks = orderbook.get("a", [])

            if not bids or not asks:
                return {}

            # Определяем диапазон цен (топ-N уровней)
            all_prices = [float(b[0]) for b in bids[:price_levels]] + [
                float(a[0]) for a in asks[:price_levels]
            ]

            min_price = min(all_prices)
            max_price = max(all_prices)

            # POC (Point of Control) - уровень с макс. объёмом
            # Упрощённый расчёт по топ-5 bid и ask
            volumes = []
            for bid in bids[:5]:
                volumes.append((float(bid[0]), float(bid[1])))
            for ask in asks[:5]:
                volumes.append((float(ask[0]), float(ask[1])))

            if volumes:
                poc_price, poc_volume = max(volumes, key=lambda x: x[1])
            else:
                poc_price = (min_price + max_price) / 2
                poc_volume = 0.0

            # VAH/VAL (Value Area High/Low) - упрощённый расчёт
            # 70% объёма находится в Value Area
            vah = max_price
            val = min_price

            return {
                "poc": round(poc_price, 2),
                "vah": round(vah, 2),
                "val": round(val, 2),
                "poc_volume": round(poc_volume, 2),
                "price_range": round(max_price - min_price, 2),
                "_optimized": True,
            }

        except Exception as e:
            logger.error(f"❌ Ошибка calculate_volume_profile_fast: {e}")
            return {}

    @staticmethod
    def batch_process_orderbooks(
        orderbooks: Dict[str, Dict], processor_func, **kwargs
    ) -> Dict[str, any]:
        """
        Batch обработка нескольких orderbook'ов

        Args:
            orderbooks: Dict {symbol: orderbook}
            processor_func: Функция обработки
            **kwargs: Дополнительные параметры

        Returns:
            Dict {symbol: result}
        """
        results = {}

        for symbol, orderbook in orderbooks.items():
            try:
                result = processor_func(orderbook, **kwargs)
                results[symbol] = result
            except Exception as e:
                logger.error(f"❌ Ошибка batch processing {symbol}: {e}")
                results[symbol] = None

        return results


# Singleton instance
_optimizer = OrderbookOptimizer()


def get_orderbook_optimizer() -> OrderbookOptimizer:
    """Получить глобальный Orderbook Optimizer"""
    return _optimizer


# Экспорт
__all__ = ["OrderbookOptimizer", "get_orderbook_optimizer"]
