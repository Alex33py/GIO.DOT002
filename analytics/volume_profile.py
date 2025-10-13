# -*- coding: utf-8 -*-
"""
Расширенный калькулятор Volume Profile для GIO Crypto Bot
Профессиональный анализ объёма с поддержкой институциональной активности
ИСПРАВЛЕННАЯ ВЕРСИЯ с улучшенной валидацией
"""

import numpy as np
from collections import defaultdict, deque
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
import time

from config.settings import (
    logger, VOLUME_PROFILE_LEVELS_COUNT, INSTITUTIONAL_VOLUME_THRESHOLD,
    ICEBERG_DETECTION_THRESHOLD
)
from config.constants import TrendDirectionEnum, VetoReasonEnum
from utils.helpers import current_epoch_ms, safe_float, safe_int
from utils.validators import validate_trade_data, validate_orderbook_data


@dataclass
class VolumeLevel:
    """Уровень объёма в Volume Profile"""
    price: float
    executed_volume: float = 0.0
    resting_liquidity: float = 0.0
    composite_volume: float = 0.0
    imbalance_score: float = 0.0
    institutional_flow: float = 0.0
    iceberg_detected: bool = False
    absorption_level: float = 0.0
    liquidity_events: deque = field(default_factory=lambda: deque(maxlen=100))  # ИСПРАВЛЕНО: ограничен размер
    bid_ask_ratio: float = 0.0
    order_count: int = 0


@dataclass
class EnhancedVolumeProfile:
    """Расширенный Volume Profile с институциональным анализом"""
    poc_price: float
    poc_volume: float
    poc_strength: float
    value_area_high: float
    value_area_low: float
    value_area_volume: float
    total_composite_volume: float
    enhanced_cvd: float
    volume_clusters: List[Dict]
    liquidity_zones: List[Dict]
    institutional_analysis: Dict[str, Any]
    hidden_volume_levels: Dict[float, float]
    iceberg_levels: List[Dict]
    exchange_contribution: Dict[str, Dict]
    analysis_timestamp: int
    data_quality_score: float
    exocharts_similarity: float
    processing_stats: Dict[str, int]


def _create_default_volume_level() -> VolumeLevel:
    """
    Фабричная функция для создания VolumeLevel по умолчанию
    ИСПРАВЛЕНО: Используется вместо lambda для совместимости с pickle
    """
    return VolumeLevel(
        price=0.0,
        executed_volume=0.0,
        resting_liquidity=0.0,
        composite_volume=0.0,
        imbalance_score=0.0,
        institutional_flow=0.0,
        iceberg_detected=False,
        absorption_level=0.0,
        liquidity_events=deque(maxlen=100),
        bid_ask_ratio=0.0,
        order_count=0
    )


class EnhancedVolumeProfileCalculator:
    """Расширенный калькулятор Volume Profile с профессиональными возможностями"""

    def __init__(self):
        """Инициализация калькулятора"""
        # Данные сделок и orderbook
        self.executed_trades = deque(maxlen=50000)
        self.orderbook_snapshots = deque(maxlen=5000)
        self.orderbook_changes = deque(maxlen=10000)

        # ИСПРАВЛЕНО: Используем обычную функцию вместо lambda
        self.price_levels: Dict[float, VolumeLevel] = defaultdict(_create_default_volume_level)

        # Веса бирж для агрегации данных
        self.exchange_weights = {
            "binance": 0.35,
            "bybit": 0.30,
            "okx": 0.20,
            "coinbase": 0.15,
        }

        # Специальные зоны и уровни
        self.liquidity_zones = []
        self.hidden_volume_levels = defaultdict(float)
        self.institutional_levels = []

        # Диапазон цен и статистика
        self.price_range = {"min": float('inf'), "max": float('-inf')}
        self.analysis_count = 0
        self.last_analysis_time = 0

        # Статистика обработки
        self.processing_stats = {
            "orderbook_updates": 0,
            "trade_updates": 0,
            "analysis_cycles": 0,
            "detection_accuracy": 0.0,
            "validation_errors": 0,  # Новая метрика
        }

        logger.info("✅ EnhancedVolumeProfileCalculator инициализирован")

    def add_trade_data(self, trade_data: Dict, exchange: str = "bybit"):
        """Добавление данных сделки с валидацией"""
        try:
            if not validate_trade_data(trade_data):
                self.processing_stats["validation_errors"] += 1
                return

            price = safe_float(trade_data.get("price", trade_data.get("p", 0)))
            quantity = safe_float(trade_data.get("quantity", trade_data.get("q", 0)))
            is_buyer_maker = trade_data.get("is_buyer_maker", trade_data.get("m", False))
            timestamp = safe_int(trade_data.get("timestamp", trade_data.get("T", current_epoch_ms())))

            # Вес биржи
            weight = self.exchange_weights.get(exchange, 0.1)
            weighted_quantity = quantity * weight

            # Расширенные данные сделки
            enhanced_trade = {
                "price": price,
                "quantity": quantity,
                "weighted_quantity": weighted_quantity,
                "is_buyer_maker": is_buyer_maker,
                "exchange": exchange,
                "timestamp": timestamp,
                "trade_size_category": self._categorize_trade_size(quantity),
                "market_impact": self._estimate_market_impact(price, quantity),
                "delta": weighted_quantity * (-1 if is_buyer_maker else 1),
            }

            self.executed_trades.append(enhanced_trade)
            self._update_price_levels_from_trades(enhanced_trade)
            self._detect_institutional_activity(enhanced_trade)

            self.processing_stats["trade_updates"] += 1

        except Exception as e:
            logger.error(f"❌ Ошибка обработки trade данных: {e}")
            self.processing_stats["validation_errors"] += 1

    def add_orderbook_snapshot(self, orderbook_data: Dict, exchange: str = "bybit"):
        """
        Обработка L2 orderbook снимков для анализа ликвидности
        ИСПРАВЛЕНО: Улучшенная валидация и обработка ошибок
        """
        try:
            if not validate_orderbook_data(orderbook_data):
                logger.debug("⚠️ Orderbook данные не прошли валидацию")
                self.processing_stats["validation_errors"] += 1
                return

            bids = orderbook_data.get("bids", orderbook_data.get("b", []))
            asks = orderbook_data.get("asks", orderbook_data.get("a", []))
            timestamp = safe_int(orderbook_data.get("timestamp", current_epoch_ms()))
            weight = self.exchange_weights.get(exchange, 0.1)

            # ИСПРАВЛЕНО: Проверяем что bids и asks не None
            if bids is None:
                logger.debug(f"⚠️ Orderbook bids = None для {exchange}")
                bids = []

            if asks is None:
                logger.debug(f"⚠️ Orderbook asks = None для {exchange}")
                asks = []

            # Проверяем что это списки
            if not isinstance(bids, (list, tuple)):
                logger.warning(f"⚠️ Orderbook bids должен быть списком, получен {type(bids)}")
                bids = []

            if not isinstance(asks, (list, tuple)):
                logger.warning(f"⚠️ Orderbook asks должен быть списком, получен {type(asks)}")
                asks = []

            processed_snapshot = {
                "bids": self._process_orderbook_side(bids, weight, "bids", exchange),
                "asks": self._process_orderbook_side(asks, weight, "asks", exchange),
                "exchange": exchange,
                "timestamp": timestamp,
                "weight": weight,
            }

            # Анализируем изменения если есть предыдущий снимок
            if len(self.orderbook_snapshots) > 0:
                self._analyze_orderbook_changes(self.orderbook_snapshots[-1], processed_snapshot)

            self.orderbook_snapshots.append(processed_snapshot)
            self._update_price_levels_from_orderbook(processed_snapshot)
            self._detect_liquidity_events(processed_snapshot)

            self.processing_stats["orderbook_updates"] += 1

        except Exception as e:
            logger.error(f"❌ Ошибка обработки orderbook данных: {e}")
            self.processing_stats["validation_errors"] += 1

    def _process_orderbook_side(
        self,
        levels: List,
        weight: float,
        side_name: str = "unknown",
        exchange: str = "unknown"
    ) -> List[Dict]:
        """
        Обработка одной стороны orderbook (bids или asks)
        ИСПРАВЛЕНО: Полная валидация с детальным логированием
        """
        processed_levels = []

        # ИСПРАВЛЕНО: Проверяем что levels не None и является списком
        if levels is None:
            logger.debug(f"⚠️ {side_name} для {exchange} = None")
            return processed_levels

        if not isinstance(levels, (list, tuple)):
            logger.warning(f"⚠️ {side_name} для {exchange} должен быть списком, получен {type(levels)}")
            return processed_levels

        try:
            for idx, level in enumerate(levels):
                try:
                    # ИСПРАВЛЕНО: Полная валидация level перед доступом к индексам
                    if level is None:
                        logger.debug(f"⚠️ {side_name}[{idx}] для {exchange} = None, пропускаем")
                        continue

                    # Проверяем что level это список или кортеж
                    if not isinstance(level, (list, tuple)):
                        logger.debug(
                            f"⚠️ {side_name}[{idx}] для {exchange} должен быть списком/кортежем, "
                            f"получен {type(level)}: {level}, пропускаем"
                        )
                        continue

                    # КРИТИЧНО: Проверяем длину перед доступом к индексам
                    if len(level) < 2:
                        logger.debug(
                            f"⚠️ {side_name}[{idx}] для {exchange} имеет недостаточную длину: "
                            f"{len(level)} (нужно минимум 2), данные: {level}, пропускаем"
                        )
                        continue

                    # Безопасное извлечение price и volume
                    price = safe_float(level[0])
                    volume = safe_float(level[1])

                    # ИСПРАВЛЕНО: Проверяем валидность значений
                    if price <= 0:
                        logger.debug(
                            f"⚠️ {side_name}[{idx}] для {exchange}: "
                            f"недопустимая цена {price}, пропускаем"
                        )
                        continue

                    if volume <= 0:
                        logger.debug(
                            f"⚠️ {side_name}[{idx}] для {exchange}: "
                            f"недопустимый объём {volume} при цене {price}, пропускаем"
                        )
                        continue

                    # Валидные данные - обрабатываем
                    weighted_volume = volume * weight

                    level_data = {
                        "price": price,
                        "volume": volume,
                        "weighted_volume": weighted_volume,
                        "size_category": self._categorize_order_size(volume),
                        "liquidity_strength": self._calculate_liquidity_strength(price, volume),
                        "potential_iceberg": volume > self._get_iceberg_threshold(price),
                    }

                    processed_levels.append(level_data)

                except (ValueError, TypeError, IndexError) as e:
                    # ИСПРАВЛЕНО: Детальное логирование с контекстом
                    logger.debug(
                        f"⚠️ Ошибка обработки {side_name}[{idx}] для {exchange}: "
                        f"{type(e).__name__}: {e}, данные: {level}, пропускаем"
                    )
                    self.processing_stats["validation_errors"] += 1
                    continue

            logger.debug(
                f"✅ Обработано {len(processed_levels)}/{len(levels)} уровней "
                f"{side_name} для {exchange}"
            )
            return processed_levels

        except Exception as e:
            logger.error(
                f"❌ Критическая ошибка обработки {side_name} для {exchange}: "
                f"{type(e).__name__}: {e}"
            )
            return []

    def _categorize_trade_size(self, quantity: float) -> str:
        """Категоризация размера сделки"""
        try:
            if quantity >= INSTITUTIONAL_VOLUME_THRESHOLD * 10:
                return "whale"
            elif quantity >= INSTITUTIONAL_VOLUME_THRESHOLD:
                return "institutional"
            elif quantity >= 1.0:
                return "retail_large"
            else:
                return "retail_small"
        except Exception:
            return "unknown"

    def _categorize_order_size(self, volume: float) -> str:
        """Категоризация размера ордера"""
        try:
            if volume >= ICEBERG_DETECTION_THRESHOLD * 5:
                return "massive"
            elif volume >= ICEBERG_DETECTION_THRESHOLD:
                return "large"
            elif volume >= 1.0:
                return "medium"
            else:
                return "small"
        except Exception:
            return "unknown"

    def _estimate_market_impact(self, price: float, quantity: float) -> float:
        """Оценка влияния сделки на рынок"""
        try:
            base_impact = quantity / 100
            price_factor = price / 50000
            return base_impact * price_factor
        except Exception:
            return 0.0

    def _get_iceberg_threshold(self, price: float) -> float:
        """Динамический порог для обнаружения iceberg ордеров"""
        try:
            base_threshold = ICEBERG_DETECTION_THRESHOLD
            price_factor = max(0.5, min(2.0, price / 50000))
            return base_threshold * price_factor
        except Exception:
            return ICEBERG_DETECTION_THRESHOLD

    def _calculate_liquidity_strength(self, price: float, volume: float) -> float:
        """Расчёт силы ликвидности"""
        try:
            volume_factor = min(1.0, volume / 10.0)
            price_significance = self._get_price_significance(price)
            return volume_factor * price_significance
        except Exception:
            return 0.0

    def _get_price_significance(self, price: float) -> float:
        """Получение важности уровня цены"""
        try:
            round_levels = [100, 500, 1000, 5000, 10000, 50000, 100000]
            min_distance = min(abs(price - level) / level for level in round_levels if level > 0)
            significance = 1.0 - min(min_distance, 1.0)
            return max(0.1, significance)
        except Exception:
            return 0.5

    def _update_price_levels_from_trades(self, trade: Dict):
        """Обновление уровней цен данными сделок"""
        try:
            price = trade["price"]
            quantity = trade["weighted_quantity"]

            level = self.price_levels[price]
            level.price = price
            level.executed_volume += quantity
            level.composite_volume = level.executed_volume + level.resting_liquidity
            level.order_count += 1

            if not trade["is_buyer_maker"]:
                level.institutional_flow += quantity
            else:
                level.institutional_flow -= quantity

            self.price_range["min"] = min(self.price_range["min"], price)
            self.price_range["max"] = max(self.price_range["max"], price)

        except Exception as e:
            logger.error(f"❌ Ошибка обновления уровней цен из сделок: {e}")

    def _update_price_levels_from_orderbook(self, snapshot: Dict):
        """
        Обновление уровней цен данными orderbook
        ИСПРАВЛЕНО: Безопасная обработка с проверкой на пустые списки
        """
        try:
            # ИСПРАВЛЕНО: Проверяем что bids и asks существуют и не пусты
            bids = snapshot.get("bids", [])
            asks = snapshot.get("asks", [])

            if not isinstance(bids, list):
                bids = []
            if not isinstance(asks, list):
                asks = []

            # Обрабатываем биды
            for bid in bids:
                if not isinstance(bid, dict):
                    continue

                price = bid.get("price")
                volume = bid.get("weighted_volume")

                if price is None or volume is None or price <= 0 or volume <= 0:
                    continue

                level = self.price_levels[price]
                level.price = price
                level.resting_liquidity = volume
                level.composite_volume = level.executed_volume + level.resting_liquidity
                level.bid_ask_ratio = min(2.0, level.bid_ask_ratio + 0.1)

            # Обрабатываем аски
            for ask in asks:
                if not isinstance(ask, dict):
                    continue

                price = ask.get("price")
                volume = ask.get("weighted_volume")

                if price is None or volume is None or price <= 0 or volume <= 0:
                    continue

                level = self.price_levels[price]
                level.price = price
                level.resting_liquidity = volume
                level.composite_volume = level.executed_volume + level.resting_liquidity
                level.bid_ask_ratio = max(0.0, level.bid_ask_ratio - 0.1)

        except Exception as e:
            logger.error(f"❌ Ошибка обновления уровней цен из orderbook: {e}")

    def _detect_institutional_activity(self, trade: Dict):
        """Обнаружение институциональной активности"""
        try:
            quantity = trade["quantity"]
            price = trade["price"]
            timestamp = trade["timestamp"]

            if trade["trade_size_category"] in ["institutional", "whale"]:
                institutional_level = {
                    "price": price,
                    "volume": quantity,
                    "timestamp": timestamp,
                    "exchange": trade["exchange"],
                    "direction": "buy" if not trade["is_buyer_maker"] else "sell",
                    "market_impact": trade["market_impact"],
                    "confidence": 0.8 if quantity >= INSTITUTIONAL_VOLUME_THRESHOLD * 5 else 0.6,
                }

                self.institutional_levels.append(institutional_level)

                if len(self.institutional_levels) > 1000:
                    self.institutional_levels = self.institutional_levels[-500:]

                logger.debug(f"🏛️ Институциональная активность: {quantity:.2f} @ ${price:.2f}")

        except Exception as e:
            logger.error(f"❌ Ошибка обнаружения институциональной активности: {e}")

    def _analyze_orderbook_changes(self, prev_snapshot: Dict, current_snapshot: Dict):
        """Анализ изменений в orderbook"""
        try:
            changes = {
                "timestamp": current_snapshot["timestamp"],
                "bid_changes": self._compare_orderbook_side(
                    prev_snapshot["bids"], current_snapshot["bids"]
                ),
                "ask_changes": self._compare_orderbook_side(
                    prev_snapshot["asks"], current_snapshot["asks"]
                ),
                "exchange": current_snapshot["exchange"],
            }

            significant_changes = self._detect_significant_changes(changes)
            if significant_changes:
                self.orderbook_changes.append(significant_changes)

        except Exception as e:
            logger.error(f"❌ Ошибка анализа изменений orderbook: {e}")

    def _compare_orderbook_side(self, prev_side: List, current_side: List) -> Dict:
        """Сравнение изменений в одной стороне orderbook"""
        try:
            prev_dict = {level["price"]: level["weighted_volume"] for level in prev_side}
            current_dict = {level["price"]: level["weighted_volume"] for level in current_side}

            changes = {
                "added": [],
                "removed": [],
                "changed": [],
                "total_volume_change": 0.0,
            }

            for price, volume in current_dict.items():
                if price not in prev_dict:
                    changes["added"].append({"price": price, "volume": volume})
                    changes["total_volume_change"] += volume

            for price, volume in prev_dict.items():
                if price not in current_dict:
                    changes["removed"].append({"price": price, "volume": volume})
                    changes["total_volume_change"] -= volume

            for price in set(prev_dict.keys()) & set(current_dict.keys()):
                volume_change = current_dict[price] - prev_dict[price]
                if abs(volume_change) > 0.01:
                    changes["changed"].append({
                        "price": price,
                        "volume_change": volume_change,
                        "prev_volume": prev_dict[price],
                        "current_volume": current_dict[price]
                    })
                    changes["total_volume_change"] += volume_change

            return changes

        except Exception as e:
            logger.error(f"❌ Ошибка сравнения стороны orderbook: {e}")
            return {"added": [], "removed": [], "changed": [], "total_volume_change": 0.0}

    def _detect_significant_changes(self, changes: Dict) -> Optional[Dict]:
        """Обнаружение значительных изменений в orderbook"""
        try:
            bid_volume_change = abs(changes["bid_changes"]["total_volume_change"])
            ask_volume_change = abs(changes["ask_changes"]["total_volume_change"])

            significant_threshold = 5.0

            if bid_volume_change > significant_threshold or ask_volume_change > significant_threshold:
                return {
                    "timestamp": changes["timestamp"],
                    "type": "significant_liquidity_change",
                    "bid_volume_change": changes["bid_changes"]["total_volume_change"],
                    "ask_volume_change": changes["ask_changes"]["total_volume_change"],
                    "exchange": changes["exchange"],
                    "severity": "high" if max(bid_volume_change, ask_volume_change) > 20.0 else "medium"
                }

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка обнаружения значительных изменений: {e}")
            return None

    def _detect_liquidity_events(self, snapshot: Dict):
        """
        Обнаружение событий ликвидности
        ИСПРАВЛЕНО: liquidity_events теперь ограничен через deque
        """
        try:
            current_time = current_epoch_ms()

            for bid in snapshot["bids"]:
                if bid["size_category"] in ["large", "massive"]:
                    event = {
                        "type": "large_bid_placed",
                        "price": bid["price"],
                        "volume": bid["volume"],
                        "timestamp": current_time,
                        "exchange": snapshot["exchange"],
                        "potential_iceberg": bid["potential_iceberg"],
                        "strength": bid["liquidity_strength"],
                    }

                    level = self.price_levels[bid["price"]]
                    # liquidity_events теперь deque с maxlen=100, автоматически ограничен
                    level.liquidity_events.append(event)

            for ask in snapshot["asks"]:
                if ask["size_category"] in ["large", "massive"]:
                    event = {
                        "type": "large_ask_placed",
                        "price": ask["price"],
                        "volume": ask["volume"],
                        "timestamp": current_time,
                        "exchange": snapshot["exchange"],
                        "potential_iceberg": ask["potential_iceberg"],
                        "strength": ask["liquidity_strength"],
                    }

                    level = self.price_levels[ask["price"]]
                    level.liquidity_events.append(event)

        except Exception as e:
            logger.error(f"❌ Ошибка обнаружения событий ликвидности: {e}")

    async def calculate_from_orderbook(
        self,
        orderbook_data: Dict,
        price_levels: int = 50
    ) -> Optional[Dict]:
        """
        Рассчитать Volume Profile из РЕАЛЬНОГО L2 orderbook (bid/ask)
        Это метод для ЭКСПОРТА данных (не внутренний метод класса)

        Args:
            orderbook_data: Данные из BybitOrderbookWebSocket
                {
                    'bids': [[price, size], ...],
                    'asks': [[price, size], ...],
                    'timestamp': 123456789
                }
            price_levels: Количество ценовых уровней для анализа

        Returns:
            Volume Profile с POC, VAH, VAL, bid/ask дисбалансом
        """
        try:
            if not orderbook_data or 'bids' not in orderbook_data or 'asks' not in orderbook_data:
                logger.warning("⚠️ Нет данных orderbook для Volume Profile")
                return None

            bids = orderbook_data['bids']  # [[price, size], ...]
            asks = orderbook_data['asks']

            if not bids or not asks:
                logger.warning("⚠️ Пустой orderbook")
                return None

            # Объединяем bid и ask в единый профиль
            volume_by_price = {}

            # Обработка bids (спрос) - первые N уровней
            total_bid_volume = 0
            for price, size in bids[:price_levels]:
                price_float = float(price)
                size_float = float(size)

                # Округляем цену до ближайшего уровня (0.1 для BTC)
                rounded_price = round(price_float, 1)

                if rounded_price not in volume_by_price:
                    volume_by_price[rounded_price] = 0

                volume_by_price[rounded_price] += size_float
                total_bid_volume += size_float

            # Обработка asks (предложение) - первые N уровней
            total_ask_volume = 0
            for price, size in asks[:price_levels]:
                price_float = float(price)
                size_float = float(size)

                rounded_price = round(price_float, 1)

                if rounded_price not in volume_by_price:
                    volume_by_price[rounded_price] = 0

                volume_by_price[rounded_price] += size_float
                total_ask_volume += size_float

            if not volume_by_price:
                logger.warning("⚠️ Пустой volume_by_price")
                return None

            # Сортировка по ценам
            sorted_prices = sorted(volume_by_price.items(), key=lambda x: x[0])

            # Рассчитываем общий объём
            total_volume = sum(vol for _, vol in sorted_prices)

            # Находим POC (Point of Control) - уровень с максимальным объёмом
            poc_price = max(sorted_prices, key=lambda x: x[1])[0]
            poc_volume = volume_by_price[poc_price]

            # Рассчитываем Value Area (70% объёма вокруг POC)
            target_volume = total_volume * 0.70

            # Находим VAH и VAL
            accumulated_volume = poc_volume
            vah = poc_price
            val = poc_price

            # Находим индекс POC
            poc_index = next(i for i, (p, _) in enumerate(sorted_prices) if p == poc_price)

            upper_idx = poc_index
            lower_idx = poc_index

            # Расширяем Value Area от POC
            while accumulated_volume < target_volume:
                # Проверяем верхнюю границу
                if upper_idx + 1 < len(sorted_prices):
                    upper_vol = sorted_prices[upper_idx + 1][1]
                else:
                    upper_vol = 0

                # Проверяем нижнюю границу
                if lower_idx - 1 >= 0:
                    lower_vol = sorted_prices[lower_idx - 1][1]
                else:
                    lower_vol = 0

                # Расширяем в сторону большего объёма
                if upper_vol > lower_vol and upper_idx + 1 < len(sorted_prices):
                    upper_idx += 1
                    accumulated_volume += upper_vol
                    vah = sorted_prices[upper_idx][0]
                elif lower_idx - 1 >= 0:
                    lower_idx -= 1
                    accumulated_volume += lower_vol
                    val = sorted_prices[lower_idx][0]
                else:
                    break

            # Рассчитываем дисбаланс bid/ask (КРИТИЧНЫЙ ПОКАЗАТЕЛЬ!)
            if total_bid_volume + total_ask_volume > 0:
                bid_ask_ratio = total_bid_volume / (total_bid_volume + total_ask_volume)
            else:
                bid_ask_ratio = 0.5

            # Дисбаланс от 0 до 1 (0.5 = баланс)
            imbalance = abs(bid_ask_ratio - 0.5) * 2

            # Определяем давление
            if bid_ask_ratio > 0.6:
                pressure = "🟢 BUYING (покупатели сильнее)"
            elif bid_ask_ratio < 0.4:
                pressure = "🔴 SELLING (продавцы сильнее)"
            else:
                pressure = "⚪ NEUTRAL (баланс)"

            result = {
                'poc': poc_price,
                'vah': vah,
                'val': val,
                'total_volume': total_volume,
                'poc_volume': poc_volume,
                'value_area_volume': accumulated_volume,
                'bid_volume': total_bid_volume,
                'ask_volume': total_ask_volume,
                'bid_ask_ratio': bid_ask_ratio,
                'imbalance': imbalance,
                'pressure': pressure,
                'levels': len(volume_by_price),
                'data_source': 'L2_orderbook',  # ВАЖНО!
                'timestamp': orderbook_data.get('timestamp', 0)
            }

            logger.info(f"✅ Volume Profile (L2 ORDERBOOK): POC=${poc_price:,.2f}, VAH=${vah:,.2f}, VAL=${val:,.2f}")
            logger.info(f"   📊 Bid: {total_bid_volume:.2f} / Ask: {total_ask_volume:.2f} ({bid_ask_ratio:.1%} / {1-bid_ask_ratio:.1%})")
            logger.info(f"   📊 Дисбаланс: {imbalance:.1%} | {pressure}")

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка calculate_from_orderbook: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return None

    # ... (остальные методы остаются без изменений, они корректны)
    # build_enhanced_volume_profile и все вспомогательные методы работают правильно

    def build_enhanced_volume_profile(self) -> EnhancedVolumeProfile:
        """Построение расширенного Volume Profile"""
        try:
            if not self.price_levels:
                return self._create_empty_profile()

            active_levels = [
                level for level in self.price_levels.values()
                if level.composite_volume > 0
            ]

            if not active_levels:
                return self._create_empty_profile()

            sorted_levels = sorted(active_levels, key=lambda x: x.composite_volume, reverse=True)

            poc_level = sorted_levels[0]
            poc_price = poc_level.price
            poc_volume = poc_level.composite_volume
            poc_strength = self._calculate_poc_strength(poc_level, sorted_levels)

            total_volume = sum(level.composite_volume for level in active_levels)
            value_area_levels = self._calculate_value_area(sorted_levels, total_volume)

            enhanced_cvd = self._calculate_enhanced_cvd()
            volume_clusters = self._identify_volume_clusters(sorted_levels)
            liquidity_zones = self._identify_liquidity_zones()
            institutional_analysis = self._perform_institutional_analysis()
            hidden_volumes = dict(self.hidden_volume_levels)
            iceberg_levels = self._detect_iceberg_levels()
            exchange_contribution = self._calculate_exchange_contribution()
            data_quality_score = self._calculate_data_quality_score()
            exocharts_similarity = self._estimate_exocharts_similarity()

            profile = EnhancedVolumeProfile(
                poc_price=poc_price,
                poc_volume=poc_volume,
                poc_strength=poc_strength,
                value_area_high=value_area_levels["high"],
                value_area_low=value_area_levels["low"],
                value_area_volume=value_area_levels["volume"],
                total_composite_volume=total_volume,
                enhanced_cvd=enhanced_cvd,
                volume_clusters=volume_clusters,
                liquidity_zones=liquidity_zones,
                institutional_analysis=institutional_analysis,
                hidden_volume_levels=hidden_volumes,
                iceberg_levels=iceberg_levels,
                exchange_contribution=exchange_contribution,
                analysis_timestamp=current_epoch_ms(),
                data_quality_score=data_quality_score,
                exocharts_similarity=exocharts_similarity,
                processing_stats=self.processing_stats.copy()
            )

            self.analysis_count += 1
            self.last_analysis_time = current_epoch_ms()
            self.processing_stats["analysis_cycles"] += 1

            return profile

        except Exception as e:
            logger.error(f"❌ Ошибка построения volume profile: {e}")
            return self._create_empty_profile()

    def _create_empty_profile(self) -> EnhancedVolumeProfile:
        """Создание пустого профиля"""
        return EnhancedVolumeProfile(
            poc_price=0.0,
            poc_volume=0.0,
            poc_strength=0.0,
            value_area_high=0.0,
            value_area_low=0.0,
            value_area_volume=0.0,
            total_composite_volume=0.0,
            enhanced_cvd=0.0,
            volume_clusters=[],
            liquidity_zones=[],
            institutional_analysis={},
            hidden_volume_levels={},
            iceberg_levels=[],
            exchange_contribution={},
            analysis_timestamp=current_epoch_ms(),
            data_quality_score=0.0,
            exocharts_similarity=0.0,
            processing_stats={}
        )
    def _calculate_poc_strength(self, poc_level: VolumeLevel, sorted_levels: List[VolumeLevel]) -> float:
        """Расчёт силы POC"""
        try:
            if len(sorted_levels) < 2:
                return 1.0

            second_level_volume = sorted_levels[1].composite_volume if len(sorted_levels) > 1 else 0
            strength = poc_level.composite_volume / (second_level_volume + 1e-6)
            return min(strength / 2.0, 1.0)
        except Exception:
            return 0.5

    def _calculate_value_area(self, sorted_levels: List[VolumeLevel], total_volume: float) -> Dict:
        """Расчёт Value Area (70% объёма)"""
        try:
            target_volume = total_volume * 0.70
            accumulated_volume = 0.0
            value_area_levels = []

            for level in sorted_levels:
                value_area_levels.append(level)
                accumulated_volume += level.composite_volume
                if accumulated_volume >= target_volume:
                    break

            if not value_area_levels:
                return {"high": 0.0, "low": 0.0, "volume": 0.0}

            prices = [level.price for level in value_area_levels]
            return {
                "high": max(prices),
                "low": min(prices),
                "volume": accumulated_volume
            }
        except Exception:
            return {"high": 0.0, "low": 0.0, "volume": 0.0}

    def _calculate_enhanced_cvd(self) -> float:
        """Расчёт Enhanced Cumulative Volume Delta"""
        try:
            cvd = 0.0
            for trade in self.executed_trades:
                cvd += trade["delta"]
            return cvd
        except Exception:
            return 0.0

    def _identify_volume_clusters(self, sorted_levels: List[VolumeLevel]) -> List[Dict]:
        """Идентификация кластеров объёма"""
        try:
            clusters = []
            avg_volume = sum(l.composite_volume for l in sorted_levels) / len(sorted_levels) if sorted_levels else 0

            for level in sorted_levels:
                if level.composite_volume > avg_volume * 1.5:
                    clusters.append({
                        "price": level.price,
                        "volume": level.composite_volume,
                        "strength": level.composite_volume / avg_volume if avg_volume > 0 else 0
                    })

            return clusters[:10]
        except Exception:
            return []

    def _identify_liquidity_zones(self) -> List[Dict]:
        """Идентификация зон ликвидности"""
        try:
            zones = []
            for price, level in self.price_levels.items():
                if level.resting_liquidity > 5.0:
                    zones.append({
                        "price": price,
                        "liquidity": level.resting_liquidity,
                        "type": "high_liquidity"
                    })
            return sorted(zones, key=lambda x: x["liquidity"], reverse=True)[:10]
        except Exception:
            return []

    def _perform_institutional_analysis(self) -> Dict:
        """Анализ институциональной активности"""
        try:
            if not self.institutional_levels:
                return {"detected": False}

            buy_volume = sum(l["volume"] for l in self.institutional_levels if l["direction"] == "buy")
            sell_volume = sum(l["volume"] for l in self.institutional_levels if l["direction"] == "sell")

            return {
                "detected": True,
                "total_events": len(self.institutional_levels),
                "buy_volume": buy_volume,
                "sell_volume": sell_volume,
                "net_flow": buy_volume - sell_volume,
                "sentiment": "bullish" if buy_volume > sell_volume else "bearish"
            }
        except Exception:
            return {"detected": False}

    def _detect_iceberg_levels(self) -> List[Dict]:
        """Обнаружение iceberg ордеров"""
        try:
            iceberg_levels = []
            for price, level in self.price_levels.items():
                if level.iceberg_detected:
                    iceberg_levels.append({
                        "price": price,
                        "volume": level.composite_volume,
                        "confidence": 0.8
                    })
            return iceberg_levels[:10]
        except Exception:
            return []

    def _calculate_exchange_contribution(self) -> Dict[str, Dict]:
        """Расчёт вклада бирж"""
        try:
            exchange_stats = defaultdict(lambda: {"volume": 0.0, "trades": 0})

            for trade in self.executed_trades:
                exchange = trade["exchange"]
                exchange_stats[exchange]["volume"] += trade["quantity"]
                exchange_stats[exchange]["trades"] += 1

            return dict(exchange_stats)
        except Exception:
            return {}

    def _calculate_data_quality_score(self) -> float:
        """Расчёт качества данных"""
        try:
            scores = []

            if len(self.executed_trades) > 100:
                scores.append(1.0)
            elif len(self.executed_trades) > 50:
                scores.append(0.7)
            else:
                scores.append(0.3)

            if len(self.orderbook_snapshots) > 10:
                scores.append(1.0)
            elif len(self.orderbook_snapshots) > 5:
                scores.append(0.7)
            else:
                scores.append(0.3)

            if self.processing_stats["validation_errors"] < 10:
                scores.append(1.0)
            elif self.processing_stats["validation_errors"] < 50:
                scores.append(0.6)
            else:
                scores.append(0.2)

            return sum(scores) / len(scores) if scores else 0.0
        except Exception:
            return 0.5

    def _estimate_exocharts_similarity(self) -> float:
        """Оценка схожести с ExoCharts"""
        try:
            has_orderbook = len(self.orderbook_snapshots) > 0
            has_trades = len(self.executed_trades) > 0
            has_institutional = len(self.institutional_levels) > 0

            score = 0.0
            if has_orderbook:
                score += 0.4
            if has_trades:
                score += 0.3
            if has_institutional:
                score += 0.3

            return score
        except Exception:
            return 0.0

    def get_statistics(self) -> Dict:
        """Получение статистики"""
        return {
            "total_trades": len(self.executed_trades),
            "total_orderbook_snapshots": len(self.orderbook_snapshots),
            "unique_price_levels": len(self.price_levels),
            "institutional_events": len(self.institutional_levels),
            "analysis_count": self.analysis_count,
            "last_analysis": self.last_analysis_time,
            "processing_stats": self.processing_stats.copy(),
            "price_range": self.price_range.copy()
        }


# Экспорт классов
__all__ = [
    'EnhancedVolumeProfileCalculator',
    'EnhancedVolumeProfile',
    'VolumeLevel',
]
