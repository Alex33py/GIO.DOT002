#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Auto Scanner - Автоматический сканер рынка (каждые 5 минут)
Объединённая версия с поддержкой UnifiedScenarioMatcher + ВАЛИДАЦИЯ ДАННЫХ
"""

import asyncio
import time
from typing import Optional, List, Dict
from datetime import datetime
from config.settings import logger, TRACKED_SYMBOLS, SCANNER_CONFIG
from utils.data_validator import DataValidator  # ← ДОБАВЛЕНО!


class UnifiedAutoScanner:
    """Унифицированный автосканер для поиска торговых возможностей"""

    def __init__(
        self,
        bot_instance,
        bybit_connector,
        binance_connector,
        indicator_calculator,
        signal_generator,
        telegram_handler,
        signal_recorder=None,
        scenario_matcher=None,
        sentiment_analyzer=None,
        veto_system=None,
        interval: int = 300,
    ):
        """
        Инициализация автосканера

        Args:
            bot_instance: Экземпляр основного бота
            bybit_connector: Bybit API коннектор
            binance_connector: Binance API коннектор
            indicator_calculator: Калькулятор индикаторов
            signal_generator: Генератор сигналов
            telegram_handler: Telegram бот handler
            signal_recorder: Рекордер сигналов (опционально)
            scenario_matcher: UnifiedScenarioMatcher (опционально)
            sentiment_analyzer: Анализатор сентимента (опционально)
            veto_system: Система вето (опционально)
            interval: Интервал сканирования в секундах (по умолчанию 300 = 5 мин)
        """
        self.bot = bot_instance
        self.bybit_connector = bybit_connector
        self.binance_connector = binance_connector
        self.indicator_calculator = indicator_calculator
        self.signal_generator = signal_generator
        self.telegram_handler = telegram_handler
        self.signal_recorder = signal_recorder
        self.scenario_matcher = scenario_matcher
        self.sentiment_analyzer = sentiment_analyzer
        self.veto_system = veto_system

        # Настройки
        self.interval_minutes = interval // 60  # Конвертируем секунды в минуты
        self.symbols = TRACKED_SYMBOLS
        self.is_running = False
        self.scan_task = None

        # ✅ АНТИ-СПАМ НАСТРОЙКИ
        self.last_signal_time = {}  # {"BTCUSDT": timestamp}
        self.signal_cooldown = 1800  # 30 минут между сигналами
        self.signals_per_hour = []  # [timestamp1, timestamp2, ...]
        self.max_signals_per_hour = 10  # Максимум 10 сигналов в час
        self.max_active_positions_per_symbol = 2  # Макс. позиций по символу

        logger.info(
            f"✅ UnifiedAutoScanner инициализирован (интервал: {self.interval_minutes} мин)"
        )

    async def start(self):
        """Запуск автосканера"""
        if self.is_running:
            logger.warning("⚠️ AutoScanner уже запущен")
            return

        self.is_running = True
        logger.info(f"🔍 Запуск AutoScanner (интервал: {self.interval_minutes} мин)")

        # Запускаем цикл сканирования
        self.scan_task = asyncio.create_task(self._scan_loop())

    async def stop(self):
        """Остановка автосканера"""
        if not self.is_running:
            return

        logger.info("🛑 Остановка AutoScanner...")
        self.is_running = False

        if self.scan_task:
            self.scan_task.cancel()
            try:
                await self.scan_task
            except asyncio.CancelledError:
                pass

        logger.info("✅ AutoScanner остановлен")

    async def _scan_loop(self):
        """Главный цикл сканирования"""
        try:
            while self.is_running:
                try:
                    # Выполняем сканирование
                    await self.scan_market()
                    await asyncio.sleep(self.interval_minutes * 60)

                except Exception as e:
                    logger.error(f"❌ Ошибка в цикле сканирования: {e}")
                    # Продолжаем работу даже при ошибке
                    await asyncio.sleep(60)  # Пауза 1 минута при ошибке

        except asyncio.CancelledError:
            logger.info("🛑 Цикл сканирования отменён")

    async def scan_market(self):
        """Сканирование рынка на всех символах"""
        try:
            now = time.time()
            hour_ago = now - 3600
            self.signals_per_hour = [t for t in self.signals_per_hour if t > hour_ago]

            if len(self.signals_per_hour) >= self.max_signals_per_hour:
                logger.warning(
                    f"⚠️ Лимит сигналов достигнут: {self.max_signals_per_hour}/час"
                )
                return
            logger.info(f"🔍 Начало сканирования рынка ({len(self.symbols)} символов)")

            signals_found = 0

            for symbol in self.symbols:
                try:
                    # Анализируем символ
                    result = await self.analyze_symbol(symbol)

                    if result and result.get("signal"):
                        signals_found += 1
                        logger.info(f"🎯 Найден сигнал: {symbol} {result['direction']}")

                        # Сохраняем сигнал если есть recorder
                        if self.signal_recorder:
                            signal_id = self.signal_recorder.record_signal(
                                symbol=symbol,
                                direction=result["direction"],
                                entry_price=result["entry_price"],
                                sl=result["stop_loss"],
                                tp1=result["tp1"],
                                tp2=result["tp2"],
                                tp3=result["tp3"],
                                scenario_id=result.get("scenario_id", "auto_scanner"),
                                status="active",
                                quality_score=result.get("quality_score", 0),
                                risk_reward=result.get("risk_reward", 0),
                            )

                            logger.info(f"✅ Сигнал #{signal_id} сохранён в БД")
                            # ✅ РЕГИСТРИРУЕМ СИГНАЛ В ЛИМИТЕ
                            self.signals_per_hour.append(now)

                            # Сохраняем данные в market_data для команды /scenario
                            try:
                                # ✅ ИСПОЛЬЗУЕМ result НАПРЯМУЮ (без market_data)
                                self.bot.market_data[symbol] = {
                                    "price": result["entry_price"],
                                    "cvd": result.get(
                                        "cvd", 0
                                    ),  # ← НАПРЯМУЮ ИЗ result!
                                    "volume_ratio": result.get(
                                        "volume_ratio", 0
                                    ),  # ← НАПРЯМУЮ ИЗ result!
                                    "funding_rate": result.get("funding_rate", 0),
                                    "long_short_ratio": result.get(
                                        "long_short_ratio", 0
                                    ),
                                    "market_regime": result.get(
                                        "market_regime", "Unknown"
                                    ),
                                    "wyckoff_phase": result.get(
                                        "wyckoff_phase", "Unknown"
                                    ),
                                    "pattern": result.get("scenario_name", "Unknown"),
                                    "strategy": result.get("strategy", "Unknown"),
                                    "score": result.get("quality_score", 0),
                                    "trend_1h": result.get("trend_1h", "UNKNOWN"),
                                    "trend_4h": result.get("trend_4h", "UNKNOWN"),
                                    "trend_1d": result.get("trend_1d", "UNKNOWN"),
                                    "mtf_aligned": result.get("mtf_aligned", 0),
                                    "mtf_agreement": result.get("mtf_agreement", 0),
                                    "timestamp": datetime.now().isoformat(),
                                }
                                logger.info(
                                    f"💾 {symbol}: Данные сохранены в market_data для /scenario"
                                )
                                logger.debug(
                                    f"🔍 DEBUG: bot.market_data[{symbol}] CVD={self.bot.market_data.get(symbol, {}).get('cvd', 'N/A')}"
                                )
                                logger.debug(
                                    f"🔍 DEBUG: Всего символов в market_data: {len(self.bot.market_data)}"
                                )
                            except Exception as e:
                                logger.error(
                                    f"❌ Ошибка сохранения market_data для {symbol}: {e}"
                                )

                            # Отправляем уведомление в Telegram
                            if (
                                hasattr(self.bot, "telegram_handler")
                                and self.bot.telegram_handler
                            ):
                                try:
                                    await self.bot.telegram_handler.notify_new_signal(
                                        {
                                            "id": signal_id,
                                            "symbol": symbol,
                                            "direction": result["direction"],
                                            "entry_price": result["entry_price"],
                                            "tp1": result["tp1"],
                                            "tp2": result["tp2"],
                                            "tp3": result["tp3"],
                                            "stop_loss": result["stop_loss"],
                                            "quality_score": result.get(
                                                "quality_score", 0
                                            ),
                                            "risk_reward": result.get("risk_reward", 0),
                                            "timestamp": datetime.now(),
                                        }
                                    )
                                    logger.info(
                                        f"📨 Сигнал #{signal_id} отправлен в Telegram"
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"❌ Ошибка отправки Telegram уведомления: {e}"
                                    )

                    # Небольшая пауза между символами
                    await asyncio.sleep(0.5)

                except Exception as e:
                    logger.error(f"❌ Ошибка анализа {symbol}: {e}")
                    continue

            logger.info(f"✅ Сканирование завершено: найдено {signals_found} сигналов")

        except Exception as e:
            logger.error(f"❌ Ошибка scan_market: {e}")

    # ✅ ДОБАВИТЬ ЭТОТ МЕТОД ЗДЕСЬ:
    async def scan_symbol(self, symbol: str) -> Optional[Dict]:
        """
        Полное сканирование одного символа

        Returns:
            Dict с деталями сигнала если создан, иначе None
        """
        try:
            logger.info(f"🔍 Сканирование {symbol}...")

            # Используем существующий метод analyze_symbol
            result = await self.analyze_symbol(symbol)

            if not result or not result.get("signal"):
                logger.debug(f"ℹ️ {symbol}: подходящих сигналов не найдено")
                return None

            # Сохраняем сигнал если есть recorder
            if self.signal_recorder:
                signal_id = self.signal_recorder.record_signal(
                    symbol=symbol,
                    direction=result["direction"],
                    entry_price=result["entry_price"],
                    sl=result["stop_loss"],
                    tp1=result["tp1"],
                    tp2=result["tp2"],
                    tp3=result["tp3"],
                    scenario_id=result.get("scenario_id", "auto_scanner"),
                    status="active",
                    quality_score=result.get("quality_score", 0),
                    risk_reward=result.get("risk_reward", 0),
                )

                logger.info(f"✅ {symbol}: Сигнал #{signal_id} создан")

                # СОХРАНЯЕМ ДАННЫЕ В market_data ДЛЯ КОМАНДЫ /scenario
                try:
                    self.bot.market_data[symbol] = {
                        "price": result["entry_price"],
                        "cvd": result.get("cvd", 0),
                        "volume_ratio": result.get("volume_ratio", 0),
                        "funding_rate": result.get("funding_rate", 0),
                        "long_short_ratio": result.get("long_short_ratio", 0),
                        "market_regime": result.get("market_regime", "Unknown"),
                        "wyckoff_phase": result.get("wyckoff_phase", "Unknown"),
                        "pattern": result.get("scenario_name", "Unknown"),
                        "strategy": result.get("strategy", "Unknown"),
                        "score": result.get("quality_score", 0),
                        "trend_1h": result.get("trend_1h", "UNKNOWN"),
                        "trend_4h": result.get("trend_4h", "UNKNOWN"),
                        "trend_1d": result.get("trend_1d", "UNKNOWN"),
                        "mtf_aligned": result.get("mtf_aligned", 0),
                        "mtf_agreement": result.get("mtf_agreement", 0),
                        "timestamp": datetime.now().isoformat(),
                    }
                    logger.info(
                        f"💾 {symbol}: Данные сохранены в market_data для /scenario"
                    )
                    logger.debug(
                        f"🔍 DEBUG: bot.market_data[{symbol}] CVD={self.bot.market_data.get(symbol, {}).get('cvd', 'N/A')}"
                    )
                    logger.debug(
                        f"🔍 DEBUG: Всего символов в market_data: {len(self.bot.market_data)}"
                    )
                except Exception as e:
                    logger.error(f"❌ Ошибка сохранения market_data для {symbol}: {e}")

                # Отправляем уведомление в Telegram
                if hasattr(self.bot, "telegram_handler") and self.bot.telegram_handler:
                    try:
                        await self.bot.telegram_handler.notify_new_signal(
                            {
                                "id": signal_id,
                                "symbol": symbol,
                                "direction": result["direction"],
                                "entry_price": result["entry_price"],
                                "tp1": result["tp1"],
                                "tp2": result["tp2"],
                                "tp3": result["tp3"],
                                "stop_loss": result["stop_loss"],
                                "quality_score": result.get("quality_score", 0),
                                "risk_reward": result.get("risk_reward", 0),
                                "status": result.get("status", "active"),
                            }
                        )
                        logger.info(f"📨 Сигнал #{signal_id} отправлен в Telegram")
                    except Exception as e:
                        logger.error(f"❌ Ошибка отправки Telegram уведомления: {e}")
                # ✅ ВОЗВРАЩАЕМ ВЕСЬ ОБЪЕКТ С ДЕТАЛЯМИ!
                return {
                    "signal_id": signal_id,
                    "symbol": symbol,
                    "direction": result["direction"],
                    "entry_price": result["entry_price"],
                    "stop_loss": result["stop_loss"],
                    "tp1": result["tp1"],
                    "tp2": result["tp2"],
                    "tp3": result["tp3"],
                    "quality_score": result.get("quality_score", 0),
                    "risk_reward": result.get("risk_reward", 0),
                    "status": result.get("status", "active"),
                }

            return None

        except Exception as e:
            logger.error(f"❌ Критическая ошибка scan_symbol {symbol}: {e}")
            return None

    async def scan_multiple_symbols(self, symbols: List[str]) -> List[Dict]:
        """
        Сканирование нескольких символов параллельно

        Args:
            symbols: Список символов

        Returns:
            Список ID сгенерированных сигналов
        """
        try:
            tasks = [self.scan_symbol(symbol) for symbol in symbols]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Фильтруем успешные результаты
            signal_data = [
                result
                for result in results
                if isinstance(result, dict) and result is not None
            ]

            if signal_data:
                logger.info(
                    f"✅ Сканирование завершено: {len(signal_data)} новых сигналов"
                )

            return signal_data

        except Exception as e:
            logger.error(f"❌ Ошибка scan_multiple_symbols: {e}")
            return []

    async def analyze_symbol(self, symbol: str) -> Optional[Dict]:
        """
        Анализ одного символа
        """
        try:
            # ✅ 1. ПРОВЕРКА COOLDOWN
            now = time.time()
            last_time = self.last_signal_time.get(symbol, 0)

            if now - last_time < self.signal_cooldown:
                remaining_min = int((self.signal_cooldown - (now - last_time)) / 60)
                logger.debug(f"⏸️ {symbol}: cooldown ({remaining_min} мин осталось)")
                return None

            # ✅ 2. ПРОВЕРКА АКТИВНЫХ ПОЗИЦИЙ
            if hasattr(self.bot, "roi_tracker"):
                active_signals = self.bot.roi_tracker.get_active_signals_by_symbol(
                    symbol
                )
                if len(active_signals) >= self.max_active_positions_per_symbol:
                    logger.debug(
                        f"⏸️ {symbol}: {len(active_signals)} активных позиций (лимит)"
                    )
                    return None

            # ========== 3. ПОЛУЧАЕМ ДАННЫЕ РЫНКА ==========

            market_data = await self._get_market_data(symbol)
            if not market_data:
                return None

            # ========== 4. ВАЛИДАЦИЯ MARKET DATA ==========
            current_price = market_data.get("close", 0)
            if not DataValidator.validate_price(current_price, symbol):
                logger.warning(f"⚠️ {symbol}: Невалидная цена, пропускаем")
                return None

            # ========== 5. ВАЛИДАЦИЯ СВЕЧЕЙ ==========
            candles = market_data.get("candles", [])
            if not DataValidator.validate_candles_list(candles, min_length=20):
                logger.warning(f"⚠️ {symbol}: Невалидные свечи, пропускаем")
                return None

            # ========== 6. ПОДГОТОВКА ДАННЫХ ==========
            indicators = {}
            mtf_trends = {}
            volume_profile = await self.bot.get_volume_profile(symbol)

            # ВАЛИДАЦИЯ VOLUME PROFILE
            if volume_profile:
                poc = volume_profile.get("poc")
                vah = volume_profile.get("vah")
                val = volume_profile.get("val")

                if not all(
                    [
                        DataValidator.validate_price(poc, f"{symbol}.poc"),
                        DataValidator.validate_price(vah, f"{symbol}.vah"),
                        DataValidator.validate_price(val, f"{symbol}.val"),
                    ]
                ):
                    logger.warning(
                        f"⚠️ {symbol}: Невалидный Volume Profile, используем fallback"
                    )
                    volume_profile = {}
            else:
                logger.debug(f"⚠️ {symbol}: Volume Profile не получен")
                volume_profile = {}

            news_sentiment = {}
            veto_checks = {}

            # Если есть MTF analyzer - получаем тренды
            if hasattr(self.bot, "mtf_analyzer") and self.bot.mtf_analyzer:
                try:
                    mtf_trends = {"1h": "neutral", "4h": "neutral", "1d": "neutral"}
                except:
                    pass

            # Если есть sentiment analyzer - получаем sentiment
            if hasattr(self.bot, "enhanced_sentiment") and self.bot.enhanced_sentiment:
                try:
                    news_sentiment = {"overall": "neutral", "score": 0.5}
                except:
                    pass

            # ========== 7. ИЩЕМ СОВПАДЕНИЕ СЦЕНАРИЯ ==========
            match_result = self.scenario_matcher.match_scenario(
                symbol=symbol,
                market_data=market_data,
                indicators=indicators,
                mtf_trends=mtf_trends,
                volume_profile=volume_profile,
                news_sentiment=news_sentiment,
                veto_checks=veto_checks,
            )

            # Проверяем успешность match
            if not match_result:
                return None

            # ========== 8. ПРИМЕНЯЕМ ФИЛЬТРЫ ==========
            direction = match_result.get("direction", "LONG")

            # Инициализируем переменные
            cvd_value = 0
            volume_ratio_value = 0
            trend_1h = "UNKNOWN"
            trend_4h = "UNKNOWN"
            trend_1d = "UNKNOWN"
            mtf_aligned = 0
            mtf_agreement = 0

            # 8.1 CONFIRM FILTER
            if hasattr(self.bot, "confirm_filter") and self.bot.confirm_filter:
                logger.info(f"🔍 Применение Confirm Filter для {symbol}...")

                # ✅ СОЗДАЁМ signal_data С РЕАЛЬНЫМ СЦЕНАРИЕМ!
                signal_data = {
                    "pattern": match_result.get("scenario_name", "Unknown"),
                    "direction": direction,
                }

                filters_passed = await self.bot.confirm_filter.validate(
                    symbol,
                    direction,
                    market_data,
                    signal_data,  # ← ПЕРЕДАЁМ signal_data!
                )

                # ✅ ПОЛУЧАЕМ CVD **СРАЗУ** ПОСЛЕ validate() (независимо от результата!)
                try:
                    cvd_value = self.bot.confirm_filter.last_cvd or 0
                    volume_ratio_value = self.bot.confirm_filter.last_volume_ratio or 0
                    logger.debug(
                        f"✅ Получены из confirm_filter: CVD={cvd_value}, Volume={volume_ratio_value}"
                    )
                except Exception as e:
                    logger.warning(f"⚠️ Не удалось получить CVD из confirm_filter: {e}")

                if not filters_passed:
                    logger.warning(
                        f"❌ {symbol} {direction}: Сигнал ОТКЛОНЁН Confirm Filter"
                    )
                    return None

                logger.info(f"✅ {symbol}: Confirm Filter пройден")

            # 8.2 MULTI-TF FILTER + ПОЛУЧЕНИЕ MTF ДАННЫХ
            if hasattr(self.bot, "multi_tf_filter") and self.bot.multi_tf_filter:
                logger.info(f"🔍 Применение Multi-TF Filter для {symbol}...")

                is_valid, trends, mtf_reason = await self.bot.multi_tf_filter.validate(
                    symbol=symbol,
                    direction=direction,
                    scenario_name=match_result.get("scenario_name"),
                )

                if not is_valid:
                    logger.warning(
                        f"❌ {symbol} {direction}: Сигнал ОТКЛОНЁН Multi-TF Filter: {mtf_reason}"
                    )
                    return None

                logger.info(f"✅ {symbol}: Multi-TF Filter пройден: {mtf_reason}")
                logger.info(f"   Тренды: {trends}")

                # ✅ ПОЛУЧАЕМ MTF ДАННЫЕ СРАЗУ!
                if trends:
                    trend_1h = trends.get("1h", "UNKNOWN")
                    trend_4h = trends.get("4h", "UNKNOWN")
                    trend_1d = trends.get("1d", "UNKNOWN")
                    mtf_aligned = trends.get("aligned_count", 0)

                    # ✅ ПРАВИЛЬНЫЙ РАСЧЁТ СОГЛАСОВАННОСТИ
                    total_trends = 3

                    if direction.upper() == "LONG":
                        target_trend = "UP"
                    elif direction.upper() == "SHORT":
                        target_trend = "DOWN"
                    else:
                        target_trend = direction.upper()

                    aligned_trends = sum(
                        [
                            1 if trend_1h.upper() == target_trend else 0,
                            1 if trend_4h.upper() == target_trend else 0,
                            1 if trend_1d.upper() == target_trend else 0,
                        ]
                    )
                    mtf_agreement = int((aligned_trends / total_trends) * 100)

                    logger.debug(
                        f"   📊 {symbol} MTF: {trend_1h}/{trend_4h}/{trend_1d} ({mtf_agreement}%)"
                    )

            # ========== 9. ПРОВЕРЯЕМ STATUS ==========
            if match_result.get("status") == "observation":
                logger.debug(f"⏭️ {symbol}: observation режим, пропускаем")
                return None

            # ========== 10. ВАЛИДАЦИЯ TP/SL ==========
            entry_price = match_result.get("entry_price", 0)
            stop_loss = match_result.get("stop_loss", 0)
            tp1 = match_result.get("tp1", 0)
            tp2 = match_result.get("tp2", 0)
            tp3 = match_result.get("tp3", 0)

            if not all(
                [
                    DataValidator.validate_price(entry_price, f"{symbol}.entry"),
                    DataValidator.validate_price(stop_loss, f"{symbol}.sl"),
                    DataValidator.validate_price(tp1, f"{symbol}.tp1"),
                    DataValidator.validate_price(tp2, f"{symbol}.tp2"),
                    DataValidator.validate_price(tp3, f"{symbol}.tp3"),
                ]
            ):
                logger.warning(f"⚠️ {symbol}: Невалидные TP/SL, пропускаем сигнал")
                return None

            # ========== 11. ПОЛУЧАЕМ ДОПОЛНИТЕЛЬНЫЕ ДАННЫЕ ==========
            # Funding Rate
            funding_rate = 0.0
            try:
                if hasattr(self.bot, "bybit_connector") and self.bot.bybit_connector:
                    ticker = await self.bot.bybit_connector.get_ticker(symbol)
                    if ticker:
                        funding_rate = float(ticker.get("fundingRate", 0))
                        logger.debug(f"   📊 {symbol} Funding Rate: {funding_rate:.4%}")
            except Exception as e:
                logger.debug(f"   ⚠️ Не удалось получить Funding Rate для {symbol}: {e}")

            # Long/Short Ratio
            long_short_ratio = 0.0
            try:
                if hasattr(self.bot, "bybit_connector") and self.bot.bybit_connector:
                    ls_ratio = self.bot.bybit_connector.get_long_short_ratio(
                        symbol
                    )

                    if ls_ratio:
                        long_short_ratio = float(ls_ratio.get("ratio", 0))
                        logger.debug(
                            f"   📊 {symbol} L/S Ratio: {long_short_ratio:.2f}"
                        )
            except Exception as e:
                logger.debug(f"   ⚠️ Не удалось получить L/S Ratio для {symbol}: {e}")

            # ========== 12. ФОРМИРУЕМ СИГНАЛ ==========
            signal = {
                "signal": True,
                "symbol": symbol,
                "direction": match_result.get("direction", "LONG"),
                "entry_price": entry_price,
                "stop_loss": stop_loss,
                "tp1": tp1,
                "tp2": tp2,
                "tp3": tp3,
                "scenario_id": match_result.get("scenario_id", "unknown"),
                "scenario_name": match_result.get("scenario_name", "Unknown"),
                "status": match_result.get("status", "active"),
                "quality_score": match_result.get("score", 0),
                "risk_reward": match_result.get("risk_reward", 2.0),
                "cvd": cvd_value,
                "volume_ratio": volume_ratio_value,
                "funding_rate": funding_rate,
                "long_short_ratio": long_short_ratio,
                "market_regime": match_result.get("market_regime", "Unknown"),
                "wyckoff_phase": match_result.get("wyckoff_phase", "Unknown"),
                "strategy": match_result.get("strategy", "Unknown"),
                "trend_1h": trend_1h,
                "trend_4h": trend_4h,
                "trend_1d": trend_1d,
                "mtf_aligned": mtf_aligned,
                "mtf_agreement": mtf_agreement,
            }
            self.last_signal_time[symbol] = now
            logger.info(f"✅ {symbol}: сигнал найден, cooldown активен")
            return signal

        except Exception as e:
            logger.error(f"❌ Ошибка analyze_symbol для {symbol}: {e}")
            return None

    async def _get_market_data(self, symbol: str) -> Optional[Dict]:
        """
        Получение данных рынка для символа

        Args:
            symbol: Торговая пара

        Returns:
            Dict с рыночными данными
        """
        try:
            # Получаем данные через коннектор бота
            if not hasattr(self.bot, "bybit_connector"):
                logger.error("❌ bybit_connector не найден в bot_instance")
                return None

            # Получаем тикер
            ticker = await self.bot.bybit_connector.get_ticker(symbol)
            if not ticker:
                logger.warning(f"⚠️ {symbol}: Не удалось получить ticker")
                return None

            # Получаем свечи (например, 1h)
            candles = await self.bot.bybit_connector.get_klines(
                symbol=symbol, interval="60", limit=100  # 1h
            )

            if not candles or len(candles) == 0:
                logger.warning(f"⚠️ {symbol}: Нет свечей")
                return None

            # ========== ВАЛИДАЦИЯ ЦЕНЫ ИЗ ТИКЕРА ==========
            last_price = float(
                ticker.get("lastPrice", 0) or ticker.get("last_price", 0)
            )

            if not DataValidator.validate_price(last_price, f"{symbol}.ticker"):
                logger.warning(f"⚠️ {symbol}: Невалидная цена в ticker")
                return None

            # Формируем данные для анализа
            market_data = {
                "symbol": symbol,
                "close": last_price,
                "price": last_price,  # Alias
                "volume": float(
                    ticker.get("volume24h", 0) or ticker.get("volume_24h", 0)
                ),
                "candles": candles,
                "timestamp": datetime.now(),
            }

            return market_data

        except Exception as e:
            logger.error(f"❌ Ошибка _get_market_data для {symbol}: {e}")
            return None


# Экспорт
__all__ = ["UnifiedAutoScanner"]
