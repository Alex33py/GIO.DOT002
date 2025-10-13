#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cross-Exchange Validator для GIO Crypto Bot
Кросс-проверка данных между Bybit, Binance, OKX, Coinbase
"""

import asyncio
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from config.settings import logger


class ValidationStatus(Enum):
    """Статус валидации"""
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"
    INSUFFICIENT_DATA = "insufficient_data"


class AnomalyType(Enum):
    """Типы аномалий"""
    PRICE_DEVIATION = "price_deviation"
    VOLUME_SPIKE = "volume_spike"
    LIQUIDITY_DRAIN = "liquidity_drain"
    FLASH_CRASH = "flash_crash"
    PUMP_DUMP = "pump_dump"
    WHALE_ACTIVITY = "whale_activity"
    ARBITRAGE_OPPORTUNITY = "arbitrage"


@dataclass
class PriceData:
    """Данные о цене с биржи"""
    exchange: str
    symbol: str
    price: float
    timestamp: datetime
    volume_24h: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None


@dataclass
class ValidationResult:
    """Результат валидации"""
    status: ValidationStatus
    confidence: float  # 0-100%
    exchanges_count: int
    price_deviation: float
    volume_correlation: float
    anomalies: List[AnomalyType]
    details: Dict
    timestamp: datetime


class CrossExchangeValidator:
    """
    Кросс-валидация данных между биржами

    Features:
    - Price consistency validation
    - Volume correlation analysis
    - Orderbook depth comparison
    - Trade pattern confirmation
    - Anomaly detection
    - Arbitrage opportunity detection
    """

    def __init__(self,
                 price_deviation_threshold: float = 0.001,  # 0.1%
                 volume_spike_threshold: float = 3.0,       # 3x average
                 min_exchanges_required: int = 2):
        """
        Инициализация Cross-Exchange Validator

        Args:
            price_deviation_threshold: Максимальное отклонение цены (%)
            volume_spike_threshold: Множитель для определения volume spike
            min_exchanges_required: Минимум бирж для валидации
        """
        self.price_deviation_threshold = price_deviation_threshold
        self.volume_spike_threshold = volume_spike_threshold
        self.min_exchanges_required = min_exchanges_required

        # Price history для каждой биржи
        self.price_history: Dict[str, Dict[str, deque]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=100))
        )

        # Volume history
        self.volume_history: Dict[str, Dict[str, deque]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=100))
        )

        # Orderbook data
        self.orderbook_data: Dict[str, Dict[str, Dict]] = defaultdict(
            lambda: defaultdict(dict)
        )

        # Trade flow tracking
        self.trade_flow: Dict[str, Dict[str, deque]] = defaultdict(
            lambda: defaultdict(lambda: deque(maxlen=50))
        )

        # Anomaly tracking
        self.detected_anomalies: deque = deque(maxlen=100)

        logger.info("✅ CrossExchangeValidator инициализирован")

    async def validate_price(self,
                            symbol: str,
                            prices: Dict[str, PriceData]) -> ValidationResult:
        """
        Валидация цены между биржами

        Args:
            symbol: Торговая пара (например, BTCUSDT)
            prices: Словарь {exchange: PriceData}

        Returns:
            ValidationResult
        """
        try:
            if len(prices) < self.min_exchanges_required:
                return ValidationResult(
                    status=ValidationStatus.INSUFFICIENT_DATA,
                    confidence=0.0,
                    exchanges_count=len(prices),
                    price_deviation=0.0,
                    volume_correlation=0.0,
                    anomalies=[],
                    details={'reason': 'Not enough exchanges'},
                    timestamp=datetime.utcnow()
                )

            # 1. Извлечение цен
            exchange_prices = {ex: data.price for ex, data in prices.items()}
            price_values = list(exchange_prices.values())

            # 2. Статистика цен
            mean_price = np.mean(price_values)
            std_price = np.std(price_values)
            max_price = max(price_values)
            min_price = min(price_values)

            # 3. Отклонение цены
            price_deviation = (max_price - min_price) / mean_price if mean_price > 0 else 0

            # 4. Обновление истории
            for exchange, data in prices.items():
                self.price_history[symbol][exchange].append({
                    'price': data.price,
                    'timestamp': data.timestamp
                })

            # 5. Проверка аномалий
            anomalies = []

            # Большое отклонение цены
            if price_deviation > self.price_deviation_threshold:
                anomalies.append(AnomalyType.PRICE_DEVIATION)
                logger.warning(
                    f"⚠️ Price deviation detected for {symbol}: "
                    f"{price_deviation:.2%} (threshold: {self.price_deviation_threshold:.2%})"
                )

            # Arbitrage opportunity
            if price_deviation > 0.002:  # 0.2%
                anomalies.append(AnomalyType.ARBITRAGE_OPPORTUNITY)
                cheapest_ex = min(exchange_prices, key=exchange_prices.get)
                expensive_ex = max(exchange_prices, key=exchange_prices.get)
                logger.info(
                    f"💰 Arbitrage opportunity: {symbol} "
                    f"{cheapest_ex}→{expensive_ex} spread: {price_deviation:.2%}"
                )

            # 6. Volume correlation
            volume_correlation = await self._calculate_volume_correlation(symbol, prices)

            # 7. Определение статуса
            if price_deviation > self.price_deviation_threshold * 2:
                status = ValidationStatus.INVALID
                confidence = 30.0
            elif price_deviation > self.price_deviation_threshold:
                status = ValidationStatus.WARNING
                confidence = 60.0
            else:
                status = ValidationStatus.VALID
                confidence = 95.0

            # 8. Boost confidence если volume correlation высокая
            if volume_correlation > 0.7:
                confidence = min(100.0, confidence + 10.0)

            result = ValidationResult(
                status=status,
                confidence=confidence,
                exchanges_count=len(prices),
                price_deviation=price_deviation,
                volume_correlation=volume_correlation,
                anomalies=anomalies,
                details={
                    'mean_price': mean_price,
                    'std_price': std_price,
                    'max_price': max_price,
                    'min_price': min_price,
                    'prices': exchange_prices
                },
                timestamp=datetime.utcnow()
            )

            return result

        except Exception as e:
            logger.error(f"❌ Error validating price for {symbol}: {e}")
            return ValidationResult(
                status=ValidationStatus.INVALID,
                confidence=0.0,
                exchanges_count=0,
                price_deviation=0.0,
                volume_correlation=0.0,
                anomalies=[],
                details={'error': str(e)},
                timestamp=datetime.utcnow()
            )

    async def _calculate_volume_correlation(self,
                                           symbol: str,
                                           prices: Dict[str, PriceData]) -> float:
        """Расчёт корреляции объёмов между биржами"""
        try:
            volumes = []
            for exchange, data in prices.items():
                if data.volume_24h:
                    volumes.append(data.volume_24h)
                    self.volume_history[symbol][exchange].append(data.volume_24h)

            if len(volumes) < 2:
                return 0.0

            # Нормализация объёмов
            volumes_array = np.array(volumes)
            if volumes_array.std() == 0:
                return 1.0

            # Простая корреляция через стандартное отклонение
            normalized = (volumes_array - volumes_array.mean()) / volumes_array.std()
            correlation = 1.0 - (normalized.std() / 2.0)  # Упрощенная метрика

            return max(0.0, min(1.0, correlation))

        except Exception as e:
            logger.error(f"❌ Error calculating volume correlation: {e}")
            return 0.0

    async def validate_whale_trade(self,
                                  symbol: str,
                                  trade_data: Dict[str, Dict]) -> bool:
        """
        Валидация whale trade между биржами

        Args:
            symbol: Торговая пара
            trade_data: {exchange: {price, volume, side, timestamp}}

        Returns:
            True если whale trade подтверждён на 2+ биржах
        """
        try:
            if len(trade_data) < 2:
                return False

            # Группировка по времени (в пределах 10 секунд)
            time_window = timedelta(seconds=10)
            reference_time = list(trade_data.values())[0]['timestamp']

            confirmed_trades = []
            for exchange, data in trade_data.items():
                time_diff = abs((data['timestamp'] - reference_time).total_seconds())
                if time_diff <= time_window.total_seconds():
                    confirmed_trades.append(exchange)

            # Whale trade подтверждён если найден на 2+ биржах
            is_confirmed = len(confirmed_trades) >= 2

            if is_confirmed:
                logger.info(
                    f"✅ Whale trade confirmed for {symbol} "
                    f"on {len(confirmed_trades)} exchanges: {', '.join(confirmed_trades)}"
                )

            return is_confirmed

        except Exception as e:
            logger.error(f"❌ Error validating whale trade: {e}")
            return False

    async def detect_anomalies(self, symbol: str) -> List[Dict]:
        """
        Обнаружение аномалий на рынке

        Returns:
            Список обнаруженных аномалий
        """
        anomalies = []

        try:
            # 1. Flash crash detection
            flash_crash = await self._detect_flash_crash(symbol)
            if flash_crash:
                anomalies.append({
                    'type': AnomalyType.FLASH_CRASH,
                    'symbol': symbol,
                    'details': flash_crash,
                    'timestamp': datetime.utcnow()
                })

            # 2. Pump/Dump detection
            pump_dump = await self._detect_pump_dump(symbol)
            if pump_dump:
                anomalies.append({
                    'type': AnomalyType.PUMP_DUMP,
                    'symbol': symbol,
                    'details': pump_dump,
                    'timestamp': datetime.utcnow()
                })

            # 3. Liquidity drain detection
            liquidity_drain = await self._detect_liquidity_drain(symbol)
            if liquidity_drain:
                anomalies.append({
                    'type': AnomalyType.LIQUIDITY_DRAIN,
                    'symbol': symbol,
                    'details': liquidity_drain,
                    'timestamp': datetime.utcnow()
                })

            # Store anomalies
            for anomaly in anomalies:
                self.detected_anomalies.append(anomaly)

            return anomalies

        except Exception as e:
            logger.error(f"❌ Error detecting anomalies: {e}")
            return []

    async def _detect_flash_crash(self, symbol: str) -> Optional[Dict]:
        """Обнаружение flash crash"""
        try:
            # Проверка резкого падения цены на 2+ биржах
            recent_prices = {}
            for exchange, prices in self.price_history[symbol].items():
                if len(prices) >= 2:
                    recent_prices[exchange] = list(prices)[-2:]

            if len(recent_prices) < 2:
                return None

            # Расчёт изменения цены
            price_changes = {}
            for exchange, prices in recent_prices.items():
                if len(prices) == 2:
                    change = (prices[1]['price'] - prices[0]['price']) / prices[0]['price']
                    price_changes[exchange] = change

            # Flash crash если 2+ биржи показывают падение >3%
            crashes = [ex for ex, change in price_changes.items() if change < -0.03]

            if len(crashes) >= 2:
                return {
                    'exchanges': crashes,
                    'price_changes': price_changes,
                    'severity': 'high'
                }

            return None

        except Exception as e:
            logger.error(f"❌ Error detecting flash crash: {e}")
            return None

    async def _detect_pump_dump(self, symbol: str) -> Optional[Dict]:
        """Обнаружение pump/dump"""
        try:
            # Проверка резкого роста/падения объёма + цены
            volume_spikes = {}
            price_changes = {}

            for exchange in self.volume_history[symbol].keys():
                volumes = list(self.volume_history[symbol][exchange])
                prices = list(self.price_history[symbol][exchange])

                if len(volumes) >= 5 and len(prices) >= 2:
                    avg_volume = np.mean([v for v in volumes[:-1]])
                    current_volume = volumes[-1]

                    if avg_volume > 0:
                        volume_ratio = current_volume / avg_volume
                        if volume_ratio > self.volume_spike_threshold:
                            volume_spikes[exchange] = volume_ratio

                            # Проверка изменения цены
                            price_change = (prices[-1]['price'] - prices[-2]['price']) / prices[-2]['price']
                            price_changes[exchange] = price_change

            # Pump/Dump если 2+ биржи показывают volume spike + price change >5%
            if len(volume_spikes) >= 2:
                avg_price_change = np.mean(list(price_changes.values()))
                if abs(avg_price_change) > 0.05:
                    return {
                        'exchanges': list(volume_spikes.keys()),
                        'volume_spikes': volume_spikes,
                        'price_changes': price_changes,
                        'direction': 'pump' if avg_price_change > 0 else 'dump'
                    }

            return None

        except Exception as e:
            logger.error(f"❌ Error detecting pump/dump: {e}")
            return None

    async def _detect_liquidity_drain(self, symbol: str) -> Optional[Dict]:
        """Обнаружение ухода ликвидности"""
        try:
            # Проверка резкого уменьшения bid/ask объёмов
            liquidity_drops = {}

            for exchange, data in self.orderbook_data[symbol].items():
                if 'bid_volume' in data and 'ask_volume' in data:
                    total_liquidity = data['bid_volume'] + data['ask_volume']
                    # TODO: Сравнить с исторической ликвидностью
                    # Для простоты - пропускаем пока
                    pass

            return None

        except Exception as e:
            logger.error(f"❌ Error detecting liquidity drain: {e}")
            return None

    def get_best_price(self, symbol: str, side: str = 'buy') -> Optional[Tuple[str, float]]:
        """
        Получение лучшей цены среди всех бирж

        Args:
            symbol: Торговая пара
            side: 'buy' или 'sell'

        Returns:
            (exchange, price) или None
        """
        try:
            prices = {}
            for exchange, history in self.price_history[symbol].items():
                if history:
                    latest = history[-1]
                    prices[exchange] = latest['price']

            if not prices:
                return None

            if side == 'buy':
                # Для покупки ищем минимальную цену
                best_exchange = min(prices, key=prices.get)
            else:
                # Для продажи ищем максимальную цену
                best_exchange = max(prices, key=prices.get)

            return (best_exchange, prices[best_exchange])

        except Exception as e:
            logger.error(f"❌ Error getting best price: {e}")
            return None


# Экспорт
__all__ = ["CrossExchangeValidator", "ValidationStatus", "AnomalyType", "ValidationResult"]
