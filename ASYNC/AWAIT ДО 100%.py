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
        cvd_threshold: float = 60.0,
        volume_multiplier: float = 1.5,
        candle_check: bool = True,
        min_large_trade_value: float = 10000
    ):
        """
        Инициализация фильтра


        Args:
            bot_instance: Ссылка на главный экземпляр бота (опционально)
            cvd_threshold: Порог CVD в процентах (60% по умолчанию)
            volume_multiplier: Множитель объёма (1.5x по умолчанию)
            candle_check: Проверять ли паттерн свечи (True по умолчанию)
            min_large_trade_value: Минимальный размер large trade ($)
        """
        self.bot = bot_instance
        self.cvd_threshold = cvd_threshold
        self.volume_multiplier = volume_multiplier
        self.volume_threshold_multiplier = volume_multiplier  # Алиас для совместимости
        self.candle_check = candle_check
        self.require_candle_confirmation = candle_check  # Алиас для совместимости
        self.min_large_trade_value = min_large_trade_value


        logger.info(
            f"✅ ConfirmFilter инициализирован (CVD≥{cvd_threshold}%, "
            f"Vol≥{volume_multiplier}x, Candle={candle_check})"
        )


    # ========== ОСНОВНОЙ МЕТОД ДЛЯ ИНТЕГРАЦИИ (ASYNC) ==========


    async def validate(self, symbol: str, direction: str, market_data: Optional[Dict] = None) -> bool:
        """
        Полная проверка сигнала перед генерацией (async версия)


        Args:
            symbol: Торговая пара (BTCUSDT)
            direction: Направление (LONG/SHORT)
            market_data: Рыночные данные (опционально, берутся из bot.market_data)


        Returns:
            True если все проверки пройдены, False если нет
        """
        logger.info(f"🔍 Confirm Filter проверка для {symbol} {direction}")


        try:
            # Получаем market_data
            if market_data is None and self.bot:
                market_data = self.bot.market_data.get(symbol, {})
            elif market_data is None:
                logger.warning(f"⚠️ {symbol}: Нет market_data, пропускаем проверку")
                return True


            # 1. ПРОВЕРКА CVD (async)
            cvd_ok = await self._check_cvd_simple(symbol, direction, market_data)
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
                candle_ok = await self._check_candle_simple(symbol, direction, market_data)
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


    async def _check_cvd_simple(self, symbol: str, direction: str, market_data: Dict) -> bool:
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


            # Рассчитываем порог в долях (60% -> 0.6)
            threshold = self.cvd_threshold / 100


            # Проверка 1: Достаточная сила (абсолютное значение)
            abs_imbalance = abs(imbalance)
            logger.debug(f"   📊 {symbol} CVD: {imbalance:.1%} (abs: {abs_imbalance:.1%})")


            if abs_imbalance < threshold:
                logger.debug(f"   ⚠️ CVD слабый: {abs_imbalance:.1%} < {threshold:.1%}")
                return False


            # Проверка 2: Согласованность направления
            if direction == "LONG" and imbalance < 0:
                logger.debug(f"   ⚠️ LONG сигнал, но CVD отрицательный ({imbalance:.1%})")
                return False
            elif direction == "SHORT" and imbalance > 0:
                logger.debug(f"   ⚠️ SHORT сигнал, но CVD положительный ({imbalance:.1%})")
                return False


            logger.debug(f"   ✅ CVD проверка OK: {imbalance:.1%} (направление согласовано)")
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
            logger.debug(f"   📊 {symbol} Volume: {current_volume:,.0f} / {avg_volume:,.0f} = {volume_ratio:.2f}x")


            if volume_ratio < self.volume_multiplier:
                logger.debug(f"   ⚠️ Volume {volume_ratio:.2f}x < порог {self.volume_multiplier}x")
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


    async def _check_candle_simple(self, symbol: str, direction: str, market_data: Dict) -> bool:
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


            candle_type = "🟢 Bullish" if is_bullish else ("🔴 Bearish" if is_bearish else "⚪ Doji")
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
                if t.get("side") == "BUY" and t.get("value", 0) >= self.min_large_trade_value
            )
            sell_value = sum(
                t["value"]
                for t in large_trades
                if t.get("side") == "SELL" and t.get("value", 0) >= self.min_large_trade_value
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



# Экспорт
__all__ = ["ConfirmFilter"]



1111111111111111111111111111111111111111111

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
        cvd_threshold: float = 60.0,
        volume_multiplier: float = 1.5,
        candle_check: bool = True,
        min_large_trade_value: float = 10000
    ):
        """
        Инициализация фильтра

        Args:
            bot_instance: Ссылка на главный экземпляр бота (опционально)
            cvd_threshold: Порог CVD в процентах (60% по умолчанию)
            volume_multiplier: Множитель объёма (1.5x по умолчанию)
            candle_check: Проверять ли паттерн свечи (True по умолчанию)
            min_large_trade_value: Минимальный размер large trade ($)
        """
        self.bot = bot_instance
        self.cvd_threshold = cvd_threshold
        self.volume_multiplier = volume_multiplier
        self.volume_threshold_multiplier = volume_multiplier  # Алиас для совместимости
        self.candle_check = candle_check
        self.require_candle_confirmation = candle_check  # Алиас для совместимости
        self.min_large_trade_value = min_large_trade_value

        logger.info(
            f"✅ ConfirmFilter инициализирован (CVD≥{cvd_threshold}%, "
            f"Vol≥{volume_multiplier}x, Candle={candle_check})"
        )

    # ========== ОСНОВНОЙ МЕТОД ДЛЯ ИНТЕГРАЦИИ ==========

    def validate(self, symbol: str, direction: str, market_data: Optional[Dict] = None) -> bool:
        """
        Полная проверка сигнала перед генерацией

        Args:
            symbol: Торговая пара (BTCUSDT)
            direction: Направление (LONG/SHORT)
            market_data: Рыночные данные (опционально, берутся из bot.market_data)

        Returns:
            True если все проверки пройдены, False если нет
        """
        logger.info(f"🔍 Confirm Filter проверка для {symbol} {direction}")

        try:
            # Получаем market_data
            if market_data is None and self.bot:
                market_data = self.bot.market_data.get(symbol, {})
            elif market_data is None:
                logger.warning(f"⚠️ {symbol}: Нет market_data, пропускаем проверку")
                return True

            # 1. ПРОВЕРКА CVD
            cvd_ok = self._check_cvd_simple(symbol, direction, market_data)
            if not cvd_ok:
                logger.warning(f"❌ {symbol}: CVD проверка не пройдена")
                return False

            # 2. ПРОВЕРКА ОБЪЁМА
            volume_ok = self._check_volume_simple(symbol, market_data)
            if not volume_ok:
                logger.warning(f"❌ {symbol}: Volume проверка не пройдена")
                return False

            # 3. ПРОВЕРКА СВЕЧИ
            if self.candle_check:
                candle_ok = self._check_candle_simple(symbol, direction, market_data)
                if not candle_ok:
                    logger.warning(f"❌ {symbol}: Candle pattern не подтвердился")
                    return False

            logger.info(f"✅ {symbol}: ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ (CVD, Volume, Candle)")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка validate для {symbol}: {e}")
            return False  # При ошибке блокируем сигнал

    # ========== АЛЬТЕРНАТИВНЫЙ МЕТОД (ДЛЯ СОВМЕСТИМОСТИ) ==========

    def validate_signal(
        self, signal: Dict, market_data: Dict, symbol: str
    ) -> Tuple[bool, str]:
        """
        Валидация сигнала через Confirm Filter (альтернативный интерфейс)

        Args:
            signal: Сигнал для валидации
            market_data: Рыночные данные
            symbol: Торговая пара

        Returns:
            (is_valid, reason) - флаг валидности и причина
        """
        try:
            direction = signal.get("direction", "LONG")

            # Используем основной метод validate
            is_valid = self.validate(symbol, direction, market_data)

            if is_valid:
                return (True, "All confirmations passed")
            else:
                return (False, "One or more confirmations failed")

        except Exception as e:
            logger.error(f"❌ Ошибка validate_signal для {symbol}: {e}")
            return (False, f"Error: {e}")

    # ========== ПРОВЕРКИ CVD ==========

    def _check_cvd_simple(self, symbol: str, direction: str, market_data: Dict) -> bool:
        """Проверка CVD (упрощённая версия)"""
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

            # Рассчитываем порог в долях (60% -> 0.6)
            threshold = self.cvd_threshold / 100  # 0.6

            # Проверка 1: Достаточная сила (абсолютное значение)
            abs_imbalance = abs(imbalance)
            logger.debug(f"   📊 {symbol} CVD: {imbalance:.1%} (abs: {abs_imbalance:.1%})")

            if abs_imbalance < threshold:
                logger.debug(f"   ⚠️ CVD слабый: {abs_imbalance:.1%} < {threshold:.1%}")
                return False

            # Проверка направления (важно!)
            if direction == "LONG" and imbalance < 0:
                logger.debug(f"   ⚠️ LONG сигнал, но CVD отрицательный ({imbalance:.1%})")
                return False
            elif direction == "SHORT" and imbalance > 0:
                logger.debug(f"   ⚠️ SHORT сигнал, но CVD положительный ({imbalance:.1%})")
                return False

            logger.debug(f"   ✅ CVD проверка OK: {imbalance:.1%} (направление согласовано)")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка _check_cvd_simple для {symbol}: {e}")
            return True  # При ошибке пропускаем проверку

    def _calculate_cvd_from_orderbook(self, symbol: str) -> float:
        """Расчёт CVD из L2 orderbook"""
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

    # ========== ПРОВЕРКИ ОБЪЁМА ==========

    def _check_volume_simple(self, symbol: str, market_data: Dict) -> bool:
        """Проверка объёма (упрощённая версия)"""
        try:
            # Вариант 1: Из market_data
            current_volume = market_data.get("volume_1m", 0)
            avg_volume = market_data.get("avg_volume_24h", 0)

            # Вариант 2: Из WebSocket данных
            if current_volume == 0:
                current_volume = market_data.get("volume", 0)

            # Вариант 3: Запросить через API
            if current_volume == 0 and self.bot:
                current_volume = self._get_current_volume(symbol)

            if avg_volume == 0 and self.bot:
                avg_volume = self._get_average_volume(symbol, periods=20)

            if avg_volume == 0:
                logger.debug(f"   ⚠️ {symbol}: Средний объём = 0, пропускаем проверку")
                return True  # Пропускаем если нет данных

            volume_ratio = current_volume / avg_volume
            logger.debug(f"   📊 {symbol} Volume: {current_volume:,.0f} / {avg_volume:,.0f} = {volume_ratio:.2f}x")

            if volume_ratio < self.volume_multiplier:
                logger.debug(f"   ⚠️ Volume {volume_ratio:.2f}x < порог {self.volume_multiplier}x")
                return False

            logger.debug(f"   ✅ Volume проверка OK: {volume_ratio:.2f}x")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка _check_volume_simple для {symbol}: {e}")
            return True  # При ошибке пропускаем проверку

    def _get_current_volume(self, symbol: str) -> float:
        """Получить текущий объём (1m свеча)"""
        try:
            if not self.bot:
                return 0

            # Из market_data (WebSocket) - быстрее
            market_data = self.bot.market_data.get(symbol, {})
            volume = market_data.get("volume", 0)

            if volume > 0:
                return float(volume)

            # Fallback: Запросить последнюю свечу через API
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    future = asyncio.ensure_future(
                        self.bot.bybit_connector.get_klines(symbol, "1", 1)
                    )
                    candles = loop.run_until_complete(future)
                else:
                    candles = asyncio.run(
                        self.bot.bybit_connector.get_klines(symbol, "1", 1)
                    )

                if candles and len(candles) > 0:
                    return float(candles[-1].get("volume", 0))
            except:
                pass

            return 0

        except Exception as e:
            logger.error(f"❌ Ошибка _get_current_volume: {e}")
            return 0

    def _get_average_volume(self, symbol: str, periods: int = 20) -> float:
        """Получить средний объём за N периодов"""
        try:
            if not self.bot:
                return 0

            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.ensure_future(
                    self.bot.bybit_connector.get_klines(symbol, "1", periods)
                )
                candles = loop.run_until_complete(future)
            else:
                candles = asyncio.run(
                    self.bot.bybit_connector.get_klines(symbol, "1", periods)
                )

            if not candles or len(candles) < periods:
                return 0

            volumes = [float(c.get("volume", 0)) for c in candles]
            avg = sum(volumes) / len(volumes)
            return avg

        except Exception as e:
            logger.error(f"❌ Ошибка _get_average_volume: {e}")
            return 0

    # ========== ПРОВЕРКИ СВЕЧИ ==========

    def _check_candle_simple(self, symbol: str, direction: str, market_data: Dict) -> bool:
        """Проверка свечи (упрощённая версия)"""
        try:
            # Вариант 1: Из market_data
            last_candle = market_data.get("last_candle")

            if not last_candle and self.bot:
                # Вариант 2: Запросить через API
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        future = asyncio.ensure_future(
                            self.bot.bybit_connector.get_klines(symbol, "1", 2)
                        )
                        candles = loop.run_until_complete(future)
                    else:
                        candles = asyncio.run(
                            self.bot.bybit_connector.get_klines(symbol, "1", 2)
                        )

                    if candles and len(candles) >= 2:
                        last_candle = candles[-2]  # Последняя закрытая
                except:
                    pass

            if not last_candle:
                logger.debug(f"   ⚠️ {symbol}: Нет данных свечей, пропускаем проверку")
                return True  # Пропускаем если нет данных

            # Анализируем свечу
            open_price = float(last_candle.get("open", 0))
            close_price = float(last_candle.get("close", 0))
            candle_body = close_price - open_price

            is_bullish = candle_body > 0
            is_bearish = candle_body < 0

            candle_type = "🟢 Bullish" if is_bullish else ("🔴 Bearish" if is_bearish else "⚪ Doji")
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

    def _check_large_trades(
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
                if t.get("side") == "BUY" and t.get("value", 0) >= self.min_large_trade_value
            )
            sell_value = sum(
                t["value"]
                for t in large_trades
                if t.get("side") == "SELL" and t.get("value", 0) >= self.min_large_trade_value
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


# Экспорт
__all__ = ["ConfirmFilter"]
