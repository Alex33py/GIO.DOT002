#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Confirm Filter - Фильтр подтверждения сигналов
Проверяет CVD, объём и паттерн свечи перед генерацией сигнала
"""


import time
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from config.settings import logger


class ConfirmFilter:
    """
    Фильтр подтверждения торговых сигналов


    Проверяет 3 критерия:
    1. CVD (Cumulative Volume Delta) ≥ 60%
    2. Volume ≥ 1.5x среднего
    3. Candle pattern подтверждает направление
    """

    def __init__(
        self,
        bot_instance=None,
        cvd_threshold: float = 0.5,  # ИЗМЕНЕНО: 2.0 → 0.5 (процент!)
        volume_multiplier: float = 1.5,  # ИЗМЕНЕНО: 1.3 → 1.5
        candle_check: bool = False,  # ИЗМЕНЕНО: True → False
        min_large_trade_value: float = 10000,
        adaptive_mode: bool = True,  # НОВОЕ: адаптивные пороги
    ):
        """
        Инициализация фильтра

        Args:
            bot_instance: Ссылка на главный экземпляр бота (опционально)
            cvd_threshold: Порог CVD в процентах (0.5% по умолчанию)
            volume_multiplier: Множитель объёма (1.5x по умолчанию)
            candle_check: Проверять ли паттерн свечи (False по умолчанию)
            min_large_trade_value: Минимальный размер large trade ($)
            adaptive_mode: Использовать адаптивные пороги CVD (True по умолчанию)
        """
        self.bot = bot_instance
        self.cvd_threshold = cvd_threshold
        self.volume_multiplier = volume_multiplier
        self.volume_threshold_multiplier = volume_multiplier  # Алиас для совместимости
        self.candle_check = candle_check
        self.require_candle_confirmation = candle_check  # Алиас для совместимости
        self.min_large_trade_value = min_large_trade_value
        self.adaptive_mode = adaptive_mode  # НОВОЕ

        logger.info(
            f"✅ ConfirmFilter инициализирован (CVD≥{cvd_threshold}%, "
            f"Vol≥{volume_multiplier}x, Candle={candle_check}, Adaptive={adaptive_mode})"
        )

    # ========== ОСНОВНОЙ МЕТОД ДЛЯ ИНТЕГРАЦИИ (ASYNC) ==========

    async def validate(
        self,
        symbol: str,
        direction: str,
        market_data: Optional[Dict] = None,
        signal_data: Optional[Dict] = None,
    ) -> bool:
        """
        Полная проверка сигнала перед генерацией (async версия)

        Args:
            symbol: Торговая пара (BTCUSDT)
            direction: Направление (LONG/SHORT)
            market_data: Рыночные данные (опционально, берутся из bot.market_data)
            signal_data: Данные сигнала (pattern, direction) для адаптивных порогов

        Returns:
            True если все проверки пройдены, False если нет
        """
        logger.info(f"🔍 Confirm Filter проверка для {symbol} {direction}")

        # ✅ ИНИЦИАЛИЗИРУЕМ АТРИБУТЫ ДЛЯ СОХРАНЕНИЯ
        self.last_cvd = 0.0
        self.last_volume_ratio = 0.0

        # ✅ ЕСЛИ НЕТ signal_data - СОЗДАЁМ БАЗОВЫЙ!
        if signal_data is None:
            signal_data = {
                "pattern": "Unknown",
                "direction": direction,
            }

        try:
            # Получаем market_data
            if market_data is None and self.bot:
                market_data = self.bot.market_data.get(symbol, {})
            elif market_data is None:
                logger.warning(f"⚠️ {symbol}: Нет market_data, пропускаем проверку")
                return True

            # 1. ПРОВЕРКА CVD (async) ← ТЕПЕРЬ signal_data ПЕРЕДАЁТСЯ!
            cvd_ok = await self._check_cvd_simple(
                symbol, direction, market_data, signal_data
            )
            if not cvd_ok:
                logger.warning(f"❌ {symbol}: CVD проверка не пройдена")
                return False

            # 2. ПРОВЕРКА ОБЪЁМА (async)
            volume_ok = await self._check_volume_simple(symbol, market_data)
            if not volume_ok:
                logger.warning(f"❌ {symbol}: Volume проверка не пройдена")
                return False

            # 3. ПРОВЕРКА СВЕЧИ (async)
            if self.candle_check:
                candle_ok = await self._check_candle_simple(
                    symbol, direction, market_data
                )
                if not candle_ok:
                    logger.warning(f"❌ {symbol}: Candle pattern не подтвердился")
                    return False

            logger.info(f"✅ {symbol}: ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ (CVD, Volume, Candle)")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка validate для {symbol}: {e}")
            return False  # При ошибке блокируем сигнал

    # ========== АЛЬТЕРНАТИВНЫЙ МЕТОД (ДЛЯ СОВМЕСТИМОСТИ) ==========

    async def validate_signal(
        self, signal: Dict, market_data: Dict, symbol: str
    ) -> Tuple[bool, str]:
        """
        Валидация сигнала через Confirm Filter (async версия)


        Args:
            signal: Сигнал для валидации
            market_data: Рыночные данные
            symbol: Торговая пара


        Returns:
            (is_valid, reason) - флаг валидности и причина
        """
        try:
            direction = signal.get("direction", "LONG")

            # Используем основной async метод validate
            is_valid = await self.validate(symbol, direction, market_data)

            if is_valid:
                return (True, "All confirmations passed")
            else:
                return (False, "One or more confirmations failed")

        except Exception as e:
            logger.error(f"❌ Ошибка validate_signal для {symbol}: {e}")
            return (False, f"Error: {e}")

    # ========== ПРОВЕРКИ CVD (ASYNC) ==========

    async def _check_cvd_simple(
        self, symbol: str, direction: str, market_data: Dict, signal_data: Dict = None
    ) -> bool:
        """Проверка CVD (async версия)"""
        try:
            # Вариант 1: Из orderbook (основной источник)
            orderbook = market_data.get("orderbook", {})
            imbalance = orderbook.get("imbalance", 0)

            # Вариант 2: Из orderbook_imbalance (WebSocket)
            if imbalance == 0:
                imbalance = market_data.get("orderbook_imbalance", 0)

            # Вариант 3: Рассчитываем из bid/ask volumes
            if imbalance == 0 and self.bot:
                imbalance = self._calculate_cvd_from_orderbook(symbol)

            # ✅ СОХРАНЯЕМ CVD (конвертируем в проценты если нужно)
            self.last_cvd = imbalance * 100 if abs(imbalance) < 1 else imbalance

            # Рассчитываем порог в долях (2% -> 0.02)
            threshold = self.cvd_threshold / 100

            # Проверка 1: Достаточная сила (абсолютное значение)
            abs_imbalance = abs(imbalance)
            logger.debug(
                f"   📊 {symbol} CVD: {imbalance:.1%} (abs: {abs_imbalance:.1%})"
            )

            if abs_imbalance < threshold:
                logger.debug(f"   ⚠️ CVD слабый: {abs_imbalance:.1%} < {threshold:.1%}")
                return False

            # Проверка 2: М'яка перевірка узгодженості напрямку
            # Используем адаптивный порог
            soft_threshold_pct = (
                self._get_adaptive_cvd_threshold(
                    signal_data.get("pattern", "Unknown"), direction
                )
                / 100
            )  # Конвертируем из % в доли (30% → 0.30)

            if direction == "LONG":
                if imbalance < -soft_threshold_pct:
                    # Якщо CVD ДУЖЕ негативний - блокуємо
                    logger.debug(
                        f"   ⚠️ LONG сигнал, але CVD дуже негативний "
                        f"({imbalance:.1%} < -{soft_threshold_pct:.1%})"
                    )
                    return False
                elif imbalance < 0:
                    # Якщо CVD помірно негативний - попередження але дозволяємо
                    logger.info(
                        f"   ⚡ LONG сигнал з помірно негативним CVD ({imbalance:.1%}), "
                        f"але в межах допуску ({-soft_threshold_pct:.1%})"
                    )
                else:
                    # CVD позитивний - ідеально!
                    logger.debug(f"   ✅ CVD підтримує LONG: {imbalance:.1%}")

            elif direction == "SHORT":
                if imbalance > soft_threshold_pct:
                    # Якщо CVD ДУЖЕ позитивний - блокуємо
                    logger.debug(
                        f"   ⚠️ SHORT сигнал, але CVD дуже позитивний "
                        f"({imbalance:.1%} > {soft_threshold_pct:.1%})"
                    )
                    return False
                elif imbalance > 0:
                    # Якщо CVD помірно позитивний - попередження але дозволяємо
                    logger.info(
                        f"   ⚡ SHORT сигнал з помірно позитивним CVD ({imbalance:.1%}), "
                        f"але в межах допуску ({soft_threshold_pct:.1%})"
                    )
                else:
                    # CVD негативний - ідеально!
                    logger.debug(f"   ✅ CVD підтримує SHORT: {imbalance:.1%}")

            logger.debug(f"   ✅ CVD перевірка OK: {imbalance:.1%}")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка _check_cvd_simple для {symbol}: {e}")
            return True  # При ошибке пропускаем проверку

    def _calculate_cvd_from_orderbook(self, symbol: str) -> float:
        """Расчёт CVD из L2 orderbook (sync)"""
        try:
            if not self.bot:
                return 0

            market_data = self.bot.market_data.get(symbol, {})

            # Получаем bid/ask volumes
            bid_volume = market_data.get("bid_volume", 0)
            ask_volume = market_data.get("ask_volume", 0)

            total_volume = bid_volume + ask_volume
            if total_volume == 0:
                return 0

            # CVD = (bid - ask) / total
            cvd = (bid_volume - ask_volume) / total_volume
            return cvd

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта CVD: {e}")
            return 0

    # ========== ПРОВЕРКИ ОБЪЁМА (ASYNC) ==========

    async def _check_volume_simple(self, symbol: str, market_data: Dict) -> bool:
        """Проверка объёма (async версия)"""
        try:
            # Вариант 1: Из market_data
            current_volume = market_data.get("volume_1m", 0)
            avg_volume = market_data.get("avg_volume_24h", 0)

            # Вариант 2: Из WebSocket данных
            if current_volume == 0:
                current_volume = market_data.get("volume", 0)

            # Вариант 3: Запросить через API (async)
            if current_volume == 0 and self.bot:
                current_volume = await self._get_current_volume(symbol)

            if avg_volume == 0 and self.bot:
                avg_volume = await self._get_average_volume(symbol, periods=20)

            if avg_volume == 0:
                logger.debug(f"   ⚠️ {symbol}: Средний объём = 0, пропускаем проверку")
                return True  # Пропускаем если нет данных

            volume_ratio = current_volume / avg_volume

            # ✅ СОХРАНЯЕМ VOLUME RATIO
            self.last_volume_ratio = volume_ratio

            logger.debug(
                f"   📊 {symbol} Volume: {current_volume:,.0f} / {avg_volume:,.0f} = {volume_ratio:.2f}x"
            )

            if volume_ratio < self.volume_multiplier:
                logger.debug(
                    f"   ⚠️ Volume {volume_ratio:.2f}x < порог {self.volume_multiplier}x"
                )
                return False

            logger.debug(f"   ✅ Volume проверка OK: {volume_ratio:.2f}x")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка _check_volume_simple для {symbol}: {e}")
            return True  # При ошибке пропускаем проверку

    async def _get_current_volume(self, symbol: str) -> float:
        """Получить текущий объём (async версия)"""
        try:
            if not self.bot:
                return 0

            # Из market_data (WebSocket) - быстрее
            market_data = self.bot.market_data.get(symbol, {})
            volume = market_data.get("volume", 0)

            if volume > 0:
                return float(volume)

            # ✅ Async fallback: запросить через API
            try:
                candles = await self.bot.bybit_connector.get_klines(symbol, "1", 1)

                if candles and len(candles) > 0:
                    return float(candles[-1].get("volume", 0))
            except Exception as e:
                logger.debug(f"   ⚠️ Ошибка получения volume через API: {e}")

            return 0

        except Exception as e:
            logger.error(f"❌ Ошибка _get_current_volume: {e}")
            return 0

    async def _get_average_volume(self, symbol: str, periods: int = 20) -> float:
        """Получить средний объём (async версия)"""
        try:
            if not self.bot:
                return 0

            # ✅ Async запрос через API
            candles = await self.bot.bybit_connector.get_klines(symbol, "1", periods)

            if not candles or len(candles) < periods:
                return 0

            volumes = [float(c.get("volume", 0)) for c in candles]
            avg = sum(volumes) / len(volumes)
            return avg

        except Exception as e:
            logger.error(f"❌ Ошибка _get_average_volume: {e}")
            return 0

    # ========== ПРОВЕРКИ СВЕЧИ (ASYNC) ==========

    async def _check_candle_simple(
        self, symbol: str, direction: str, market_data: Dict
    ) -> bool:
        """Проверка свечи (async версия)"""
        try:
            # Вариант 1: Из market_data
            last_candle = market_data.get("last_candle")

            if not last_candle and self.bot:
                # ✅ Async fallback: запросить через API
                try:
                    candles = await self.bot.bybit_connector.get_klines(symbol, "1", 2)

                    if candles and len(candles) >= 2:
                        last_candle = candles[-2]  # Последняя закрытая
                except Exception as e:
                    logger.debug(f"   ⚠️ Ошибка получения свечей через API: {e}")

            if not last_candle:
                logger.debug(f"   ⚠️ {symbol}: Нет данных свечей, пропускаем проверку")
                return True  # Пропускаем если нет данных

            # Анализируем свечу
            open_price = float(last_candle.get("open", 0))
            close_price = float(last_candle.get("close", 0))
            candle_body = close_price - open_price

            is_bullish = candle_body > 0
            is_bearish = candle_body < 0

            candle_type = (
                "🟢 Bullish"
                if is_bullish
                else ("🔴 Bearish" if is_bearish else "⚪ Doji")
            )
            logger.debug(f"   🕯️ {symbol} Свеча: {candle_type}")

            # Проверка соответствия направлению
            if direction == "LONG" and not is_bullish:
                logger.debug(f"   ⚠️ LONG сигнал, но свеча bearish")
                return False
            elif direction == "SHORT" and not is_bearish:
                logger.debug(f"   ⚠️ SHORT сигнал, но свеча bullish")
                return False

            logger.debug(f"   ✅ Candle проверка OK")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка _check_candle_simple для {symbol}: {e}")
            return True  # При ошибке пропускаем проверку

    # ========== ДОПОЛНИТЕЛЬНЫЕ ПРОВЕРКИ ==========

    async def _check_large_trades(
        self, signal: Dict, market_data: Dict, symbol: str
    ) -> Tuple[bool, str]:
        """Проверка крупных сделок (Large Trades)"""
        try:
            large_trades = market_data.get("large_trades", [])
            if not large_trades:
                return (False, "No large trades data")

            direction = signal.get("direction", "LONG")

            # Подсчитываем баланс BUY/SELL large trades
            buy_value = sum(
                t["value"]
                for t in large_trades
                if t.get("side") == "BUY"
                and t.get("value", 0) >= self.min_large_trade_value
            )
            sell_value = sum(
                t["value"]
                for t in large_trades
                if t.get("side") == "SELL"
                and t.get("value", 0) >= self.min_large_trade_value
            )

            if direction == "LONG" and buy_value > sell_value * 1.5:
                logger.info(
                    f"✅ {symbol}: Large trades поддерживают LONG "
                    f"(BUY: ${buy_value:,.0f} vs SELL: ${sell_value:,.0f})"
                )
                return (True, f"Large trades support LONG")
            elif direction == "SHORT" and sell_value > buy_value * 1.5:
                logger.info(
                    f"✅ {symbol}: Large trades поддерживают SHORT "
                    f"(SELL: ${sell_value:,.0f} vs BUY: ${buy_value:,.0f})"
                )
                return (True, f"Large trades support SHORT")
            else:
                return (False, "Large trades neutral or conflicting")

        except Exception as e:
            logger.error(f"❌ Ошибка _check_large_trades: {e}")
            return (False, "Large trades check error")

    def _get_adaptive_cvd_threshold(self, scenario: str, direction: str) -> float:
        """
        Адаптивный порог CVD в зависимости от сценария

        Args:
            scenario: Название сценария (Impulse, Reversal, Range и т.д.)
            direction: Направление сигнала (LONG/SHORT)

        Returns:
            float: Адаптивный порог CVD в процентах (например, -30.0 для LONG)
        """

        if not self.adaptive_mode:
            # Если адаптивный режим выключен, возвращаем стандартный порог
            return 30.0  # Стандартный порог 30%

        # Нормализуем название сценария
        scenario_upper = scenario.upper()

        # Для разворотных стратегий - более мягкий порог
        if any(x in scenario_upper for x in ["REVERSAL", "COUNTER", "DEAL_REVERSAL"]):
            threshold = 50.0  # 50% допуск для разворотов
            logger.debug(
                f"   🔄 Адаптивный CVD порог для {scenario}: ±{threshold}% (Reversal)"
            )
            return threshold

        # Для импульсных - более строгий
        elif any(x in scenario_upper for x in ["IMPULSE", "BREAKOUT", "DEAL"]):
            threshold = 10.0  # 10% допуск для импульсов
            logger.debug(
                f"   ⚡ Адаптивный CVD порог для {scenario}: ±{threshold}% (Impulse)"
            )
            return threshold

        # Для Range - средний
        elif any(x in scenario_upper for x in ["RANGE", "CONSOLIDATION"]):
            threshold = 30.0  # 30% допуск для range
            logger.debug(
                f"   ↔️ Адаптивный CVD порог для {scenario}: ±{threshold}% (Range)"
            )
            return threshold

        # Для Squeeze - учитываем ликвидации
        elif any(x in scenario_upper for x in ["SQUEEZE", "LIQUIDATION"]):
            threshold = 40.0  # 40% допуск для squeeze
            logger.debug(
                f"   💥 Адаптивный CVD порог для {scenario}: ±{threshold}% (Squeeze)"
            )
            return threshold

        # По умолчанию
        threshold = 30.0
        logger.debug(
            f"   📊 Адаптивный CVD порог для {scenario}: ±{threshold}% (Default)"
        )
        return threshold


# Экспорт
__all__ = ["ConfirmFilter"]
