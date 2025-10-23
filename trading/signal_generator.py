# -*- coding: utf-8 -*-
"""
Продвинутый генератор торговых сигналов для GIO Crypto Bot
Интеллектуальное создание торговых сигналов на основе комплексного анализа
"""

import asyncio
import numpy as np
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
from database.signal_manager import save_signal_to_unified


from config.settings import (
    logger,
    DEAL_THRESHOLD,
    RISKY_THRESHOLD,
    DEFAULT_ATR_SL_MULTIPLIER,
    DEFAULT_TP1_PCT,
    MIN_RR_RATIO,
)
from config.constants import (
    SignalStatusEnum,
    SignalLevelEnum,
    EnhancedTradingSignal,
    TrendDirectionEnum,
    VetoReasonEnum,
)
from analytics.veto_system import EnhancedVetoSystem, VetoAnalysisResult
from utils.helpers import current_epoch_ms, safe_float, calculate_percentage_change
from utils.validators import validate_signal_data
from systems.unified_scenario_matcher import EnhancedScenarioMatcher


# Импорт фильтров (если они есть)
try:
    from filters.confirm_filter import ConfirmFilter
    from filters.multi_tf_filter import MultiTimeframeFilter

    FILTERS_AVAILABLE = True
except ImportError:
    FILTERS_AVAILABLE = False
    logger.warning("⚠️ Фильтры не найдены, работа без фильтров")


@dataclass
class ScenarioMatch:
    """Совпадение сценария с рыночными условиями"""

    scenario_id: str
    scenario_name: str
    match_confidence: float
    matched_conditions: List[str]
    signal_type: str  # BUY/SELL
    entry_reasoning: str
    risk_level: str
    expected_timeframe: str


@dataclass
class TechnicalAnalysis:
    """Результат технического анализа"""

    rsi: float = 0.0
    atr: float = 0.0
    sma_20: float = 0.0
    ema_12: float = 0.0
    ema_26: float = 0.0
    macd_line: float = 0.0
    macd_signal: float = 0.0
    bollinger_upper: float = 0.0
    bollinger_lower: float = 0.0
    support_level: float = 0.0
    resistance_level: float = 0.0
    trend_direction: TrendDirectionEnum = TrendDirectionEnum.NEUTRAL
    trend_strength: float = 0.0


class AdvancedSignalGenerator:
    """Продвинутый генератор торговых сигналов с комплексным анализом"""

    def __init__(
        self,
        bot,
        veto_system: EnhancedVetoSystem,
        confirm_filter: Optional["ConfirmFilter"] = None,
        multi_tf_filter: Optional["MultiTimeframeFilter"] = None,
    ):
        """Инициализация генератора сигналов"""
        self.bot = bot
        self.veto_system = veto_system
        self.confirm_filter = confirm_filter
        self.multi_tf_filter = multi_tf_filter

        # ========== ✅ НОВОЕ: EnhancedScenarioMatcher ==========
        try:
            self.scenario_matcher = EnhancedScenarioMatcher()
            logger.info(
                "✅ EnhancedScenarioMatcher v2.0 интегрирован в SignalGenerator"
            )
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации EnhancedScenarioMatcher: {e}")
            self.scenario_matcher = None

        if self.confirm_filter:
            logger.info("✅ Confirm Filter интегрирован в SignalGenerator")
        if self.multi_tf_filter:
            logger.info("✅ Multi-TF Filter интегрирован в SignalGenerator")

        # Кэш технических индикаторов
        self.technical_cache = {}
        self.price_history = defaultdict(lambda: [])

        # Настройки генерации сигналов
        self.signal_settings = {
            "min_confidence": 0.6,
            "max_signals_per_symbol": 3,
            "signal_timeout_ms": 3600000,  # 1 час
            "rr_ratio_multiplier": 1.2,
            "volume_confirmation_required": True,
            "news_sentiment_weight": 0.3,
            "technical_analysis_weight": 0.4,
            "volume_profile_weight": 0.3,
        }

        # Статистика генерации
        self.generation_stats = {
            "total_generated": 0,
            "deal_signals": 0,
            "risky_signals": 0,
            "vetoed_signals": 0,
            "avg_confidence": 0.0,
            "scenarios_matched": defaultdict(int),
            "success_rate_by_level": defaultdict(lambda: {"total": 0, "successful": 0}),
        }

        logger.info("✅ AdvancedSignalGenerator инициализирован")

    async def generate_enhanced_signals(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        volume_profile: Any,
        news_sentiment: Dict[str, Any],
        scenarios: Dict[str, Any],
    ) -> List[EnhancedTradingSignal]:
        """Генерация расширенных торговых сигналов"""
        try:
            if not market_data or not scenarios:
                logger.warning("⚠️ Недостаточно данных для генерации сигналов")
                return []

            # 1. Проверяем veto систему
            veto_result = await self.veto_system.analyze_market_conditions(
                symbol, market_data, volume_profile, news_sentiment
            )

            if veto_result.is_vetoed:
                logger.info(
                    f"🛑 Генерация сигналов заблокирована veto системой для {symbol}"
                )
                self.generation_stats["vetoed_signals"] += 1
                return self._create_vetoed_signals(symbol, veto_result)

            # 2. Выполняем технический анализ
            technical_analysis = await self._perform_technical_analysis(
                symbol, market_data
            )

            # 3. ✅ НОВОЕ: Используем EnhancedScenarioMatcher
            scenario_match = None
            if self.scenario_matcher:
                try:
                    # Подготовка indicators для EnhancedScenarioMatcher
                    indicators = {
                        "adx": 25,  # TODO: Добавить реальный ADX
                        "rsi": technical_analysis.rsi,
                        "macd": technical_analysis.macd_line,
                        "macd_signal": technical_analysis.macd_signal,
                        "macd_above_signal": technical_analysis.macd_line
                        > technical_analysis.macd_signal,
                        "volume_ma20": safe_float(
                            market_data.get("ticker", {}).get("volume_24h", 0)
                        )
                        / 24,
                        "atr": technical_analysis.atr,
                        "bb_width_percentile": 50,  # TODO: Добавить расчёт
                        "atr_percentile": 50,  # TODO: Добавить расчёт
                    }

                    # MTF trends
                    mtf_trends = {
                        "1H": technical_analysis.trend_direction.value,
                        "4H": technical_analysis.trend_direction.value,
                        "1D": technical_analysis.trend_direction.value,
                    }

                    # Volume profile dict
                    vp_dict = {
                        "poc": (
                            getattr(volume_profile, "poc_price", 0)
                            if volume_profile
                            else 0
                        ),
                        "vah": (
                            getattr(volume_profile, "vah_price", 0)
                            if volume_profile
                            else 0
                        ),
                        "val": (
                            getattr(volume_profile, "val_price", 0)
                            if volume_profile
                            else 0
                        ),
                        "vwap": safe_float(
                            market_data.get("ticker", {}).get("last_price", 0)
                        ),
                    }

                    # News sentiment dict
                    news_dict = {}
                    if news_sentiment and symbol in news_sentiment:
                        symbol_sentiment = news_sentiment[symbol]
                        news_dict = {
                            "overall": (
                                "bullish"
                                if symbol_sentiment.overall_sentiment > 0.1
                                else (
                                    "bearish"
                                    if symbol_sentiment.overall_sentiment < -0.1
                                    else "neutral"
                                )
                            ),
                            "overall_score": symbol_sentiment.overall_sentiment,
                        }

                    # Veto checks
                    veto_checks = {
                        "high_impact_news": False,
                        "exchange_maintenance": False,
                    }

                    # Вызов EnhancedScenarioMatcher
                    scenario_match = self.scenario_matcher.match_scenario(
                        symbol=symbol,
                        market_data=market_data,
                        indicators=indicators,
                        mtf_trends=mtf_trends,
                        volume_profile=vp_dict,
                        news_sentiment=news_dict,
                        veto_checks=veto_checks,
                    )
                    if scenario_match:
                        logger.info(
                            f"✅ EnhancedScenarioMatcher нашёл сценарий {scenario_match['scenario_id']} для {symbol}"
                        )
                except Exception as e:
                    logger.error(f"❌ Ошибка EnhancedScenarioMatcher для {symbol}: {e}")
                    scenario_match = None

            # Обогащаем market_data информацией о Market Regime
            if hasattr(self.bot, "market_regime_detector"):
                try:
                    regime_result = self.bot.market_regime_detector.detect_regime(
                        market_data
                    )
                    if regime_result:
                        market_data["market_regime"] = regime_result.get(
                            "regime", "NEUTRAL"
                        )
                        market_data["regime_confidence"] = regime_result.get(
                            "confidence", 0.5
                        )
                        logger.debug(
                            f"✅ Market Regime определён: {market_data['market_regime']} (conf: {market_data['regime_confidence']:.2f})"
                        )
                except Exception as e:
                    logger.debug(f"⚠️ Ошибка Market Regime для {symbol}: {e}")
                    market_data["market_regime"] = "NEUTRAL"
                    market_data["regime_confidence"] = 0.5

            # Fallback на старую логику если новый matcher не нашёл сигнал
            if not scenario_match:
                logger.info(
                    f"⚠️ EnhancedScenarioMatcher не нашёл сценарий, используем старую логику для {symbol}"
                )
                scenario_matches = await self._analyze_scenarios(
                    symbol,
                    market_data,
                    volume_profile,
                    news_sentiment,
                    scenarios,
                    technical_analysis,
                )
            else:
                # Конвертируем результат EnhancedScenarioMatcher в ScenarioMatch
                scenario_matches = [
                    ScenarioMatch(
                        scenario_id=scenario_match["scenario_id"],
                        scenario_name=scenario_match["scenario_name"],
                        match_confidence=(
                            1.0
                            if scenario_match["confidence"] == "high"
                            else (
                                0.8 if scenario_match["confidence"] == "medium" else 0.6
                            )
                        ),
                        matched_conditions=["EnhancedScenarioMatcher v2.0"],
                        signal_type=scenario_match["direction"],
                        entry_reasoning=f"{scenario_match['strategy']} в {scenario_match['market_regime']} режиме",
                        risk_level=scenario_match["risk_profile"],
                        expected_timeframe="1h",
                    )
                ]

            if not scenario_matches:
                logger.debug(f"📊 Нет подходящих сценариев для {symbol}")
                return []

            # 4. Генерируем сигналы из совпадающих сценариев
            generated_signals = []
            for match in scenario_matches:
                signal = await self._create_signal_from_match(
                    symbol,
                    match,
                    market_data,
                    technical_analysis,
                    veto_result,
                    volume_profile,
                    news_sentiment,
                )
                if signal:
                    # ========== ✅ DEBUG ЛОГИ ==========
                    logger.info(f"🔍 DEBUG для {symbol}:")
                    logger.info(f"   FILTERS_AVAILABLE = {FILTERS_AVAILABLE}")
                    logger.info(f"   self.confirm_filter = {self.confirm_filter}")
                    logger.info(f"   self.multi_tf_filter = {self.multi_tf_filter}")
                    # ===================================

                    # НОВОЕ: Применяем фильтры
                    if FILTERS_AVAILABLE and (
                        self.confirm_filter or self.multi_tf_filter
                    ):
                        logger.info(f"🔍 Применение фильтров для {symbol}...")

                        filters_passed, reason = await self._apply_filters(
                            signal, symbol, market_data, technical_analysis
                        )

                        if filters_passed:
                            logger.info(f"✅ {symbol}: Сигнал прошёл все фильтры")

                            # ========== ✅ СОХРАНЕНИЕ В unified_signals ==========
                            if save_signal_to_unified(signal):
                                logger.info(
                                    f"💾 {symbol}: Сигнал сохранён в unified_signals"
                                )
                            # ====================================================

                            generated_signals.append(signal)
                        else:
                            logger.warning(
                                f"❌ {symbol}: Сигнал отклонён фильтром: {reason}"
                            )
                    else:
                        # Фильтры не доступны или не настроены
                        logger.warning(f"⚠️ {symbol}: Фильтры ПРОПУЩЕНЫ!")
                        logger.warning(
                            f"   Причина: FILTERS_AVAILABLE={FILTERS_AVAILABLE}, confirm={self.confirm_filter}, mtf={self.multi_tf_filter}"
                        )
                        generated_signals.append(signal)

            # 5. Фильтруем и ранжируем сигналы
            final_signals = await self._filter_and_rank_signals(
                generated_signals, market_data
            )

            # 6. Обновляем статистику
            self._update_generation_stats(final_signals, scenario_matches)

            if final_signals:
                logger.info(
                    f"🎯 Сгенерировано {len(final_signals)} сигналов для {symbol}"
                )

            return final_signals

        except Exception as e:
            logger.error(f"❌ Ошибка генерации сигналов: {e}")
            return []

    async def _perform_technical_analysis(
        self, symbol: str, market_data: Dict
    ) -> TechnicalAnalysis:
        """Выполнение технического анализа"""
        try:
            # Получаем исторические данные свечей
            klines_data = market_data.get("klines", {})
            candles = klines_data.get("candles", [])

            if len(candles) < 50:  # Минимум 50 свечей для анализа
                logger.warning(f"⚠️ Недостаточно исторических данных для {symbol}")
                return TechnicalAnalysis()

            # Извлекаем цены
            closes = [safe_float(candle.get("close", 0)) for candle in candles[-50:]]
            highs = [safe_float(candle.get("high", 0)) for candle in candles[-50:]]
            lows = [safe_float(candle.get("low", 0)) for candle in candles[-50:]]
            volumes = [safe_float(candle.get("volume", 0)) for candle in candles[-50:]]

            # Сохраняем историю цен
            self.price_history[symbol] = closes[-20:]  # Последние 20 значений

            current_price = closes[-1]

            # Рассчитываем индикаторы
            technical = TechnicalAnalysis()

            # RSI
            technical.rsi = self._calculate_rsi(closes, period=14)

            # ATR
            technical.atr = self._calculate_atr(highs, lows, closes, period=14)

            # Moving Averages
            technical.sma_20 = self._calculate_sma(closes, period=20)
            technical.ema_12 = self._calculate_ema(closes, period=12)
            technical.ema_26 = self._calculate_ema(closes, period=26)

            # MACD
            macd_line, macd_signal = self._calculate_macd(closes)
            technical.macd_line = macd_line
            technical.macd_signal = macd_signal

            # Bollinger Bands
            bb_upper, bb_lower = self._calculate_bollinger_bands(
                closes, period=20, std_dev=2
            )
            technical.bollinger_upper = bb_upper
            technical.bollinger_lower = bb_lower

            # Support & Resistance
            technical.support_level = self._find_support_level(lows[-20:])
            technical.resistance_level = self._find_resistance_level(highs[-20:])

            # Trend Analysis
            technical.trend_direction = self._determine_trend_direction(
                closes, technical
            )
            technical.trend_strength = self._calculate_trend_strength(closes, technical)

            return technical

        except Exception as e:
            logger.error(f"❌ Ошибка технического анализа: {e}")
            return TechnicalAnalysis()

    def _calculate_rsi(self, prices: List[float], period: int = 14) -> float:
        """Расчёт RSI индикатора"""
        try:
            if len(prices) < period + 1:
                return 50.0  # Нейтральное значение

            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)

            avg_gains = np.mean(gains[-period:])
            avg_losses = np.mean(losses[-period:])

            if avg_losses == 0:
                return 100.0

            rs = avg_gains / avg_losses
            rsi = 100 - (100 / (1 + rs))

            return round(float(rsi), 2)

        except Exception:
            return 50.0

    def _calculate_atr(
        self,
        highs: List[float],
        lows: List[float],
        closes: List[float],
        period: int = 14,
    ) -> float:
        """Расчёт Average True Range"""
        try:
            if len(highs) < period + 1:
                return 0.0

            true_ranges = []
            for i in range(1, len(closes)):
                tr1 = highs[i] - lows[i]
                tr2 = abs(highs[i] - closes[i - 1])
                tr3 = abs(lows[i] - closes[i - 1])
                true_range = max(tr1, tr2, tr3)
                true_ranges.append(true_range)

            if len(true_ranges) < period:
                return 0.0

            atr = np.mean(true_ranges[-period:])
            return round(float(atr), 2)

        except Exception:
            return 0.0

    def _calculate_sma(self, prices: List[float], period: int) -> float:
        """Расчёт Simple Moving Average"""
        try:
            if len(prices) < period:
                return 0.0

            sma = np.mean(prices[-period:])
            return round(float(sma), 2)

        except Exception:
            return 0.0

    def _calculate_ema(self, prices: List[float], period: int) -> float:
        """Расчёт Exponential Moving Average"""
        try:
            if len(prices) < period:
                return 0.0

            multiplier = 2 / (period + 1)
            ema = prices[0]

            for price in prices[1:]:
                ema = (price * multiplier) + (ema * (1 - multiplier))

            return round(float(ema), 2)

        except Exception:
            return 0.0

    def _calculate_macd(self, prices: List[float]) -> Tuple[float, float]:
        """Расчёт MACD индикатора"""
        try:
            if len(prices) < 26:
                return 0.0, 0.0

            ema_12 = self._calculate_ema(prices, 12)
            ema_26 = self._calculate_ema(prices, 26)
            macd_line = ema_12 - ema_26

            # Для упрощения используем простую EMA для сигнальной линии
            macd_signal = macd_line * 0.8  # Упрощённый расчёт

            return round(float(macd_line), 2), round(float(macd_signal), 2)

        except Exception:
            return 0.0, 0.0

    def _calculate_bollinger_bands(
        self, prices: List[float], period: int = 20, std_dev: int = 2
    ) -> Tuple[float, float]:
        """Расчёт полос Боллинжера"""
        try:
            if len(prices) < period:
                return 0.0, 0.0

            sma = self._calculate_sma(prices, period)
            std = np.std(prices[-period:])

            upper_band = sma + (std * std_dev)
            lower_band = sma - (std * std_dev)

            return round(float(upper_band), 2), round(float(lower_band), 2)

        except Exception:
            return 0.0, 0.0

    def _find_support_level(self, lows: List[float]) -> float:
        """Поиск уровня поддержки"""
        try:
            if len(lows) < 5:
                return 0.0

            # Простой алгоритм: находим минимум из последних минимумов
            recent_lows = sorted(lows)
            support = np.mean(recent_lows[:3])  # Среднее из 3 самых низких значений

            return round(float(support), 2)

        except Exception:
            return 0.0

    def _find_resistance_level(self, highs: List[float]) -> float:
        """Поиск уровня сопротивления"""
        try:
            if len(highs) < 5:
                return 0.0

            # Простой алгоритм: находим максимум из последних максимумов
            recent_highs = sorted(highs, reverse=True)
            resistance = np.mean(
                recent_highs[:3]
            )  # Среднее из 3 самых высоких значений

            return round(float(resistance), 2)

        except Exception:
            return 0.0

    def _determine_trend_direction(
        self, prices: List[float], technical: TechnicalAnalysis
    ) -> TrendDirectionEnum:
        """Определение направления тренда"""
        try:
            if len(prices) < 10:
                return TrendDirectionEnum.NEUTRAL

            current_price = prices[-1]

            # Анализ на основе скользящих средних
            bullish_signals = 0
            bearish_signals = 0

            # EMA 12 vs EMA 26
            if technical.ema_12 > technical.ema_26:
                bullish_signals += 1
            else:
                bearish_signals += 1

            # Текущая цена vs SMA 20
            if current_price > technical.sma_20:
                bullish_signals += 1
            else:
                bearish_signals += 1

            # MACD
            if technical.macd_line > technical.macd_signal:
                bullish_signals += 1
            else:
                bearish_signals += 1

            # RSI
            if 30 < technical.rsi < 70:
                pass  # Нейтральная зона
            elif technical.rsi > 70:
                bearish_signals += 0.5  # Перекупленность
            elif technical.rsi < 30:
                bullish_signals += 0.5  # Перепроданность

            # Определяем итоговое направление
            if bullish_signals > bearish_signals:
                return TrendDirectionEnum.BULLISH
            elif bearish_signals > bullish_signals:
                return TrendDirectionEnum.BEARISH
            else:
                return TrendDirectionEnum.NEUTRAL

        except Exception:
            return TrendDirectionEnum.NEUTRAL

    def _calculate_trend_strength(
        self, prices: List[float], technical: TechnicalAnalysis
    ) -> float:
        """Расчёт силы тренда"""
        try:
            if len(prices) < 10:
                return 0.0

            strength_factors = []

            # Фактор ADX (упрощённая версия)
            price_changes = np.diff(prices[-14:])
            avg_change = np.mean(np.abs(price_changes))
            strength_factors.append(min(1.0, avg_change / prices[-1] * 100))

            # Фактор расстояния от скользящих средних
            current_price = prices[-1]
            if technical.sma_20 > 0:
                sma_distance = abs(current_price - technical.sma_20) / technical.sma_20
                strength_factors.append(min(1.0, sma_distance * 10))

            # Фактор MACD дивергенции
            if technical.macd_line != 0:
                macd_strength = abs(technical.macd_line - technical.macd_signal) / abs(
                    technical.macd_line
                )
                strength_factors.append(min(1.0, macd_strength))

            # Итоговая сила тренда
            if strength_factors:
                trend_strength = sum(strength_factors) / len(strength_factors)
                return round(float(trend_strength), 3)

            return 0.0

        except Exception:
            return 0.0

    async def _analyze_scenarios(
        self,
        symbol: str,
        market_data: Dict,
        volume_profile: Any,
        news_sentiment: Dict,
        scenarios: Dict,
        technical: TechnicalAnalysis,
    ) -> List[ScenarioMatch]:
        """Анализ соответствия торговых сценариев"""
        try:
            matches = []
            current_price = safe_float(
                market_data.get("ticker", {}).get("last_price", 0)
            )

            if current_price <= 0:
                return matches

            if isinstance(scenarios, list):
                logger.info(
                    f"🔄 Конвертация {len(scenarios)} сценариев из списка в словарь"
                )
                scenarios_dict = {}
                for idx, scenario in enumerate(scenarios):
                    # Используем 'id' или 'name' как ключ, или генерируем
                    scenario_id = scenario.get(
                        "id", scenario.get("name", f"scenario_{idx}")
                    )
                    scenarios_dict[scenario_id] = scenario
                scenarios = scenarios_dict
                logger.debug(f"✅ Преобразовано в {len(scenarios)} сценариев-словарей")

            for scenario_id, scenario_data in scenarios.items():
                try:
                    # Проверяем базовые условия сценария
                    if not self._validate_scenario_basic_conditions(
                        scenario_data, symbol
                    ):
                        continue

                    # Анализируем совпадение условий
                    match_result = await self._match_scenario_conditions(
                        scenario_data,
                        market_data,
                        volume_profile,
                        news_sentiment,
                        technical,
                        current_price,
                    )

                    if (
                        match_result["confidence"]
                        >= self.signal_settings["min_confidence"]
                    ):
                        scenario_match = ScenarioMatch(
                            scenario_id=scenario_id,
                            scenario_name=scenario_data.get(
                                "name", f"Scenario_{scenario_id}"
                            ),
                            match_confidence=match_result["confidence"],
                            matched_conditions=match_result["matched_conditions"],
                            signal_type=scenario_data.get("signal_type", "BUY").upper(),
                            entry_reasoning=match_result["reasoning"],
                            risk_level=scenario_data.get("risk_level", "medium"),
                            expected_timeframe=scenario_data.get("timeframe", "1h"),
                        )
                        matches.append(scenario_match)

                except Exception as e:
                    logger.warning(f"⚠️ Ошибка анализа сценария {scenario_id}: {e}")
                    continue

            # Сортируем по уверенности
            matches.sort(key=lambda x: x.match_confidence, reverse=True)
            return matches[:5]  # Топ 5 совпадений

        except Exception as e:
            logger.error(f"❌ Ошибка анализа сценариев: {e}")
            return []

    def _validate_scenario_basic_conditions(
        self, scenario_data: Dict, symbol: str
    ) -> bool:
        """Валидация базовых условий сценария"""
        try:
            # Проверяем обязательные поля
            required_fields = ["name", "signal_type", "conditions"]
            for field in required_fields:
                if field not in scenario_data:
                    return False

            # Проверяем поддерживаемый тип сигнала
            signal_type = scenario_data.get("signal_type", "").upper()
            if signal_type not in ["BUY", "SELL", "LONG", "SHORT"]:
                return False

            # Проверяем символ если указан
            target_symbol = scenario_data.get("symbol")
            if target_symbol and target_symbol != symbol:
                return False

            return True

        except Exception:
            return False

    async def _match_scenario_conditions(
        self,
        scenario_data: Dict,
        market_data: Dict,
        volume_profile: Any,
        news_sentiment: Dict,
        technical: TechnicalAnalysis,
        current_price: float,
    ) -> Dict:
        """Сопоставление условий сценария с рыночными данными"""
        try:
            conditions = scenario_data.get("conditions", {})
            matched_conditions = []
            confidence_scores = []
            reasoning_parts = []

            # Анализ технических условий
            tech_match = self._match_technical_conditions(
                conditions.get("technical", {}), technical
            )
            if tech_match["matched"]:
                matched_conditions.extend(tech_match["conditions"])
                confidence_scores.append(tech_match["confidence"])
                reasoning_parts.append(tech_match["reasoning"])

            # Анализ объёмных условий
            volume_match = self._match_volume_conditions(
                conditions.get("volume", {}), market_data, volume_profile
            )
            if volume_match["matched"]:
                matched_conditions.extend(volume_match["conditions"])
                confidence_scores.append(volume_match["confidence"])
                reasoning_parts.append(volume_match["reasoning"])

            # Анализ новостных условий
            if news_sentiment:
                news_match = self._match_news_conditions(
                    conditions.get("news", {}), news_sentiment
                )
                if news_match["matched"]:
                    matched_conditions.extend(news_match["conditions"])
                    confidence_scores.append(news_match["confidence"])
                    reasoning_parts.append(news_match["reasoning"])

            # Анализ ценовых условий
            price_match = self._match_price_conditions(
                conditions.get("price", {}), market_data, technical, current_price
            )
            if price_match["matched"]:
                matched_conditions.extend(price_match["conditions"])
                confidence_scores.append(price_match["confidence"])
                reasoning_parts.append(price_match["reasoning"])

            # Рассчитываем общую уверенность
            if confidence_scores:
                # Взвешенное среднее с учётом количества совпавших условий
                weight_multiplier = min(2.0, len(matched_conditions) / 3)
                overall_confidence = (
                    sum(confidence_scores) / len(confidence_scores)
                ) * weight_multiplier
                overall_confidence = min(1.0, overall_confidence)
            else:
                overall_confidence = 0.0

            return {
                "confidence": round(overall_confidence, 3),
                "matched_conditions": matched_conditions,
                "reasoning": " | ".join(reasoning_parts),
            }

        except Exception as e:
            logger.error(f"❌ Ошибка сопоставления условий: {e}")
            return {
                "confidence": 0.0,
                "matched_conditions": [],
                "reasoning": f"Error: {e}",
            }

    def _match_technical_conditions(
        self, tech_conditions: Dict, technical: TechnicalAnalysis
    ) -> Dict:
        """Сопоставление технических условий"""
        try:
            if not tech_conditions:
                return {
                    "matched": False,
                    "conditions": [],
                    "confidence": 0.0,
                    "reasoning": "",
                }

            matched = []
            scores = []
            reasons = []

            # RSI условия
            rsi_range = tech_conditions.get("rsi_range")
            if rsi_range and len(rsi_range) == 2:
                if rsi_range[0] <= technical.rsi <= rsi_range[1]:
                    matched.append("RSI в диапазоне")
                    scores.append(0.8)
                    reasons.append(f"RSI {technical.rsi:.1f} в диапазоне {rsi_range}")

            # Тренд условия
            expected_trend = tech_conditions.get("trend_direction")
            if expected_trend and technical.trend_direction.value == expected_trend:
                matched.append("Направление тренда")
                scores.append(0.9)
                reasons.append(f"Тренд {technical.trend_direction.value}")

            # MACD условия
            macd_condition = tech_conditions.get("macd_signal")
            if (
                macd_condition == "bullish_crossover"
                and technical.macd_line > technical.macd_signal
            ):
                matched.append("MACD bullish crossover")
                scores.append(0.7)
                reasons.append("MACD линия выше сигнальной")
            elif (
                macd_condition == "bearish_crossover"
                and technical.macd_line < technical.macd_signal
            ):
                matched.append("MACD bearish crossover")
                scores.append(0.7)
                reasons.append("MACD линия ниже сигнальной")

            # Bollinger Bands условия
            bb_condition = tech_conditions.get("bollinger_position")
            current_price = technical.support_level or technical.resistance_level or 0
            if bb_condition and current_price > 0:
                if (
                    bb_condition == "lower_band"
                    and current_price <= technical.bollinger_lower
                ):
                    matched.append("Цена у нижней полосы Боллинжера")
                    scores.append(0.8)
                    reasons.append("Цена достигла нижней BB")
                elif (
                    bb_condition == "upper_band"
                    and current_price >= technical.bollinger_upper
                ):
                    matched.append("Цена у верхней полосы Боллинжера")
                    scores.append(0.8)
                    reasons.append("Цена достигла верхней BB")

            if matched:
                avg_confidence = sum(scores) / len(scores)
                return {
                    "matched": True,
                    "conditions": matched,
                    "confidence": avg_confidence,
                    "reasoning": " & ".join(reasons),
                }

            return {
                "matched": False,
                "conditions": [],
                "confidence": 0.0,
                "reasoning": "",
            }

        except Exception:
            return {
                "matched": False,
                "conditions": [],
                "confidence": 0.0,
                "reasoning": "Tech analysis error",
            }

    def _match_volume_conditions(
        self, volume_conditions: Dict, market_data: Dict, volume_profile: Any
    ) -> Dict:
        """Сопоставление объёмных условий"""
        try:
            if not volume_conditions:
                return {
                    "matched": False,
                    "conditions": [],
                    "confidence": 0.0,
                    "reasoning": "",
                }

            matched = []
            scores = []
            reasons = []

            ticker = market_data.get("ticker", {})
            current_volume = safe_float(ticker.get("volume_24h", 0))

            # Минимальный объём
            min_volume = volume_conditions.get("min_volume_24h")
            if min_volume and current_volume >= min_volume:
                matched.append("Минимальный объём")
                scores.append(0.6)
                reasons.append(f"Объём {current_volume:.0f} >= {min_volume}")

            # Аномалия объёма
            volume_spike = volume_conditions.get("volume_spike_required")
            if volume_spike and volume_profile:
                # Простая проверка через данные volume profile
                total_volume = getattr(volume_profile, "total_composite_volume", 0)
                if total_volume > current_volume * 1.5:  # Спайк объёма
                    matched.append("Спайк объёма")
                    scores.append(0.8)
                    reasons.append("Обнаружен спайк объёма")

            # POC анализ
            poc_condition = volume_conditions.get("poc_interaction")
            if poc_condition and volume_profile:
                poc_price = getattr(volume_profile, "poc_price", 0)
                current_price = safe_float(ticker.get("last_price", 0))

                if poc_price > 0 and current_price > 0:
                    price_diff_pct = abs(current_price - poc_price) / poc_price * 100

                    if (
                        poc_condition == "near_poc" and price_diff_pct <= 1.0
                    ):  # В пределах 1%
                        matched.append("Цена рядом с POC")
                        scores.append(0.7)
                        reasons.append(f"Цена в {price_diff_pct:.2f}% от POC")

            if matched:
                avg_confidence = sum(scores) / len(scores)
                return {
                    "matched": True,
                    "conditions": matched,
                    "confidence": avg_confidence,
                    "reasoning": " & ".join(reasons),
                }

            return {
                "matched": False,
                "conditions": [],
                "confidence": 0.0,
                "reasoning": "",
            }

        except Exception:
            return {
                "matched": False,
                "conditions": [],
                "confidence": 0.0,
                "reasoning": "Volume analysis error",
            }

    def _match_news_conditions(
        self, news_conditions: Dict, news_sentiment: Dict
    ) -> Dict:
        """Сопоставление новостных условий"""
        try:
            if not news_conditions or not news_sentiment:
                return {
                    "matched": False,
                    "conditions": [],
                    "confidence": 0.0,
                    "reasoning": "",
                }

            matched = []
            scores = []
            reasons = []

            # Берём первый доступный символ из news_sentiment
            symbol_sentiment = None
            for symbol, sentiment_data in news_sentiment.items():
                symbol_sentiment = sentiment_data
                break

            if not symbol_sentiment:
                return {
                    "matched": False,
                    "conditions": [],
                    "confidence": 0.0,
                    "reasoning": "",
                }

            # Общий sentiment
            required_sentiment = news_conditions.get("overall_sentiment")
            if required_sentiment:
                actual_sentiment = symbol_sentiment.overall_sentiment

                if required_sentiment == "bullish" and actual_sentiment > 0.1:
                    matched.append("Bullish новостной sentiment")
                    scores.append(min(1.0, actual_sentiment * 2))
                    reasons.append(f"Bullish sentiment {actual_sentiment:.2f}")
                elif required_sentiment == "bearish" and actual_sentiment < -0.1:
                    matched.append("Bearish новостной sentiment")
                    scores.append(min(1.0, abs(actual_sentiment) * 2))
                    reasons.append(f"Bearish sentiment {actual_sentiment:.2f}")

            # Минимальное количество новостей
            min_news_count = news_conditions.get("min_news_count", 0)
            if symbol_sentiment.total_news_count >= min_news_count:
                matched.append("Достаточное количество новостей")
                scores.append(0.6)
                reasons.append(f"{symbol_sentiment.total_news_count} новостей")

            # Уверенность новостного анализа
            min_confidence = news_conditions.get("min_confidence", 0.5)
            if symbol_sentiment.confidence >= min_confidence:
                matched.append("Высокая уверенность новостного анализа")
                scores.append(symbol_sentiment.confidence)
                reasons.append(f"Уверенность {symbol_sentiment.confidence:.2f}")

            if matched:
                avg_confidence = sum(scores) / len(scores)
                return {
                    "matched": True,
                    "conditions": matched,
                    "confidence": avg_confidence,
                    "reasoning": " & ".join(reasons),
                }

            return {
                "matched": False,
                "conditions": [],
                "confidence": 0.0,
                "reasoning": "",
            }

        except Exception:
            return {
                "matched": False,
                "conditions": [],
                "confidence": 0.0,
                "reasoning": "News analysis error",
            }

    def _match_price_conditions(
        self,
        price_conditions: Dict,
        market_data: Dict,
        technical: TechnicalAnalysis,
        current_price: float,
    ) -> Dict:
        """Сопоставление ценовых условий"""
        try:
            if not price_conditions:
                return {
                    "matched": False,
                    "conditions": [],
                    "confidence": 0.0,
                    "reasoning": "",
                }

            matched = []
            scores = []
            reasons = []

            # Поддержка/сопротивление
            support_test = price_conditions.get("support_test")
            if support_test and technical.support_level > 0:
                support_distance = (
                    abs(current_price - technical.support_level)
                    / technical.support_level
                    * 100
                )
                if support_distance <= 2.0:  # В пределах 2% от поддержки
                    matched.append("Тест поддержки")
                    scores.append(0.8)
                    reasons.append(f"Цена в {support_distance:.2f}% от поддержки")

            resistance_test = price_conditions.get("resistance_test")
            if resistance_test and technical.resistance_level > 0:
                resistance_distance = (
                    abs(current_price - technical.resistance_level)
                    / technical.resistance_level
                    * 100
                )
                if resistance_distance <= 2.0:  # В пределах 2% от сопротивления
                    matched.append("Тест сопротивления")
                    scores.append(0.8)
                    reasons.append(
                        f"Цена в {resistance_distance:.2f}% от сопротивления"
                    )

            # Скользящие средние
            ma_condition = price_conditions.get("moving_average_position")
            if ma_condition and technical.sma_20 > 0:
                if ma_condition == "above_sma20" and current_price > technical.sma_20:
                    matched.append("Цена выше SMA20")
                    scores.append(0.7)
                    reasons.append("Цена выше SMA20")
                elif ma_condition == "below_sma20" and current_price < technical.sma_20:
                    matched.append("Цена ниже SMA20")
                    scores.append(0.7)
                    reasons.append("Цена ниже SMA20")

            # Процентное изменение
            price_change_condition = price_conditions.get("price_change_24h")
            if price_change_condition:
                ticker = market_data.get("ticker", {})
                actual_change = safe_float(ticker.get("price_24h_pcnt", 0))

                min_change = price_change_condition.get("min")
                max_change = price_change_condition.get("max")

                if min_change is not None and actual_change >= min_change:
                    matched.append("Минимальное изменение цены")
                    scores.append(0.6)
                    reasons.append(f"Изменение {actual_change:.2f}% >= {min_change}%")

                if max_change is not None and actual_change <= max_change:
                    matched.append("Максимальное изменение цены")
                    scores.append(0.6)
                    reasons.append(f"Изменение {actual_change:.2f}% <= {max_change}%")

            if matched:
                avg_confidence = sum(scores) / len(scores)
                return {
                    "matched": True,
                    "conditions": matched,
                    "confidence": avg_confidence,
                    "reasoning": " & ".join(reasons),
                }

            return {
                "matched": False,
                "conditions": [],
                "confidence": 0.0,
                "reasoning": "",
            }

        except Exception:
            return {
                "matched": False,
                "conditions": [],
                "confidence": 0.0,
                "reasoning": "Price analysis error",
            }

    async def _create_signal_from_match(
        self,
        symbol: str,
        match: ScenarioMatch,
        market_data: Dict,
        technical: TechnicalAnalysis,
        veto_result: VetoAnalysisResult,
        volume_profile: Any,
        news_sentiment: Dict,
    ) -> Optional[EnhancedTradingSignal]:
        """Создание торгового сигнала из совпадения сценария"""
        try:
            ticker = market_data.get("ticker", {})
            current_price = safe_float(ticker.get("last_price", 0))

            if current_price <= 0:
                return None

            # Определяем параметры входа
            side = match.signal_type.upper()
            if side in ["LONG"]:
                side = "BUY"
            elif side in ["SHORT"]:
                side = "SELL"

            # Рассчитываем стоп-лосс на основе ATR
            atr_multiplier = DEFAULT_ATR_SL_MULTIPLIER
            if technical.atr > 0:
                sl_distance = technical.atr * atr_multiplier
            else:
                sl_distance = current_price * 0.02  # 2% по умолчанию

            if side == "BUY":
                sl_price = current_price - sl_distance
            else:
                sl_price = current_price + sl_distance

            # Рассчитываем тейк-профиты
            tp_distance_1 = sl_distance * MIN_RR_RATIO  # Минимальный RR
            tp_distance_2 = sl_distance * (MIN_RR_RATIO * 2)
            tp_distance_3 = sl_distance * (MIN_RR_RATIO * 3)

            if side == "BUY":
                tp1_price = current_price + tp_distance_1
                tp2_price = current_price + tp_distance_2
                tp3_price = current_price + tp_distance_3
            else:
                tp1_price = current_price - tp_distance_1
                tp2_price = current_price - tp_distance_2
                tp3_price = current_price - tp_distance_3

            # Рассчитываем R/R соотношения
            risk_amount = abs(current_price - sl_price)
            if risk_amount > 0:
                rr1 = abs(tp1_price - current_price) / risk_amount
                rr2 = abs(tp2_price - current_price) / risk_amount
                rr3 = abs(tp3_price - current_price) / risk_amount
            else:
                rr1 = rr2 = rr3 = 1.0

            # Определяем статус сигнала
            if match.match_confidence >= DEAL_THRESHOLD:
                signal_status = SignalStatusEnum.DEAL
            elif match.match_confidence >= RISKY_THRESHOLD:
                signal_status = SignalStatusEnum.RISKY_ENTRY
            else:
                signal_status = SignalStatusEnum.OBSERVATION

            # Определяем уровень сигнала
            if match.match_confidence >= 0.9:
                signal_level = SignalLevelEnum.T1
            elif match.match_confidence >= 0.7:
                signal_level = SignalLevelEnum.T2
            else:
                signal_level = SignalLevelEnum.T3

            # Собираем индикаторы
            indicators = {
                "rsi": technical.rsi,
                "atr": technical.atr,
                "macd_line": technical.macd_line,
                "macd_signal": technical.macd_signal,
                "trend_strength": technical.trend_strength,
                "match_confidence": match.match_confidence,
                "risk_score": veto_result.risk_score,
                "market_stability": veto_result.market_stability,
            }

            # Собираем рыночные условия
            market_conditions = {
                "current_price": current_price,
                "volume_24h": safe_float(ticker.get("volume_24h", 0)),
                "price_change_24h": safe_float(ticker.get("price_24h_pcnt", 0)),
                "spread_bps": safe_float(
                    market_data.get("orderbook", {}).get("spread_bps", 0)
                ),
                "trend_direction": technical.trend_direction.value,
                "poc_price": (
                    getattr(volume_profile, "poc_price", 0) if volume_profile else 0
                ),
            }

            # Собираем новостное влияние
            news_impact = {}
            if news_sentiment and symbol in news_sentiment:
                symbol_sentiment = news_sentiment[symbol]
                news_impact = {
                    "overall_sentiment": symbol_sentiment.overall_sentiment,
                    "confidence": symbol_sentiment.confidence,
                    "total_news_count": symbol_sentiment.total_news_count,
                    "trend_direction": symbol_sentiment.trend_direction.value,
                }

            # Создаём сигнал
            signal = EnhancedTradingSignal(
                symbol=symbol,
                side=side,
                scenario_id=match.scenario_id,
                status=signal_status,
                price_entry=round(current_price, 2),
                sl=round(sl_price, 2),
                tp1=round(tp1_price, 2),
                tp2=round(tp2_price, 2),
                tp3=round(tp3_price, 2),
                rr1=round(rr1, 2),
                rr2=round(rr2, 2),
                rr3=round(rr3, 2),
                timestamp=current_epoch_ms(),
                indicators=indicators,
                reason=f"{match.scenario_name}: {match.entry_reasoning}",
                level=signal_level,
                confidence_score=round(match.match_confidence, 3),
                market_conditions=market_conditions,
                news_impact=news_impact,
                volume_profile_context={},
            )

            # Валидируем сигнал
            if validate_signal_data(signal.__dict__):
                return signal
            else:
                logger.warning(f"⚠️ Созданный сигнал не прошёл валидацию для {symbol}")
                return None

        except Exception as e:
            logger.error(f"❌ Ошибка создания сигнала: {e}")
            return None

    def _create_vetoed_signals(
        self, symbol: str, veto_result: VetoAnalysisResult
    ) -> List[EnhancedTradingSignal]:
        """Создание заблокированных veto сигналов для информации"""
        try:
            if not veto_result.active_vetos:
                return []

            # Создаём информационный сигнал о блокировке
            primary_veto = veto_result.active_vetos[0]

            vetoed_signal = EnhancedTradingSignal(
                symbol=symbol,
                side="NONE",
                scenario_id="veto_block",
                status=SignalStatusEnum.VETOED,
                price_entry=0.0,
                sl=0.0,
                tp1=0.0,
                tp2=0.0,
                tp3=0.0,
                rr1=0.0,
                rr2=0.0,
                rr3=0.0,
                timestamp=current_epoch_ms(),
                indicators={
                    "risk_score": veto_result.risk_score,
                    "market_stability": veto_result.market_stability,
                },
                reason=f"VETO: {primary_veto.message}",
                veto_reasons=[primary_veto.reason],
                level=SignalLevelEnum.T3,
                confidence_score=0.0,
                market_conditions={},
                news_impact={},
                volume_profile_context={},
            )

            return [vetoed_signal]

        except Exception as e:
            logger.error(f"❌ Ошибка создания vetoed signals: {e}")
            return []

    async def _apply_filters(
        self,
        signal: EnhancedTradingSignal,
        symbol: str,
        market_data: Dict,
        technical: TechnicalAnalysis,
    ) -> Tuple[bool, str]:
        """
        Применение всех фильтров к сигналу

        Args:
            signal: Сигнал для проверки
            symbol: Торговая пара
            market_data: Рыночные данные
            technical: Технический анализ

        Returns:
            (is_valid, reason) - прошёл ли фильтры и причина
        """
        try:
            # Подготовка данных для фильтров
            ticker = market_data.get("ticker", {})
            current_price = safe_float(ticker.get("last_price", 0))

            # Получаем orderbook data
            orderbook_data = market_data.get("orderbook", {})
            bids = orderbook_data.get("bids", [])
            asks = orderbook_data.get("asks", [])

            # Рассчитываем orderbook imbalance
            orderbook_imbalance = None
            if bids and asks:
                bid_volume = sum([float(bid[1]) for bid in bids[:20]])
                ask_volume = sum([float(ask[1]) for ask in asks[:20]])
                total = bid_volume + ask_volume

                if total > 0:
                    orderbook_imbalance = ((bid_volume - ask_volume) / total) * 100

            # Получаем candle data
            klines_data = market_data.get("klines", {})
            candles = klines_data.get("candles", [])
            last_candle = {}

            if candles:
                last_candle_data = candles[-1]
                last_candle = {
                    "open": safe_float(last_candle_data.get("open", 0)),
                    "high": safe_float(last_candle_data.get("high", 0)),
                    "low": safe_float(last_candle_data.get("low", 0)),
                    "close": safe_float(last_candle_data.get("close", 0)),
                    "volume": safe_float(last_candle_data.get("volume", 0)),
                }

            # Подготовка market_data для фильтров
            filter_market_data = {
                "orderbook": {
                    "imbalance": orderbook_imbalance,
                    "bids": bids,
                    "asks": asks,
                },
                "volume_1m": last_candle.get("volume", 0),
                "avg_volume_24h": (
                    safe_float(ticker.get("volume_24h", 0)) / 1440
                    if ticker.get("volume_24h")
                    else 0
                ),
                "last_candle": last_candle,
                "large_trades": [],
            }

            # Подготовка signal_dict для фильтров
            signal_dict = {
                "symbol": symbol,
                "direction": signal.side,
                "entry": signal.price_entry,
                "tp1": signal.tp1,
                "tp2": signal.tp2,
                "tp3": signal.tp3,
                "sl": signal.sl,
                "score": signal.confidence_score * 100,
                "risk_reward": signal.rr1,
            }

            # ========== 1. Multi-TF Filter (BLOCKING) ==========
            if self.multi_tf_filter:
                logger.info(f"🔍 Применение Multi-TF Filter для {symbol}...")

                mtf_valid, mtf_trends, mtf_reason = await self.multi_tf_filter.validate(
                    symbol=symbol,
                    direction=signal.side,
                    timeframes=["1h", "4h", "1d"],
                    min_agreement=2,
                )

                if not mtf_valid:
                    logger.warning(
                        f"❌ {symbol}: Multi-TF Filter отклонил сигнал: {mtf_reason}"
                    )
                    return (False, f"Multi-TF Filter: {mtf_reason}")
                else:
                    logger.info(f"✅ {symbol}: Multi-TF Filter пройден: {mtf_reason}")
                    logger.info(f"   📊 MTF Тренды: {mtf_trends}")

                    # Увеличиваем confidence за согласование TF
                    signal.confidence_score = min(1.0, signal.confidence_score + 0.1)

                    # Сохраняем MTF информацию в сигнал
                    signal.market_conditions["mtf_trends"] = mtf_trends
                    signal.market_conditions["mtf_alignment"] = mtf_reason

            # ========== 2. Confirm Filter (NON-BLOCKING) ==========
            if self.confirm_filter:
                logger.info(f"🔍 Применение Confirm Filter для {symbol}...")

                # ✅ validate() теперь возвращает dict с penalty
                result = await self.confirm_filter.validate(
                    symbol=symbol,
                    direction=signal.side,
                    market_data=filter_market_data,
                    signal_data=signal_dict,
                )

                penalty = result.get("confidence_penalty", 0)
                warnings = result.get("warnings", [])

                # Применяем штраф к confidence
                original_confidence = signal.confidence_score
                signal.confidence_score = max(
                    0, signal.confidence_score - (penalty / 100)
                )

                # Логирование
                if penalty > 0:
                    logger.warning(
                        f"⚠️ {symbol}: Confirm Filter снизил confidence "
                        f"{original_confidence:.2f} → {signal.confidence_score:.2f} (-{penalty}%)"
                    )
                    for warn in warnings:
                        logger.warning(f"  └─ {warn}")
                else:
                    logger.info(f"✅ {symbol}: Confirm Filter OK (0% penalty)")

                # Сохраняем детали в сигнал
                signal.market_conditions["confirm_filter_penalty"] = penalty
                signal.market_conditions["confirm_filter_warnings"] = warnings

            # ========== 3. Cluster Analysis (NON-BLOCKING) ==========
            if hasattr(self.bot, "cluster_detector") and self.bot.cluster_detector:
                try:
                    logger.info(f"🔍 Применение Cluster Analysis для {symbol}...")

                    cluster_score = await self.bot.cluster_detector.get_cluster_score(
                        symbol=symbol, direction=signal.side
                    )

                    logger.info(f"   📊 Cluster Score: {cluster_score:.2f}")

                    if cluster_score > 0.5:
                        signal.confidence_score = min(
                            1.0, signal.confidence_score + (cluster_score * 0.14)
                        )
                        logger.info(
                            f"✅ {symbol}: Cluster Analysis пройден, новый confidence: {signal.confidence_score:.2f}"
                        )
                        signal.market_conditions["cluster_score"] = cluster_score
                    else:
                        logger.warning(
                            f"⚠️ {symbol}: Низкий Cluster Score: {cluster_score:.2f}"
                        )

                except Exception as e:
                    logger.warning(f"⚠️ Ошибка Cluster Analysis для {symbol}: {e}")
            else:
                logger.debug(f"⚠️ Cluster Detector не доступен для {symbol}")

            # ✅ Все фильтры пройдены
            logger.info(f"🎯 {symbol}: Все фильтры успешно пройдены!")
            return (True, "All filters passed")

        except Exception as e:
            logger.error(f"❌ Ошибка применения фильтров: {e}", exc_info=True)
            # В случае ошибки пропускаем сигнал (безопасная стратегия)
            return (True, f"Filters skipped due to error: {e}")

    async def _filter_and_rank_signals(
        self, signals: List[EnhancedTradingSignal], market_data: Dict
    ) -> List[EnhancedTradingSignal]:
        """Фильтрация и ранжирование сигналов"""
        try:
            if not signals:
                return []

            # Исключаем заблокированные сигналы из основной фильтрации
            vetoed_signals = [s for s in signals if s.status == SignalStatusEnum.VETOED]
            active_signals = [s for s in signals if s.status != SignalStatusEnum.VETOED]

            # Фильтруем активные сигналы
            filtered_signals = []

            for signal in active_signals:
                # Минимальный RR фильтр
                if signal.rr1 >= MIN_RR_RATIO:
                    filtered_signals.append(signal)

            # Ранжируем по комплексной оценке
            ranked_signals = self._rank_signals_by_quality(filtered_signals)

            # Ограничиваем количество сигналов на символ
            max_signals = self.signal_settings["max_signals_per_symbol"]
            final_signals = ranked_signals[:max_signals]

            # Добавляем vetoed сигналы в конец для информации
            final_signals.extend(vetoed_signals)

            return final_signals

        except Exception as e:
            logger.error(f"❌ Ошибка фильтрации сигналов: {e}")
            return signals

    def _rank_signals_by_quality(
        self, signals: List[EnhancedTradingSignal]
    ) -> List[EnhancedTradingSignal]:
        """Ранжирование сигналов по качеству"""
        try:

            def calculate_quality_score(signal: EnhancedTradingSignal) -> float:
                score_components = []

                # Уверенность совпадения сценария
                score_components.append(signal.confidence_score * 0.4)

                # R/R соотношение (нормализованное)
                rr_score = min(1.0, signal.rr1 / 3.0)  # Нормализуем к RR=3
                score_components.append(rr_score * 0.3)

                # Стабильность рынка
                market_stability = signal.market_conditions.get("market_stability", 0.5)
                score_components.append(market_stability * 0.2)

                # Уровень сигнала
                level_scores = {
                    SignalLevelEnum.T1: 1.0,
                    SignalLevelEnum.T2: 0.8,
                    SignalLevelEnum.T3: 0.6,
                }
                score_components.append(level_scores.get(signal.level, 0.6) * 0.1)

                return sum(score_components)

            # Рассчитываем качество и сортируем
            signal_quality_pairs = [
                (signal, calculate_quality_score(signal)) for signal in signals
            ]
            signal_quality_pairs.sort(key=lambda x: x[1], reverse=True)

            return [signal for signal, quality in signal_quality_pairs]

        except Exception as e:
            logger.error(f"❌ Ошибка ранжирования сигналов: {e}")
            return signals

    def _update_generation_stats(
        self, signals: List[EnhancedTradingSignal], matches: List[ScenarioMatch]
    ):
        """Обновление статистики генерации"""
        try:
            self.generation_stats["total_generated"] += len(signals)

            for signal in signals:
                if signal.status == SignalStatusEnum.DEAL:
                    self.generation_stats["deal_signals"] += 1
                elif signal.status == SignalStatusEnum.RISKY_ENTRY:
                    self.generation_stats["risky_signals"] += 1
                elif signal.status == SignalStatusEnum.VETOED:
                    self.generation_stats["vetoed_signals"] += 1

            # Обновляем среднюю уверенность
            active_signals = [s for s in signals if s.status != SignalStatusEnum.VETOED]
            if active_signals:
                confidences = [s.confidence_score for s in active_signals]
                current_total = self.generation_stats["total_generated"]
                current_avg = self.generation_stats["avg_confidence"]

                new_avg = (
                    (current_avg * (current_total - len(active_signals)))
                    + sum(confidences)
                ) / current_total
                self.generation_stats["avg_confidence"] = round(new_avg, 3)

            # Статистика по сценариям
            for match in matches:
                self.generation_stats["scenarios_matched"][match.scenario_id] += 1

        except Exception as e:
            logger.error(f"❌ Ошибка обновления статистики генерации: {e}")

    def get_generator_stats(self) -> Dict[str, Any]:
        """Получение статистики генератора"""
        try:
            return {
                "generation_stats": dict(self.generation_stats),
                "signal_settings": self.signal_settings.copy(),
                "technical_cache_size": len(self.technical_cache),
                "price_history_symbols": len(self.price_history),
                "most_matched_scenario": (
                    max(
                        self.generation_stats["scenarios_matched"],
                        key=self.generation_stats["scenarios_matched"].get,
                    )
                    if self.generation_stats["scenarios_matched"]
                    else None
                ),
            }
        except Exception as e:
            return {"error": str(e)}


# Экспорт классов
__all__ = [
    "AdvancedSignalGenerator",
    "ScenarioMatch",
    "TechnicalAnalysis",
]
