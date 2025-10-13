import logging
from typing import Dict, List, Optional
from indicators.technical import AdvancedTechnicalIndicators
from models.data_classes import TrendDirectionEnum

logger = logging.getLogger(__name__)


class MultiTimeframeAnalyzer:
    """Мультитаймфрейм анализ с весовыми коэффициентами"""

    def __init__(self):
        self.timeframe_weights = {
            "1m": 0.1,
            "5m": 0.2,
            "15m": 0.3,
            "1h": 0.4,
            "4h": 0.6,
            "1d": 0.8
        }
        self.technical_analyzer = AdvancedTechnicalIndicators()

    async def analyze_multiple_timeframes(self, candles_data: Dict[str, List[Dict]]) -> Dict[str, any]:
        """Анализ множественных таймфреймов с консенсусным подходом"""
        try:
            if not candles_data:
                return {"error": "No candles data provided"}

            timeframe_analysis = {}
            consensus_scores = {
                "bullish_score": 0.0,
                "bearish_score": 0.0,
                "neutral_score": 0.0,
                "total_weight": 0.0
            }

            # Анализируем каждый таймфрейм
            for timeframe, candles in candles_data.items():
                if not candles or len(candles) < 50:
                    continue

                tf_analysis = await self._analyze_single_timeframe(timeframe, candles)
                timeframe_analysis[timeframe] = tf_analysis

                # Добавляем к консенсусу с весовым коэффициентом
                weight = self.timeframe_weights.get(timeframe, 0.1)

                if tf_analysis.get("trend_direction"):
                    if tf_analysis["trend_direction"] == TrendDirectionEnum.BULLISH.value:
                        consensus_scores["bullish_score"] += weight * tf_analysis.get("trend_strength", 0.5)
                    elif tf_analysis["trend_direction"] == TrendDirectionEnum.BEARISH.value:
                        consensus_scores["bearish_score"] += weight * tf_analysis.get("trend_strength", 0.5)
                    else:
                        consensus_scores["neutral_score"] += weight * 0.5

                consensus_scores["total_weight"] += weight

            # Нормализуем консенсусные оценки
            if consensus_scores["total_weight"] > 0:
                for key in ["bullish_score", "bearish_score", "neutral_score"]:
                    consensus_scores[key] /= consensus_scores["total_weight"]

            # Определяем общий консенсус
            consensus_trend = self._determine_consensus_trend(consensus_scores)

            # Рассчитываем уровни поддержки и сопротивления
            key_levels = self._calculate_multi_timeframe_levels(timeframe_analysis)

            # Анализ дивергенций между таймфреймами
            divergences = self._detect_timeframe_divergences(timeframe_analysis)

            return {
                "timeframe_analysis": timeframe_analysis,
                "consensus": {
                    "trend": consensus_trend,
                    "scores": consensus_scores,
                    "confidence": self._calculate_consensus_confidence(consensus_scores)
                },
                "key_levels": key_levels,
                "divergences": divergences,
                "analysis_timestamp": self._get_current_timestamp()
            }

        except Exception as e:
            logger.error(f"Ошибка мультитаймфрейм анализа: {e}")
            return {"error": str(e)}

    async def _analyze_single_timeframe(self, timeframe: str, candles: List[Dict]) -> Dict[str, any]:
        """Анализ одного таймфрейма"""
        try:
            # Рассчитываем технические индикаторы
            indicators = self.technical_analyzer.calculate_all_indicators(candles)

            # Анализируем тренд
            trend_analysis = self._analyze_trend(indicators, candles)

            # Анализируем моментум
            momentum_analysis = self._analyze_momentum(indicators)

            # Анализируем волатильность
            volatility_analysis = self._analyze_volatility(indicators, candles)

            # Определяем силу сигнала
            signal_strength = self._calculate_signal_strength(trend_analysis, momentum_analysis, volatility_analysis)

            return {
                "timeframe": timeframe,
                "indicators": indicators,
                "trend_direction": trend_analysis["direction"],
                "trend_strength": trend_analysis["strength"],
                "momentum": momentum_analysis,
                "volatility": volatility_analysis,
                "signal_strength": signal_strength,
                "key_levels": {
                    "support": indicators.get("lower"),
                    "resistance": indicators.get("upper"),
                    "middle": indicators.get("middle")
                }
            }

        except Exception as e:
            logger.error(f"Ошибка анализа таймфрейма {timeframe}: {e}")
            return {"timeframe": timeframe, "error": str(e)}

    def _analyze_trend(self, indicators: Dict, candles: List[Dict]) -> Dict[str, any]:
        """Анализ тренда на основе индикаторов"""
        try:
            trend_signals = []

            # MACD анализ
            macd = indicators.get("macd")
            macd_signal = indicators.get("signal_line")
            if macd is not None and macd_signal is not None:
                if macd > macd_signal:
                    trend_signals.append(("bullish", 0.7))
                else:
                    trend_signals.append(("bearish", 0.7))

            # Moving Average анализ (на основе цены относительно Bollinger Middle)
            current_price = indicators.get("current_price")
            bb_middle = indicators.get("middle")
            if current_price and bb_middle:
                if current_price > bb_middle:
                    trend_signals.append(("bullish", 0.5))
                else:
                    trend_signals.append(("bearish", 0.5))

            # Определяем общий тренд
            if not trend_signals:
                return {"direction": TrendDirectionEnum.NEUTRAL.value, "strength": 0.0}

            bullish_weight = sum(weight for signal, weight in trend_signals if signal == "bullish")
            bearish_weight = sum(weight for signal, weight in trend_signals if signal == "bearish")
            neutral_weight = sum(weight for signal, weight in trend_signals if signal == "neutral")

            total_weight = bullish_weight + bearish_weight + neutral_weight

            if total_weight == 0:
                return {"direction": TrendDirectionEnum.NEUTRAL.value, "strength": 0.0}

            bullish_pct = bullish_weight / total_weight
            bearish_pct = bearish_weight / total_weight
            neutral_pct = neutral_weight / total_weight

            if bullish_pct > bearish_pct and bullish_pct > neutral_pct:
                direction = TrendDirectionEnum.BULLISH.value
                strength = bullish_pct
            elif bearish_pct > neutral_pct:
                direction = TrendDirectionEnum.BEARISH.value
                strength = bearish_pct
            else:
                direction = TrendDirectionEnum.NEUTRAL.value
                strength = neutral_pct

            return {
                "direction": direction,
                "strength": round(strength, 3),
                "signals_count": len(trend_signals),
                "bullish_weight": round(bullish_pct, 3),
                "bearish_weight": round(bearish_pct, 3),
                "neutral_weight": round(neutral_pct, 3)
            }

        except Exception as e:
            logger.error(f"Ошибка анализа тренда: {e}")
            return {"direction": TrendDirectionEnum.NEUTRAL.value, "strength": 0.0}

    def _analyze_momentum(self, indicators: Dict) -> Dict[str, any]:
        """Анализ моментума"""
        try:
            momentum_signals = []

            # RSI анализ
            rsi = indicators.get("rsi")
            if rsi:
                if rsi < 30:
                    momentum_signals.append(("oversold", 0.8))
                elif rsi > 70:
                    momentum_signals.append(("overbought", 0.8))
                elif 40 <= rsi <= 60:
                    momentum_signals.append(("neutral", 0.5))
                elif rsi < 50:
                    momentum_signals.append(("bearish", 0.3))
                else:
                    momentum_signals.append(("bullish", 0.3))

            # Stochastic анализ
            stoch_k = indicators.get("percent_k")
            stoch_d = indicators.get("percent_d")
            if stoch_k and stoch_d:
                if stoch_k < 20 and stoch_d < 20:
                    momentum_signals.append(("oversold", 0.6))
                elif stoch_k > 80 and stoch_d > 80:
                    momentum_signals.append(("overbought", 0.6))
                elif stoch_k > stoch_d:
                    momentum_signals.append(("bullish", 0.4))
                else:
                    momentum_signals.append(("bearish", 0.4))

            return {
                "signals": momentum_signals,
                "is_oversold": any(signal[0] == "oversold" for signal in momentum_signals),
                "is_overbought": any(signal[0] == "overbought" for signal in momentum_signals),
                "strength": len([s for s in momentum_signals if s[1] > 0.5])
            }

        except Exception as e:
            logger.error(f"Ошибка анализа моментума: {e}")
            return {"signals": [], "is_oversold": False, "is_overbought": False, "strength": 0}

    def _analyze_volatility(self, indicators: Dict, candles: List[Dict]) -> Dict[str, any]:
        """Анализ волатильности"""
        try:
            volatility_data = {}

            # ATR для измерения волатильности
            atr = indicators.get("atr")
            if atr and candles:
                current_price = candles[-1]["close"]
                atr_percentage = (atr / current_price) * 100
                volatility_data["atr_percentage"] = round(atr_percentage, 3)

                # Классификация волатильности
                if atr_percentage < 1.0:
                    volatility_data["level"] = "low"
                elif atr_percentage < 3.0:
                    volatility_data["level"] = "medium"
                else:
                    volatility_data["level"] = "high"

            # Bollinger Bands ширина
            bb_bandwidth = indicators.get("bandwidth")
            if bb_bandwidth:
                volatility_data["bb_bandwidth"] = round(bb_bandwidth, 3)

                # Сжатие или расширение
                if bb_bandwidth < 5.0:
                    volatility_data["bb_status"] = "squeeze"  # Сжатие
                elif bb_bandwidth > 20.0:
                    volatility_data["bb_status"] = "expansion"  # Расширение
                else:
                    volatility_data["bb_status"] = "normal"

            return volatility_data

        except Exception as e:
            logger.error(f"Ошибка анализа волатильности: {e}")
            return {}

    def _calculate_signal_strength(self, trend_analysis: Dict, momentum_analysis: Dict, volatility_analysis: Dict) -> float:
        """Расчет силы сигнала"""
        try:
            strength = 0.0

            # Сила тренда (40% веса)
            trend_strength = trend_analysis.get("strength", 0.0)
            strength += trend_strength * 0.4

            # Моментум (35% веса)
            momentum_strength = momentum_analysis.get("strength", 0) / 5.0  # Нормализуем
            strength += momentum_strength * 0.35

            # Волатильность (25% веса)
            volatility_level = volatility_analysis.get("level", "medium")
            if volatility_level == "medium":
                volatility_strength = 0.7  # Средняя волатильность лучше для торговли
            elif volatility_level == "high":
                volatility_strength = 0.5  # Высокая волатильность рискованна
            else:
                volatility_strength = 0.3  # Низкая волатильность скучна

            strength += volatility_strength * 0.25

            return round(min(strength, 1.0), 3)

        except Exception as e:
            logger.error(f"Ошибка расчета силы сигнала: {e}")
            return 0.0

    def _determine_consensus_trend(self, consensus_scores: Dict) -> str:
        """Определение консенсусного тренда"""
        try:
            bullish = consensus_scores.get("bullish_score", 0.0)
            bearish = consensus_scores.get("bearish_score", 0.0)
            neutral = consensus_scores.get("neutral_score", 0.0)

            # Требуем значительного превосходства для определения тренда
            if bullish > bearish * 1.5 and bullish > neutral:
                return TrendDirectionEnum.BULLISH.value
            elif bearish > bullish * 1.5 and bearish > neutral:
                return TrendDirectionEnum.BEARISH.value
            elif abs(bullish - bearish) < 0.1:
                return TrendDirectionEnum.MIXED.value
            else:
                return TrendDirectionEnum.NEUTRAL.value

        except Exception as e:
            logger.error(f"Ошибка определения консенсуса: {e}")
            return TrendDirectionEnum.NEUTRAL.value

    def _calculate_consensus_confidence(self, consensus_scores: Dict) -> float:
        """Расчет уверенности в консенсусном решении"""
        try:
            scores = [
                consensus_scores.get("bullish_score", 0.0),
                consensus_scores.get("bearish_score", 0.0),
                consensus_scores.get("neutral_score", 0.0)
            ]

            max_score = max(scores)
            min_score = min(scores)

            # Чем больше разброс, тем выше уверенность в лидирующем направлении
            confidence = (max_score - min_score) * max_score

            return round(min(confidence, 1.0), 3)

        except Exception as e:
            logger.error(f"Ошибка расчета уверенности: {e}")
            return 0.0

    def _calculate_multi_timeframe_levels(self, timeframe_analysis: Dict) -> Dict[str, any]:
        """Расчет ключевых уровней на основе мультитаймфрейм анализа"""
        try:
            all_supports = []
            all_resistances = []
            all_middles = []

            for tf, analysis in timeframe_analysis.items():
                if "key_levels" in analysis:
                    levels = analysis["key_levels"]
                    weight = self.timeframe_weights.get(tf, 0.1)

                    if levels.get("support"):
                        all_supports.append((levels["support"], weight))
                    if levels.get("resistance"):
                        all_resistances.append((levels["resistance"], weight))
                    if levels.get("middle"):
                        all_middles.append((levels["middle"], weight))

            # Находим weighted average уровни
            key_levels = {}

            if all_supports:
                weighted_support = sum(price * weight for price, weight in all_supports) / sum(weight for _, weight in all_supports)
                key_levels["support"] = round(weighted_support, 2)

            if all_resistances:
                weighted_resistance = sum(price * weight for price, weight in all_resistances) / sum(weight for _, weight in all_resistances)
                key_levels["resistance"] = round(weighted_resistance, 2)

            if all_middles:
                weighted_middle = sum(price * weight for price, weight in all_middles) / sum(weight for _, weight in all_middles)
                key_levels["middle"] = round(weighted_middle, 2)

            return key_levels

        except Exception as e:
            logger.error(f"Ошибка расчета мультитаймфрейм уровней: {e}")
            return {}

    def _detect_timeframe_divergences(self, timeframe_analysis: Dict) -> List[Dict]:
        """Обнаружение дивергенций между таймфреймами"""
        try:
            divergences = []

            # Сравниваем краткосрочные и долгосрочные таймфреймы
            short_term_tfs = ["1m", "5m", "15m"]
            long_term_tfs = ["1h", "4h", "1d"]

            short_trends = []
            long_trends = []

            for tf, analysis in timeframe_analysis.items():
                trend = analysis.get("trend_direction")
                if trend:
                    if tf in short_term_tfs:
                        short_trends.append(trend)
                    elif tf in long_term_tfs:
                        long_trends.append(trend)

            if short_trends and long_trends:
                # Проверяем на противоположные тренды
                short_bullish = short_trends.count(TrendDirectionEnum.BULLISH.value)
                short_bearish = short_trends.count(TrendDirectionEnum.BEARISH.value)
                long_bullish = long_trends.count(TrendDirectionEnum.BULLISH.value)
                long_bearish = long_trends.count(TrendDirectionEnum.BEARISH.value)

                if short_bullish > short_bearish and long_bearish > long_bullish:
                    divergences.append({
                        "type": "trend_divergence",
                        "description": "Краткосрочный бычий тренд против долгосрочного медвежьего",
                        "severity": "medium"
                    })
                elif short_bearish > short_bullish and long_bullish > long_bearish:
                    divergences.append({
                        "type": "trend_divergence",
                        "description": "Краткосрочный медвежий тренд против долгосрочного бычьего",
                        "severity": "medium"
                    })

            return divergences

        except Exception as e:
            logger.error(f"Ошибка обнаружения дивергенций: {e}")
            return []

    def _get_current_timestamp(self) -> int:
        """Получить текущий timestamp"""
        import time
        return int(time.time() * 1000)
