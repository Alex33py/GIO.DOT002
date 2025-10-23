#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Confirm Filter - Фильтр подтверждения сигналов БЕЗ БЛОКИРОВКИ
Проверяет CVD, объём и паттерн свечи, возвращает penalties вместо False
"""

import time
import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from config.settings import logger


class ConfirmFilter:
    """
    Фильтр подтверждения торговых сигналов (NON-BLOCKING)

    Проверяет 3 критерия:
    1. CVD (Cumulative Volume Delta)
    2. Volume ≥ 1.5x среднего
    3. Candle pattern (опционально)

    НЕ БЛОКИРУЕТ сигналы - только добавляет penalties и warnings
    """

    def __init__(
        self,
        bot_instance=None,
        cvd_threshold: float = 0.5,
        volume_multiplier: float = 1.5,
        candle_check: bool = False,
        min_large_trade_value: float = 10000,
        adaptive_mode: bool = True,
    ):
        """Инициализация фильтра"""
        self.bot = bot_instance
        self.cvd_threshold = cvd_threshold
        self.volume_multiplier = volume_multiplier
        self.volume_threshold_multiplier = volume_multiplier
        self.candle_check = candle_check
        self.require_candle_confirmation = candle_check
        self.min_large_trade_value = min_large_trade_value
        self.adaptive_mode = adaptive_mode

        # Для сохранения последних значений
        self.last_cvd = 0.0
        self.last_volume_ratio = 0.0

        logger.info(
            f"✅ ConfirmFilter инициализирован (CVD≥{cvd_threshold}%, "
            f"Vol≥{volume_multiplier}x, Candle={candle_check}, Adaptive={adaptive_mode}, NON-BLOCKING)"
        )

    # ========== ОСНОВНОЙ МЕТОД (ВОЗВРАЩАЕТ DICT!) ==========

    async def validate(
        self,
        symbol: str,
        direction: str,
        market_data: Optional[Dict] = None,
        signal_data: Optional[Dict] = None,
    ) -> Dict:
        """
        Полная проверка сигнала БЕЗ БЛОКИРОВКИ

        Returns:
            Dict: {
                'passed': True,  # ВСЕГДА True
                'confidence_penalty': int,  # 0-30
                'warnings': List[str],
                'cvd_check': Dict,
                'volume_check': Dict,
                'candle_check': Dict
            }
        """
        logger.info(f"🔍 Confirm Filter проверка для {symbol} {direction}")

        result = {
            'passed': True,  # ВСЕГДА True
            'confidence_penalty': 0,
            'warnings': [],
            'cvd_check': {},
            'volume_check': {},
            'candle_check': {}
        }

        try:
            # Получаем market_data
            if market_data is None and self.bot:
                market_data = self.bot.market_data.get(symbol, {})
            elif market_data is None:
                logger.warning(f"⚠️ {symbol}: Нет market_data, пропускаем проверку")
                result['warnings'].append("⚠️ Нет market_data")
                result['confidence_penalty'] += 20
                return result

            # signal_data по умолчанию
            if signal_data is None:
                signal_data = {
                    "pattern": "Unknown",
                    "direction": direction,
                }

            # 1. ПРОВЕРКА CVD
            cvd_confirmed, cvd_value, cvd_warning = await self._check_cvd_simple(
                symbol, direction, market_data, signal_data
            )

            result['cvd_check'] = {
                'value': cvd_value,
                'confirmed': cvd_confirmed,
                'warning': cvd_warning
            }

            if not cvd_confirmed:
                result['confidence_penalty'] += 15
                result['warnings'].append(cvd_warning)
                logger.warning(f"⚠️ {symbol}: {cvd_warning}")
            else:
                logger.info(f"✅ {symbol}: CVD OK ({cvd_value:.1f}%)")

            # 2. ПРОВЕРКА ОБЪЁМА
            volume_confirmed, volume_ratio, volume_warning = await self._check_volume_simple(
                symbol, market_data
            )

            result['volume_check'] = {
                'value': volume_ratio,
                'confirmed': volume_confirmed,
                'warning': volume_warning
            }

            if not volume_confirmed:
                result['confidence_penalty'] += 10
                result['warnings'].append(volume_warning)
                logger.warning(f"⚠️ {symbol}: {volume_warning}")
            else:
                logger.info(f"✅ {symbol}: Volume OK ({volume_ratio:.2f}x)")

            # 3. ПРОВЕРКА СВЕЧИ (опционально)
            if self.candle_check:
                candle_confirmed, candle_pattern, candle_warning = await self._check_candle_simple(
                    symbol, direction, market_data
                )

                result['candle_check'] = {
                    'pattern': candle_pattern,
                    'confirmed': candle_confirmed,
                    'warning': candle_warning
                }

                if not candle_confirmed and candle_warning:
                    result['confidence_penalty'] += 5
                    result['warnings'].append(candle_warning)
                    logger.warning(f"⚠️ {symbol}: {candle_warning}")

            # Summary
            total_penalty = result['confidence_penalty']
            if total_penalty == 0:
                logger.info(f"✅ {symbol}: ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ")
            elif total_penalty <= 15:
                logger.info(f"⚠️ {symbol}: Минимальные warnings, penalty: -{total_penalty}%")
            else:
                logger.warning(f"⚠️⚠️ {symbol}: Множественные warnings, penalty: -{total_penalty}%")

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка validate для {symbol}: {e}")
            return {
                'passed': True,
                'confidence_penalty': 20,
                'warnings': [f"❌ Validation error: {str(e)}"],
                'cvd_check': {},
                'volume_check': {},
                'candle_check': {}
            }

    # ========== ПРОВЕРКИ CVD (ВОЗВРАЩАЕТ TUPLE!) ==========

    async def _check_cvd_simple(
        self, symbol: str, direction: str, market_data: Dict, signal_data: Dict
    ) -> Tuple[bool, float, str]:
        """
        Проверяет CVD с адаптивными порогами

        Returns:
            (is_confirmed: bool, cvd_value: float, warning: str)
        """
        try:
            # Получаем scenario
            scenario = signal_data.get("pattern", "Unknown")

            # Адаптивный порог
            cvd_threshold = self._get_adaptive_cvd_threshold(scenario, direction)

            # Получаем CVD от коннекторов
            cvd_okx = None
            cvd_bybit = None

            if hasattr(self.bot, "okx") and self.bot.okx:
                cvd_okx = self.bot.okx.get_cvd_percentage(symbol)

            if hasattr(self.bot, "bybit") and self.bot.bybit:
                cvd_bybit = self.bot.bybit.get_cvd_percentage(symbol)

            cvd = cvd_okx if cvd_okx is not None else cvd_bybit

            if cvd is None:
                logger.warning(f"⚠️ CVD недоступен для {symbol}")
                return (True, 0, "")  # Пропускаем если нет данных

            # Сохраняем CVD
            self.last_cvd = cvd

            logger.debug(f"   📊 {symbol} CVD: {cvd:.1f}% (порог: ±{cvd_threshold}%)")

            # Проверка направления CVD
            if direction == "LONG":
                if cvd < -cvd_threshold:
                    return (False, cvd, f"⚠️ CVD против LONG: {cvd:.1f}% < -{cvd_threshold}%")
                elif abs(cvd) < cvd_threshold * 0.3:
                    return (False, cvd, f"⚠️ CVD слабый: {cvd:.1f}% (порог {cvd_threshold}%)")
                else:
                    return (True, cvd, "")

            elif direction == "SHORT":
                if cvd > cvd_threshold:
                    return (False, cvd, f"⚠️ CVD против SHORT: {cvd:.1f}% > {cvd_threshold}%")
                elif abs(cvd) < cvd_threshold * 0.3:
                    return (False, cvd, f"⚠️ CVD слабый: {cvd:.1f}% (порог {cvd_threshold}%)")
                else:
                    return (True, cvd, "")

            else:
                return (False, cvd, "⚠️ Неизвестное направление")

        except Exception as e:
            logger.error(f"❌ Ошибка проверки CVD для {symbol}: {e}")
            return (True, 0, "")  # Пропускаем при ошибке

    # ========== ПРОВЕРКИ ОБЪЁМА (ВОЗВРАЩАЕТ TUPLE!) ==========

    async def _check_volume_simple(
        self, symbol: str, market_data: Dict
    ) -> Tuple[bool, float, str]:
        """
        Проверка объёма

        Returns:
            (is_confirmed: bool, volume_ratio: float, warning: str)
        """
        try:
            current_volume = market_data.get("volume_1m", 0)
            avg_volume = market_data.get("avg_volume_24h", 0)

            if current_volume == 0:
                current_volume = market_data.get("volume", 0)

            # Async fallback
            if current_volume == 0 and self.bot:
                current_volume = await self._get_current_volume(symbol)

            if avg_volume == 0 and self.bot:
                avg_volume = await self._get_average_volume(symbol, periods=20)

            if avg_volume == 0:
                logger.debug(f"   ⚠️ {symbol}: Средний объём = 0, пропускаем проверку")
                return (True, 0, "")

            volume_ratio = current_volume / avg_volume

            # Сохраняем
            self.last_volume_ratio = volume_ratio

            logger.debug(
                f"   📊 {symbol} Volume: {current_volume:,.0f} / {avg_volume:,.0f} = {volume_ratio:.2f}x"
            )

            if volume_ratio < 0.5:
                return (False, volume_ratio, f"⚠️ Volume очень низкий: {volume_ratio:.2f}x")
            elif volume_ratio < self.volume_multiplier:
                return (False, volume_ratio, f"⚠️ Volume ниже порога: {volume_ratio:.2f}x < {self.volume_multiplier}x")
            else:
                return (True, volume_ratio, "")

        except Exception as e:
            logger.error(f"❌ Ошибка _check_volume_simple для {symbol}: {e}")
            return (True, 0, "")

    async def _get_current_volume(self, symbol: str) -> float:
        """Получить текущий объём"""
        try:
            if not self.bot:
                return 0

            market_data = self.bot.market_data.get(symbol, {})
            volume = market_data.get("volume", 0)

            if volume > 0:
                return float(volume)

            # Async API fallback
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
        """Получить средний объём"""
        try:
            if not self.bot:
                return 0

            candles = await self.bot.bybit_connector.get_klines(symbol, "1", periods)

            if not candles or len(candles) < periods:
                return 0

            volumes = [float(c.get("volume", 0)) for c in candles]
            avg = sum(volumes) / len(volumes)
            return avg

        except Exception as e:
            logger.error(f"❌ Ошибка _get_average_volume: {e}")
            return 0

    # ========== ПРОВЕРКИ СВЕЧИ (ВОЗВРАЩАЕТ TUPLE!) ==========

    async def _check_candle_simple(
        self, symbol: str, direction: str, market_data: Dict
    ) -> Tuple[bool, str, str]:
        """
        Проверка свечи

        Returns:
            (is_confirmed: bool, pattern: str, warning: str)
        """
        try:
            last_candle = market_data.get("last_candle")

            if not last_candle and self.bot:
                try:
                    candles = await self.bot.bybit_connector.get_klines(symbol, "1", 2)
                    if candles and len(candles) >= 2:
                        last_candle = candles[-2]
                except Exception as e:
                    logger.debug(f"   ⚠️ Ошибка получения свечей через API: {e}")

            if not last_candle:
                logger.debug(f"   ⚠️ {symbol}: Нет данных свечей, пропускаем проверку")
                return (True, "UNKNOWN", "")

            open_price = float(last_candle.get("open", 0))
            close_price = float(last_candle.get("close", 0))
            candle_body = close_price - open_price

            is_bullish = candle_body > 0
            is_bearish = candle_body < 0

            candle_type = (
                "BULLISH" if is_bullish else ("BEARISH" if is_bearish else "DOJI")
            )

            logger.debug(f"   🕯️ {symbol} Свеча: {candle_type}")

            # Проверка соответствия
            if direction == "LONG" and not is_bullish:
                return (False, candle_type, f"⚠️ LONG сигнал, но свеча bearish")
            elif direction == "SHORT" and not is_bearish:
                return (False, candle_type, f"⚠️ SHORT сигнал, но свеча bullish")
            else:
                return (True, candle_type, "")

        except Exception as e:
            logger.error(f"❌ Ошибка _check_candle_simple для {symbol}: {e}")
            return (True, "ERROR", "")

    # ========== АДАПТИВНЫЕ ПОРОГИ CVD ==========

    def _get_adaptive_cvd_threshold(self, scenario: str, direction: str) -> float:
        """Адаптивный порог CVD в зависимости от сценария"""
        if not self.adaptive_mode:
            return 30.0

        scenario_upper = scenario.upper()

        # Разворотные стратегии
        if any(x in scenario_upper for x in ["REVERSAL", "COUNTER", "DEAL_REVERSAL"]):
            threshold = 50.0
            logger.debug(f"   🔄 Адаптивный CVD порог для {scenario}: ±{threshold}% (Reversal)")
            return threshold

        # Импульсные
        elif any(x in scenario_upper for x in ["IMPULSE", "BREAKOUT", "DEAL"]):
            threshold = 10.0
            logger.debug(f"   ⚡ Адаптивный CVD порог для {scenario}: ±{threshold}% (Impulse)")
            return threshold

        # Range
        elif any(x in scenario_upper for x in ["RANGE", "CONSOLIDATION"]):
            threshold = 30.0
            logger.debug(f"   ↔️ Адаптивный CVD порог для {scenario}: ±{threshold}% (Range)")
            return threshold

        # Squeeze
        elif any(x in scenario_upper for x in ["SQUEEZE", "LIQUIDATION"]):
            threshold = 40.0
            logger.debug(f"   💥 Адаптивный CVД порог для {scenario}: ±{threshold}% (Squeeze)")
            return threshold

        # Default
        threshold = 30.0
        logger.debug(f"   📊 Адаптивный CVD порог для {scenario}: ±{threshold}% (Default)")
        return threshold

    # ========== АЛЬТЕРНАТИВНЫЙ МЕТОД (ДЛЯ СОВМЕСТИМОСТИ) ==========

    async def validate_signal(
        self, signal: Dict, market_data: Dict, symbol: str
    ) -> Tuple[bool, str]:
        """
        Валидация сигнала (старая версия для совместимости)

        Returns:
            (is_valid, reason)
        """
        try:
            direction = signal.get("direction", "LONG")

            result = await self.validate(symbol, direction, market_data, signal)

            if result['passed']:
                penalty = result['confidence_penalty']
                warnings_str = "; ".join(result['warnings']) if result['warnings'] else "All OK"
                return (True, f"Confirmed (penalty: -{penalty}%): {warnings_str}")
            else:
                return (False, "Validation failed")

        except Exception as e:
            logger.error(f"❌ Ошибка validate_signal для {symbol}: {e}")
            return (False, f"Error: {e}")


# Экспорт
__all__ = ["ConfirmFilter"]
