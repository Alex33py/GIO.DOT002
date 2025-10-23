#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Wyckoff Phase Detection с Volume Spread Analysis (VSA)
Определяет фазы рыночного цикла: Accumulation, Markup, Distribution, Markdown
"""
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import numpy as np
from dataclasses import dataclass


@dataclass
class WyckoffPhase:
    """Результат анализа фазы Wyckoff"""

    phase: str  # "Accumulation", "Markup", "Distribution", "Markdown", "Unknown"
    confidence: float  # 0-100%
    sub_phase: Optional[str]  # Детальная фаза (PS, SC, AR, ST, SOS, etc.)
    signals: List[str]  # Обнаруженные сигналы
    description: str  # Описание текущей фазы
    action: str  # Рекомендуемое действие


class WyckoffAnalyzer:
    """Анализатор фаз Wyckoff с VSA"""

    def __init__(self, bot):
        from config.settings import logger

        self.logger = logger
        self.bot = bot

        # Пороговые значения для определения фаз
        self.thresholds = {
            "volume_spike": 1.5,  # Объём выше среднего в 1.5 раза
            "spring_range": 0.02,  # 2% ниже минимума
            "upthrust_range": 0.02,  # 2% выше максимума
            "accumulation_range": 0.05,  # 5% боковик
            "distribution_range": 0.05,  # 5% боковик на топе
        }

        self.logger.info("✅ WyckoffAnalyzer инициализирован")

    async def analyze_phase(self, symbol: str, timeframe: str = "60") -> WyckoffPhase:
        """
        Основной метод анализа фазы Wyckoff

        Args:
            symbol: Торговая пара (BTCUSDT)
            timeframe: Таймфрейм для анализа (1h, 4h, 1d)

        Returns:
            WyckoffPhase с определённой фазой и рекомендациями
        """
        try:
            # 1. Получаем исторические данные
            candles = await self._get_candles(symbol, timeframe, limit=200)
            if not candles:
                return self._unknown_phase("Недостаточно данных")

            # 2. Вычисляем метрики VSA
            vsa_metrics = self._calculate_vsa_metrics(candles)

            # 3. Получаем текущие рыночные данные
            market_data = await self._get_market_data(symbol)

            # 4. Определяем фазу Wyckoff
            phase = self._detect_phase(candles, vsa_metrics, market_data)

            self.logger.info(
                f"📊 {symbol} Wyckoff Phase: {phase.phase} ({phase.confidence:.1f}%)"
            )
            return phase

        except Exception as e:
            self.logger.error(
                f"Error analyzing Wyckoff phase for {symbol}: {e}", exc_info=True
            )
            return self._unknown_phase(f"Ошибка анализа: {str(e)}")

    async def _get_candles(self, symbol: str, timeframe: str, limit: int) -> List[Dict]:
        """Получить исторические свечи"""
        try:
            if hasattr(self.bot, "bybit_connector"):
                # ✅ Сначала обновляем кэш свечей
                await self.bot.bybit_connector.update_klines_cache(
                    symbol, timeframe, limit
                )

                # ✅ Затем получаем из кэша
                cache_key = f"{symbol}:{timeframe}"
                cache_data = self.bot.bybit_connector.klines_cache.get(cache_key, {})

                # ✅ ИЗВЛЕКАЕМ СПИСОК СВЕЧЕЙ ИЗ СЛОВАРЯ!
                if isinstance(cache_data, dict) and "candles" in cache_data:
                    candles = cache_data["candles"]
                elif isinstance(cache_data, list):
                    candles = cache_data  # На случай старого формата
                else:
                    candles = []

                if candles and len(candles) >= limit:
                    # Берём последние N свечей
                    result = candles[-limit:]
                    self.logger.info(
                        f"✅ Получено {len(result)} свечей для {symbol} ({timeframe})"
                    )
                    return result
                elif candles:
                    # Берём сколько есть
                    self.logger.warning(
                        f"⚠️ Получено только {len(candles)} свечей для {symbol} (запрошено {limit})"
                    )
                    return candles
                else:
                    self.logger.warning(f"⚠️ Нет данных свечей для {symbol}")
                    return []
            else:
                self.logger.error("❌ bybit_connector не найден!")
                return []

        except Exception as e:
            self.logger.error(f"❌ Error fetching candles: {e}", exc_info=True)
            return []

    def _calculate_vsa_metrics(self, candles: List[Dict]) -> Dict:
        """
        Вычислить метрики Volume Spread Analysis

        Returns:
            {
                "avg_volume": float,
                "avg_spread": float,
                "current_volume": float,
                "current_spread": float,
                "volume_ratio": float,
                "spread_ratio": float,
                "effort_result": str,  # "no_demand", "no_supply", "normal"
            }
        """
        if len(candles) < 20:
            return {}

        # Извлекаем данные
        volumes = [float(c.get("volume", 0)) for c in candles]
        highs = [float(c.get("high", 0)) for c in candles]
        lows = [float(c.get("low", 0)) for c in candles]
        closes = [float(c.get("close", 0)) for c in candles]

        # Вычисляем спреды (high - low)
        spreads = [h - l for h, l in zip(highs, lows)]

        # Средние значения (последние 20 свечей)
        avg_volume = np.mean(volumes[-20:])
        avg_spread = np.mean(spreads[-20:])

        # Текущие значения
        current_volume = volumes[-1]
        current_spread = spreads[-1]
        current_close = closes[-1]
        prev_close = closes[-2] if len(closes) > 1 else closes[-1]

        # Коэффициенты
        volume_ratio = current_volume / avg_volume if avg_volume > 0 else 1.0
        spread_ratio = current_spread / avg_spread if avg_spread > 0 else 1.0

        # Effort vs Result (ключевая концепция VSA)
        effort_result = self._analyze_effort_result(
            volume_ratio, spread_ratio, current_close, prev_close
        )

        return {
            "avg_volume": avg_volume,
            "avg_spread": avg_spread,
            "current_volume": current_volume,
            "current_spread": current_spread,
            "volume_ratio": volume_ratio,
            "spread_ratio": spread_ratio,
            "effort_result": effort_result,
            "price_direction": "up" if current_close > prev_close else "down",
        }

    def _analyze_effort_result(
        self,
        volume_ratio: float,
        spread_ratio: float,
        current_close: float,
        prev_close: float,
    ) -> str:
        """
        Анализ Effort (объём) vs Result (движение цены)

        Returns:
            "no_demand" - нет спроса (медвежий сигнал)
            "no_supply" - нет предложения (бычий сигнал)
            "normal" - нормальное соотношение
        """
        price_change = (
            (current_close - prev_close) / prev_close if prev_close > 0 else 0
        )

        # No Demand: Высокий объём + узкий спред + цена не растёт
        if volume_ratio > 1.5 and spread_ratio < 0.8 and price_change < 0.002:
            return "no_demand"

        # No Supply: Высокий объём + узкий спред + цена не падает
        if volume_ratio > 1.5 and spread_ratio < 0.8 and price_change > -0.002:
            return "no_supply"

        return "normal"

    async def _get_market_data(self, symbol: str) -> Dict:
        """Получить текущие рыночные данные"""
        try:
            market_data = {}

            # CVD
            if hasattr(self.bot, "orderbook_analyzer"):
                cvd_data = await self.bot.orderbook_analyzer.get_cvd(symbol)
                market_data["cvd"] = cvd_data.get("cvd_pct", 0)

            # L/S Ratio (из существующих данных бота)
            if hasattr(self.bot, "sentiment_cache"):
                sentiment = self.bot.sentiment_cache.get(symbol, {})
                market_data["ls_ratio"] = sentiment.get("ls_ratio", 1.0)

            # Whale Activity
            if hasattr(self.bot, "whale_tracker") and hasattr(
                self.bot.whale_tracker, "get_recent_whales_from_db"
            ):
                try:
                    # ✅ БЕЗ await! Метод НЕ async!
                    whale_data = self.bot.whale_tracker.get_recent_whales_from_db(
                        symbol=symbol, minutes=5
                    )
                    # Фильтруем киты >$100K вручную
                    if whale_data:
                        whale_data = [
                            w for w in whale_data if w.get("usd_value", 0) >= 100000
                        ]
                    if whale_data:
                        # Рассчитываем net flow (buy - sell)
                        net_flow = sum(
                            w.get("usd_value", 0)
                            * (1 if w.get("side", "").lower() == "buy" else -1)
                            for w in whale_data
                        )
                        market_data["whale_net"] = net_flow
                        self.logger.debug(
                            f"🐋 Whale Net Flow {symbol}: ${net_flow:,.0f}"
                        )
                    else:
                        market_data["whale_net"] = 0
                except Exception as e:
                    self.logger.error(f"Error getting whale data: {e}")
                    market_data["whale_net"] = 0
            else:
                market_data["whale_net"] = 0

            return market_data
        except Exception as e:
            self.logger.error(f"Error getting market data: {e}")
            return {}

    def _detect_phase(
        self, candles: List[Dict], vsa_metrics: Dict, market_data: Dict
    ) -> WyckoffPhase:
        """Определить фазу Wyckoff на основе VSA и рыночных данных"""
        if not candles or not vsa_metrics:
            return self._unknown_phase("Недостаточно данных VSA")

        # Извлекаем данные
        closes = [float(c.get("close", 0)) for c in candles[-50:]]
        highs = [float(c.get("high", 0)) for c in candles[-50:]]
        lows = [float(c.get("low", 0)) for c in candles[-50:]]

        current_price = closes[-1]
        range_high = max(highs[-20:])
        range_low = min(lows[-20:])
        price_range = (range_high - range_low) / range_low if range_low > 0 else 0

        # CVD и другие метрики
        cvd = market_data.get("cvd", 0)
        ls_ratio = market_data.get("ls_ratio", 1.0)
        whale_net = market_data.get("whale_net", 0)
        effort_result = vsa_metrics.get("effort_result", "normal")
        volume_ratio = vsa_metrics.get("volume_ratio", 1.0)

        # Определяем тренд (последние 50 свечей)
        trend = self._determine_trend(closes)

        # Проверяем Spring (ложный пробой вниз)
        spring_detected = self._detect_spring(candles[-20:], range_low)

        # Проверяем Upthrust (ложный пробой вверх)
        upthrust_detected = self._detect_upthrust(candles[-20:], range_high)

        signals = []

        # === PHASE A: ACCUMULATION ===
        if (
            price_range < self.thresholds["accumulation_range"]
            and trend in ["down", "sideways"]
            and (effort_result == "no_supply" or cvd > 20)
            and spring_detected
        ):
            signals.append("Spring detected (ложный пробой вниз)")
            signals.append(f"CVD: {cvd:+.1f}% (покупательское давление)")
            if whale_net > 0:
                signals.append("Киты накапливают позиции")

            return WyckoffPhase(
                phase="Accumulation",
                confidence=min(85 + (cvd / 10), 95),
                sub_phase="Phase A - Spring",
                signals=signals,
                description="Умные деньги накапливают актив после падения. Ожидается переход к росту.",
                action="🟢 НАКАПЛИВАТЬ лонг-позиции на откатах",
            )

        # === PHASE B: MARKUP ===
        if (
            trend == "up"
            and volume_ratio > 1.2
            and cvd > 20
            and current_price > range_high * 1.01
        ):
            signals.append("Пробой сопротивления с объёмом")
            signals.append(f"CVD: {cvd:+.1f}% (сильная покупка)")
            signals.append(f"Volume Ratio: {volume_ratio:.2f}x")

            return WyckoffPhase(
                phase="Markup",
                confidence=min(80 + (volume_ratio * 5), 95),
                sub_phase="Phase B - Sign of Strength (SOS)",
                signals=signals,
                description="Уверенный рост цены. Фаза накопления завершена, начался восходящий тренд.",
                action="🟢 ДЕРЖАТЬ лонги, добавлять на откатах к поддержке",
            )

        # PHASE C: DISTRIBUTION
        if (
            price_range < self.thresholds["distribution_range"]
            and trend in ["up", "sideways"]
            and current_price > max(closes[-100:]) * 0.90
            and (
                effort_result == "no_demand"
                or (ls_ratio < 0.5 and whale_net < -50000)
                or (cvd < -50 and whale_net < -50000)
            )
        ):
            signals.append(f"Боковик на высоких уровнях ({price_range*100:.1f}%)")

            if ls_ratio < 0.5:
                signals.append(
                    f"L/S Ratio: {ls_ratio:.2f} (экстремальный перевес в шорты)"
                )

            if cvd < -50:
                signals.append(f"CVD: {cvd:+.1f}% (экстремальная продажа)")

            if whale_net < -50000:
                signals.append(f"Киты продают (Net: ${whale_net:,.0f})")

            if upthrust_detected:
                signals.append("⚠️ Upthrust detected (ложный пробой вверх)")

            confidence = 70
            if abs(cvd) > 50:
                confidence += 10
            if abs(whale_net) > 50000:
                confidence += abs(whale_net) / 10000
            if upthrust_detected:
                confidence += 5

            return WyckoffPhase(
                phase="Distribution",
                confidence=min(confidence, 92),
                sub_phase="Phase C - Distribution Zone",
                signals=signals,
                description="Умные деньги распределяют актив. Сильное давление продавцов.",
                action="🔴 ФИКСИРОВАТЬ прибыль, готовить шорты",
            )

        # === PHASE D: MARKDOWN ===
        if (
            trend == "down"
            and volume_ratio > 1.2
            and cvd < -20
            and current_price < range_low * 0.99
        ):
            signals.append("Пробой поддержки с объёмом")
            signals.append(f"CVD: {cvd:+.1f}% (сильная продажа)")
            signals.append(f"Volume Ratio: {volume_ratio:.2f}x")

            return WyckoffPhase(
                phase="Markdown",
                confidence=min(80 + (volume_ratio * 5), 95),
                sub_phase="Phase D - Last Point of Supply (LPSY)",
                signals=signals,
                description="Распродажа актива. Ожидается продолжение падения до новой зоны накопления.",
                action="🔴 ШОРТИТЬ или выйти в кэш, ждать Phase A",
            )

        # === UNKNOWN / TRANSITION ===
        signals.append(f"Price Range: {price_range*100:.1f}%")
        signals.append(f"Trend: {trend}")
        signals.append(f"Effort-Result: {effort_result}")

        return WyckoffPhase(
            phase="Unknown",
            confidence=40,
            sub_phase="Transition Zone",
            signals=signals,
            description="Рынок находится в переходной зоне между фазами. Ожидайте подтверждения.",
            action="⚪ НАБЛЮДАТЬ, не открывать крупные позиции",
        )

    def _determine_trend(self, closes: List[float]) -> str:
        """Определить тренд по последним 50 свечам"""
        if len(closes) < 50:
            return "unknown"

        # Простая SMA
        sma_20 = np.mean(closes[-20:])
        sma_50 = np.mean(closes[-50:])

        current_price = closes[-1]

        if current_price > sma_20 > sma_50:
            return "up"
        elif current_price < sma_20 < sma_50:
            return "down"
        else:
            return "sideways"

    def _detect_spring(self, candles: List[Dict], range_low: float) -> bool:
        """Обнаружить Spring (ложный пробой вниз)"""
        if len(candles) < 5:
            return False

        lows = [float(c.get("low", 0)) for c in candles]
        closes = [float(c.get("close", 0)) for c in candles]

        # Spring: low пробивает range_low, но close закрывается выше
        for i in range(-5, 0):
            if lows[i] < range_low * (1 - self.thresholds["spring_range"]):
                if closes[i] > range_low:
                    return True

        return False

    def _detect_upthrust(self, candles: List[Dict], range_high: float) -> bool:
        """Обнаружить Upthrust (ложный пробой вверх)"""
        if len(candles) < 5:
            return False

        highs = [float(c.get("high", 0)) for c in candles]
        closes = [float(c.get("close", 0)) for c in candles]

        # Upthrust: high пробивает range_high, но close закрывается ниже
        for i in range(-5, 0):
            if highs[i] > range_high * (1 + self.thresholds["upthrust_range"]):
                if closes[i] < range_high:
                    return True

        return False

    def _unknown_phase(self, reason: str = "") -> WyckoffPhase:
        """Возвращает Unknown фазу"""
        return WyckoffPhase(
            phase="Unknown",
            confidence=0,
            sub_phase=None,
            signals=[reason] if reason else [],
            description="Невозможно определить фазу Wyckoff",
            action="⚪ Дождитесь дополнительных данных",
        )
