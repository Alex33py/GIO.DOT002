#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Liquidity Depth Analyzer
Расширенный анализ глубины ликвидности с детальными метриками
"""
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
from dataclasses import dataclass


@dataclass
class LiquidityLevel:
    """Уровень ликвидности"""
    price: float
    volume: float
    volume_usd: float
    is_bid: bool


@dataclass
class LiquidityAnalysis:
    """Результат анализа ликвидности"""
    current_price: float
    total_bid: float
    total_ask: float
    imbalance: float
    imbalance_ratio: float

    # Spread
    best_bid: float
    best_ask: float
    spread: float
    spread_pct: float

    # Key levels
    resistance_zones: List[Dict]
    support_zones: List[Dict]
    poc_price: float  # Point of Control

    # Slippage
    slippage_buy: Dict[float, float]
    slippage_sell: Dict[float, float]

    # Risk assessment
    liquidity_score: float
    bid_ask_ratio: float
    market_depth_status: str

    # Trading signals
    long_signal: Dict
    short_signal: Dict

    # Historical comparison
    avg_bid_6h: Optional[float] = None
    avg_ask_6h: Optional[float] = None
    avg_imbalance_6h: Optional[float] = None


class EnhancedLiquidityAnalyzer:
    """Расширенный анализатор ликвидности"""

    def __init__(self, bot):
        from config.settings import logger

        self.logger = logger
        self.bot = bot

        # История ликвидности для трендов
        self.liquidity_history = {}  # {symbol: [(timestamp, bid, ask, imbalance)]}

        self.logger.info("✅ EnhancedLiquidityAnalyzer инициализирован")

    async def analyze(self, symbol: str) -> LiquidityAnalysis:
        """
        Полный анализ ликвидности

        Args:
            symbol: Торговая пара (BTCUSDT)

        Returns:
            LiquidityAnalysis с детальными метриками
        """
        try:
            # 1. Получаем orderbook
            orderbook = await self._get_orderbook(symbol)
            if not orderbook:
                raise ValueError("Не удалось получить orderbook")

            # 2. Получаем текущую цену
            current_price = await self._get_current_price(symbol)

            # 3. Обрабатываем orderbook
            bids, asks = self._process_orderbook(orderbook)

            # 4. Базовые метрики
            total_bid = sum(level.volume_usd for level in bids)
            total_ask = sum(level.volume_usd for level in asks)
            imbalance = total_bid - total_ask
            imbalance_ratio = total_bid / total_ask if total_ask > 0 else 0

            # 5. Spread
            best_bid = bids[0].price if bids else current_price
            best_ask = asks[0].price if asks else current_price
            spread = best_ask - best_bid
            spread_pct = (spread / current_price) * 100 if current_price > 0 else 0

            # 6. Key levels
            resistance_zones = self._find_resistance_zones(asks, current_price)
            support_zones = self._find_support_zones(bids, current_price)
            poc_price = self._find_poc(bids, asks, current_price)

            # 7. Slippage
            slippage_buy = self._calculate_slippage(asks, is_buy=True)
            slippage_sell = self._calculate_slippage(bids, is_buy=False)

            # 8. Risk assessment
            liquidity_score = self._calculate_liquidity_score(
                total_bid, total_ask, spread_pct
            )
            market_depth_status = self._assess_market_depth(liquidity_score)

            # 9. Trading signals
            long_signal = self._generate_long_signal(
                current_price, support_zones, imbalance_ratio, liquidity_score
            )
            short_signal = self._generate_short_signal(
                current_price, resistance_zones, imbalance_ratio, liquidity_score
            )

            # 10. Исторический анализ
            historical = self._get_historical_metrics(symbol)

            # 11. Сохраняем в историю
            self._save_to_history(symbol, total_bid, total_ask, imbalance)

            return LiquidityAnalysis(
                current_price=current_price,
                total_bid=total_bid,
                total_ask=total_ask,
                imbalance=imbalance,
                imbalance_ratio=imbalance_ratio,
                best_bid=best_bid,
                best_ask=best_ask,
                spread=spread,
                spread_pct=spread_pct,
                resistance_zones=resistance_zones,
                support_zones=support_zones,
                poc_price=poc_price,
                slippage_buy=slippage_buy,
                slippage_sell=slippage_sell,
                liquidity_score=liquidity_score,
                bid_ask_ratio=imbalance_ratio,
                market_depth_status=market_depth_status,
                long_signal=long_signal,
                short_signal=short_signal,
                **historical
            )

        except Exception as e:
            self.logger.error(f"Error analyzing liquidity for {symbol}: {e}", exc_info=True)
            raise

    async def _get_orderbook(self, symbol: str) -> Dict:
        """Получить orderbook"""
        if hasattr(self.bot, 'bybit_connector'):
            return await self.bot.bybit_connector.get_orderbook(symbol, limit=50)
        return {}

    async def _get_current_price(self, symbol: str) -> float:
        """Получить текущую цену"""
        try:
            if hasattr(self.bot, 'bybit_connector'):
                ticker = await self.bot.bybit_connector.get_ticker(symbol)
                # Правильное поле для Bybit V5 API:
                if 'result' in ticker and 'list' in ticker['result']:
                    return float(ticker['result']['list'][0]['lastPrice'])
                # Или попробуйте другой формат:
                elif 'lastPrice' in ticker:
                    return float(ticker['lastPrice'])
            return 0.0
        except Exception as e:
            self.logger.error(f"Error getting current price: {e}")
            # Fallback: используем best_bid/best_ask среднее
            return 0.0


    def _process_orderbook(self, orderbook: Dict) -> Tuple[List[LiquidityLevel], List[LiquidityLevel]]:
        """Обработать orderbook"""
        bids = []
        asks = []

        # Bids (покупки)
        for price_str, volume_str in orderbook.get('bids', []):
            price = float(price_str)
            volume = float(volume_str)
            bids.append(LiquidityLevel(
                price=price,
                volume=volume,
                volume_usd=price * volume,
                is_bid=True
            ))

        # Asks (продажи)
        for price_str, volume_str in orderbook.get('asks', []):
            price = float(price_str)
            volume = float(volume_str)
            asks.append(LiquidityLevel(
                price=price,
                volume=volume,
                volume_usd=price * volume,
                is_bid=False
            ))

        return bids, asks

    def _find_resistance_zones(self, asks: List[LiquidityLevel], current_price: float) -> List[Dict]:
        """Найти зоны сопротивления"""
        zones = []

        # Группируем уровни по зонам (по 0.5% от цены)
        zone_width = current_price * 0.005

        # Сортируем по объёму
        sorted_asks = sorted(asks, key=lambda x: x.volume_usd, reverse=True)

        # Берём топ-3 уровня
        for i, level in enumerate(sorted_asks[:3]):
            zone_low = level.price - zone_width / 2
            zone_high = level.price + zone_width / 2

            # Суммируем объём в зоне
            zone_volume = sum(
                ask.volume_usd for ask in asks
                if zone_low <= ask.price <= zone_high
            )

            strength = "Heavy" if i == 0 else "Medium" if i == 1 else "Light"

            zones.append({
                'price_low': zone_low,
                'price_high': zone_high,
                'volume_usd': zone_volume,
                'strength': strength
            })

        return zones

    def _find_support_zones(self, bids: List[LiquidityLevel], current_price: float) -> List[Dict]:
        """Найти зоны поддержки"""
        zones = []

        # Группируем уровни по зонам
        zone_width = current_price * 0.005

        # Сортируем по объёму
        sorted_bids = sorted(bids, key=lambda x: x.volume_usd, reverse=True)

        # Берём топ-3 уровня
        for i, level in enumerate(sorted_bids[:3]):
            zone_low = level.price - zone_width / 2
            zone_high = level.price + zone_width / 2

            # Суммируем объём в зоне
            zone_volume = sum(
                bid.volume_usd for bid in bids
                if zone_low <= bid.price <= zone_high
            )

            strength = "Strong" if i == 0 else "Medium" if i == 1 else "Weak"

            zones.append({
                'price_low': zone_low,
                'price_high': zone_high,
                'volume_usd': zone_volume,
                'strength': strength
            })

        return zones

    def _find_poc(self, bids: List[LiquidityLevel], asks: List[LiquidityLevel], current_price: float) -> float:
        """Найти Point of Control (цена с максимальным объёмом)"""
        all_levels = bids + asks
        if not all_levels:
            return current_price

        # Находим уровень с максимальным объёмом
        poc_level = max(all_levels, key=lambda x: x.volume_usd)
        return poc_level.price

    def _calculate_slippage(self, levels: List[LiquidityLevel], is_buy: bool) -> Dict[float, float]:
        """Рассчитать проскальзывание для разных размеров ордеров"""
        slippage = {}
        order_sizes = [10000, 100000, 500000, 1000000]  # USD

        for order_size in order_sizes:
            remaining = order_size
            total_volume = 0
            weighted_price_sum = 0

            for level in levels:
                if remaining <= 0:
                    break

                # Сколько можем купить/продать на этом уровне
                available_usd = level.volume_usd
                to_fill = min(remaining, available_usd)

                # Взвешенная цена
                weighted_price_sum += level.price * to_fill
                total_volume += to_fill
                remaining -= to_fill

            if remaining > 0:
                # Недостаточно ликвидности
                slippage[order_size] = None
            else:
                # Средняя цена исполнения
                avg_price = weighted_price_sum / total_volume if total_volume > 0 else 0
                start_price = levels[0].price if levels else 0

                if start_price > 0:
                    # Проскальзывание в %
                    slippage_pct = abs((avg_price - start_price) / start_price) * 100
                    slippage[order_size] = slippage_pct
                else:
                    slippage[order_size] = 0.0

        return slippage


    def _calculate_liquidity_score(self, total_bid: float, total_ask: float, spread_pct: float) -> float:
        """Рассчитать оценку ликвидности (0-10)"""
        score = 0

        # 1. Общий объём (max 4 points)
        total_volume = total_bid + total_ask
        if total_volume > 10_000_000:
            score += 4
        elif total_volume > 5_000_000:
            score += 3
        elif total_volume > 2_000_000:
            score += 2
        elif total_volume > 1_000_000:
            score += 1

        # 2. Баланс BID/ASK (max 3 points)
        ratio = total_bid / total_ask if total_ask > 0 else 0
        if 0.8 <= ratio <= 1.2:
            score += 3
        elif 0.5 <= ratio <= 2.0:
            score += 2
        else:
            score += 1

        # 3. Спред (max 3 points)
        if spread_pct < 0.05:
            score += 3
        elif spread_pct < 0.15:
            score += 2
        elif spread_pct < 0.30:
            score += 1

        return score

    def _assess_market_depth(self, liquidity_score: float) -> str:
        """Оценить глубину рынка"""
        if liquidity_score >= 8:
            return "Excellent"
        elif liquidity_score >= 6:
            return "Good"
        elif liquidity_score >= 4:
            return "Medium"
        else:
            return "Low"

    def _generate_long_signal(
        self,
        current_price: float,
        support_zones: List[Dict],
        imbalance_ratio: float,
        liquidity_score: float
    ) -> Dict:
        """Генерация сигнала на покупку"""
        signal = {
            'recommended': False,
            'confidence': 0,
            'entry': None,
            'stop_loss': None,
            'target': None,
            'risk_reward': None,
            'reasons': []
        }

        # Условия для лонга
        conditions = []

        # 1. Сильная поддержка
        if support_zones and support_zones[0]['strength'] == 'Strong':
            conditions.append("Strong support detected")
            signal['confidence'] += 30

        # 2. BID >> ASK
        if imbalance_ratio > 2.0:
            conditions.append(f"Strong BUY pressure (ratio: {imbalance_ratio:.2f}x)")
            signal['confidence'] += 25

        # 3. Хорошая ликвидность
        if liquidity_score >= 6:
            conditions.append("Good liquidity")
            signal['confidence'] += 15

        # Если confidence >= 50%, рекомендуем
        if signal['confidence'] >= 50:
            signal['recommended'] = True
            signal['reasons'] = conditions

            # Рассчитываем уровни
            if support_zones:
                support = (support_zones[0]['price_low'] + support_zones[0]['price_high']) / 2
                signal['entry'] = current_price
                signal['stop_loss'] = support * 0.99  # -1% от поддержки
                signal['target'] = current_price * 1.015  # +1.5%

                risk = abs(signal['entry'] - signal['stop_loss'])
                reward = abs(signal['target'] - signal['entry'])
                signal['risk_reward'] = reward / risk if risk > 0 else 0

        return signal

    def _generate_short_signal(
        self,
        current_price: float,
        resistance_zones: List[Dict],
        imbalance_ratio: float,
        liquidity_score: float
    ) -> Dict:
        """Генерация сигнала на продажу"""
        signal = {
            'recommended': False,
            'confidence': 0,
            'entry': None,
            'stop_loss': None,
            'target': None,
            'risk_reward': None,
            'reasons': []
        }

        # Условия для шорта
        conditions = []

        # 1. Сильное сопротивление
        if resistance_zones and resistance_zones[0]['strength'] == 'Heavy':
            conditions.append("Heavy resistance detected")
            signal['confidence'] += 30

        # 2. ASK >> BID
        if imbalance_ratio < 0.5:
            conditions.append(f"Strong SELL pressure (ratio: {imbalance_ratio:.2f}x)")
            signal['confidence'] += 25

        # 3. Хорошая ликвидность на продажу
        if liquidity_score >= 6:
            conditions.append("Good liquidity")
            signal['confidence'] += 15

        # Если confidence >= 50%, рекомендуем
        if signal['confidence'] >= 50:
            signal['recommended'] = True
            signal['reasons'] = conditions

            # Рассчитываем уровни
            if resistance_zones:
                resistance = (resistance_zones[0]['price_low'] + resistance_zones[0]['price_high']) / 2
                signal['entry'] = current_price
                signal['stop_loss'] = resistance * 1.01  # +1% от сопротивления
                signal['target'] = current_price * 0.985  # -1.5%

                risk = abs(signal['entry'] - signal['stop_loss'])
                reward = abs(signal['entry'] - signal['target'])
                signal['risk_reward'] = reward / risk if risk > 0 else 0

        return signal

    def _get_historical_metrics(self, symbol: str) -> Dict:
        """Получить исторические метрики (за 6 часов)"""
        if symbol not in self.liquidity_history:
            return {}

        cutoff_time = datetime.now() - timedelta(hours=6)
        recent_data = [
            (ts, bid, ask, imb) for ts, bid, ask, imb in self.liquidity_history[symbol]
            if ts >= cutoff_time
        ]

        if not recent_data:
            return {}

        bids = [bid for _, bid, _, _ in recent_data]
        asks = [ask for _, ask, _, _ in recent_data]
        imbalances = [imb for _, _, _, imb in recent_data]

        return {
            'avg_bid_6h': np.mean(bids),
            'avg_ask_6h': np.mean(asks),
            'avg_imbalance_6h': np.mean(imbalances)
        }

    def _save_to_history(self, symbol: str, bid: float, ask: float, imbalance: float):
        """Сохранить данные в историю"""
        if symbol not in self.liquidity_history:
            self.liquidity_history[symbol] = []

        self.liquidity_history[symbol].append((
            datetime.now(),
            bid,
            ask,
            imbalance
        ))

        # Удаляем данные старше 24 часов
        cutoff_time = datetime.now() - timedelta(hours=24)
        self.liquidity_history[symbol] = [
            entry for entry in self.liquidity_history[symbol]
            if entry[0] >= cutoff_time
        ]
