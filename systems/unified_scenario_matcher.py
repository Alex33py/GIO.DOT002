# -*- coding: utf-8 -*-
"""
Enhanced Unified Scenario Matcher v2.0
Продвинутый матчер сценариев с поддержкой market regime detection
"""

import json
import os
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from pathlib import Path
from config.settings import logger, SCENARIOS_DIR, DATA_DIR
from systems.market_regime_detector import MarketRegimeDetector


class EnhancedScenarioMatcher:
    """
    Улучшенный матчер сценариев с:
    - Автоматическим определением рыночного режима
    - Детальной валидацией сигналов
    - Расчётом уверенности
    - Отслеживанием фазы рынка
    """

    def __init__(self):
        """Инициализация матчера"""
        self.scenarios = []
        self.strategies = {}
        self.regime_detector = MarketRegimeDetector()

        # Загружаем данные
        self._load_scenarios()
        self._load_strategies()

        logger.info("✅ EnhancedScenarioMatcher v2.0 инициализирован")


    def _load_scenarios(self):
        """Загрузка сценариев из JSON"""
        try:
            scenarios_path = Path(DATA_DIR) / "scenarios" / "gio_scenarios_v2.json"

            if not scenarios_path.exists():
                logger.error(f"❌ Файл сценариев не найден: {scenarios_path}")
                return

            with open(scenarios_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.scenarios = data.get("scenarios", [])
            logger.info(f"✅ Загружено {len(self.scenarios)} сценариев")

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки сценариев: {e}")
            self.scenarios = []


    def _load_strategies(self):
        """Загрузка стратегий из JSON"""
        try:
            strategies_path = Path(DATA_DIR) / "strategies" / "strategy_extensions_v1.1.json"

            if not strategies_path.exists():
                logger.error(f"❌ Файл стратегий не найден: {strategies_path}")
                return

            with open(strategies_path, 'r', encoding='utf-8') as f:
                self.strategies = json.load(f)

            logger.info("✅ Загружены правила стратегий")

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки стратегий: {e}")
            self.strategies = {}


    def match_scenario(
        self,
        symbol: str,
        market_data: Dict,
        indicators: Dict,
        mtf_trends: Dict,
        volume_profile: Dict,
        news_sentiment: Dict,
        veto_checks: Dict
    ) -> Optional[Dict]:
        """
        Главный метод: найти подходящий сценарий

        Args:
            symbol: Торговая пара
            market_data: Рыночные данные (price, volume, candles, etc.)
            indicators: Технические индикаторы (RSI, MACD, ADX, etc.)
            mtf_trends: Тренды по таймфреймам (1H, 4H, 1D)
            volume_profile: Volume Profile данные (POC, VAH, VAL)
            news_sentiment: Настроения новостей
            veto_checks: Veto условия

        Returns:
            Dict с параметрами сигнала или None
        """
        try:
            # 1. Собираем все метрики в единый dict
            metrics = self._build_metrics(
                market_data, indicators, mtf_trends,
                volume_profile, news_sentiment
            )

            # 2. Определяем рыночный режим
            market_regime = self.regime_detector.detect(metrics)
            logger.info(f"📊 {symbol}: Рыночный режим = {market_regime}")

            # 3. Выбираем подходящие стратегии для режима
            suitable_strategies = self._get_suitable_strategies(market_regime)
            logger.debug(f"🎯 Подходящие стратегии: {suitable_strategies}")

            # 4. Ищем лучший сценарий
            best_match = self._find_best_scenario(
                symbol, metrics, suitable_strategies, mtf_trends
            )

            if not best_match:
                return None

            # 5. Валидация сценария
            validation = self._validate_scenario(best_match, metrics, veto_checks)

            # 6. Расчёт уверенности
            confidence = self._calculate_confidence(best_match, metrics, validation)

            # 7. Построение итогового сигнала
            signal = self._build_signal(
                best_match, metrics, market_regime,
                confidence, validation
            )

            return signal

        except Exception as e:
            logger.error(f"❌ Ошибка match_scenario для {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _build_metrics(
        self,
        market_data: Dict,
        indicators: Dict,
        mtf_trends: Dict,
        volume_profile: Dict,
        news_sentiment: Dict
    ) -> Dict:
        """Объединить все метрики в один dict"""
        metrics = {}

        # Market data
        metrics.update({
            "price": market_data.get("close", 0),
            "volume": market_data.get("volume", 0),
            "candles": market_data.get("candles", [])
        })

        # Indicators
        metrics.update(indicators)

        # MTF trends
        metrics["trend_1h"] = mtf_trends.get("1H", "neutral")
        metrics["trend_4h"] = mtf_trends.get("4H", "neutral")
        metrics["trend_1d"] = mtf_trends.get("1D", "neutral")

        # Volume Profile
        metrics["poc"] = volume_profile.get("poc", metrics["price"])
        metrics["vah"] = volume_profile.get("vah", metrics["price"] * 1.01)
        metrics["val"] = volume_profile.get("val", metrics["price"] * 0.99)
        metrics["vwap"] = volume_profile.get("vwap", metrics["price"])

        # News sentiment
        metrics["news_score"] = news_sentiment.get("overall_score", 0)
        metrics["news_sentiment"] = news_sentiment.get("overall", "neutral")

        return metrics


    def _get_suitable_strategies(self, market_regime: str) -> List[str]:
        """Получить подходящие стратегии для режима"""
        selector = self.strategies.get("strategy_selector", {})
        regime_map = selector.get("market_regime", {})
        all_weather = selector.get("all_weather", [])

        strategies = regime_map.get(market_regime, [])
        strategies.extend(all_weather)

        return list(set(strategies))  # Убираем дубликаты


    def _find_best_scenario(
        self,
        symbol: str,
        metrics: Dict,
        suitable_strategies: List[str],
        mtf_trends: Dict
    ) -> Optional[Dict]:
        """Найти лучший подходящий сценарий"""

        matches = []

        for scenario in self.scenarios:
            # Проверяем что стратегия подходит
            if scenario["strategy"] not in suitable_strategies:
                continue

            # Проверяем MTF условия
            if not self._check_mtf_conditions(scenario, mtf_trends):
                continue

            # Проверяем triggers
            trigger_score = self._evaluate_triggers(scenario, metrics)

            if trigger_score >= scenario["triggers"].get("min_score", 0.7):
                matches.append({
                    "scenario": scenario,
                    "score": trigger_score
                })

        if not matches:
            return None

        # Возвращаем сценарий с лучшим score
        best = max(matches, key=lambda x: x["score"])
        logger.info(f"🎯 {symbol}: Найден сценарий {best['scenario']['id']} (score={best['score']:.2f})")

        return best["scenario"]


    def _check_mtf_conditions(self, scenario: Dict, mtf_trends: Dict) -> bool:
        """Проверка Multi-TimeFrame условий"""
        mtf = scenario.get("mtf", {})
        conditions = mtf.get("conditions", {})
        required_alignment = mtf.get("required_alignment", 2)

        aligned = 0

        for tf, expected_trends in conditions.items():
            actual_trend = mtf_trends.get(tf, "neutral")

            if actual_trend in expected_trends:
                aligned += 1

        return aligned >= required_alignment


    def _evaluate_triggers(self, scenario: Dict, metrics: Dict) -> float:
        """Оценка triggers сценария"""
        triggers = scenario.get("triggers", {})
        conditions = triggers.get("conditions", {})

        total_score = 0.0

        for condition, weight in conditions.items():
            if self._check_condition(condition, metrics):
                total_score += float(weight)

        return total_score


    def _check_condition(self, condition: str, metrics: Dict) -> bool:
        """Проверка одного условия"""
        try:
            # Простые boolean условия
            if condition in metrics:
                return bool(metrics[condition])

            # Условия с операторами (>= <= == etc)
            if ">=" in condition:
                left, right = condition.split(">=")
                left_val = self._resolve_value(left.strip(), metrics)
                right_val = self._resolve_value(right.strip(), metrics)
                return left_val is not None and right_val is not None and left_val >= right_val

            elif "<=" in condition:
                left, right = condition.split("<=")
                left_val = self._resolve_value(left.strip(), metrics)
                right_val = self._resolve_value(right.strip(), metrics)
                return left_val is not None and right_val is not None and left_val <= right_val

            elif "==" in condition:
                left, right = condition.split("==")
                left_val = self._resolve_value(left.strip(), metrics)
                right_val = right.strip()
                return str(left_val) == right_val

            return False

        except Exception as e:
            logger.debug(f"⚠️ Ошибка проверки условия '{condition}': {e}")
            return False


    def _resolve_value(self, expr: str, metrics: Dict):
        """Вычислить значение выражения"""
        # Простое значение из metrics
        if expr in metrics:
            return metrics[expr]

        # Arithmetic expression (volume_ma20*1.5)
        if "*" in expr:
            parts = expr.split("*")
            val = metrics.get(parts[0].strip())
            multiplier = float(parts[1].strip())
            return val * multiplier if val is not None else None

        # Число
        try:
            return float(expr)
        except:
            return None


    def _validate_scenario(
        self,
        scenario: Dict,
        metrics: Dict,
        veto_checks: Dict
    ) -> Dict:
        """Валидация сценария"""
        validation = {
            "basic_conditions": True,
            "volume_confirmation": metrics.get("volume", 0) >= metrics.get("volume_ma20", 0),
            "cluster_orderflow": metrics.get("cluster_imbalance", 0) > 1,
            "multi_timeframe_alignment": True,  # Уже проверено в _check_mtf_conditions
            "news_sentiment": abs(metrics.get("news_score", 0)) < 0.3,
            "veto_passed": not any(veto_checks.values())
        }

        return validation

    def _calculate_confidence(
        self,
        scenario: Dict,
        metrics: Dict,
        validation: Dict
    ) -> str:
        """Расчёт уверенности в сигнале"""

        base_confidence = scenario.get("confidence_base", "medium")

        # Подсчитываем validation score
        passed = sum(1 for v in validation.values() if v)
        total = len(validation)
        validation_ratio = passed / total

        # Бустеры (с защитой от строк)
        try:
            adx = float(metrics.get("adx", 0))
            volume = float(metrics.get("volume", 1))
            volume_ma20 = float(metrics.get("volume_ma20", 1))
            volume_ratio = volume / max(volume_ma20, 1)
        except (ValueError, TypeError):
            adx = 0
            volume_ratio = 1.0

        # Логика
        if validation_ratio >= 0.9 and adx > 30 and volume_ratio > 2.0:
            return "high"
        elif validation_ratio >= 0.7:
            return "medium"
        else:
            return "low"


    def _build_signal(
        self,
        scenario: Dict,
        metrics: Dict,
        market_regime: str,
        confidence: str,
        validation: Dict
    ) -> Dict:
        """Построение финального сигнала"""

        price = metrics["price"]
        tactic = scenario["tactic"]

        # Рассчитываем TP/SL на основе tactic
        entry_price = price
        sl_distance = self._calculate_sl_distance(tactic["sl"], metrics)

        if scenario["side"] == "long":
            stop_loss = entry_price - sl_distance
            tp1 = entry_price * (1 + float(tactic["tp1"]["value"]) / 100)
            tp2 = entry_price * (1 + float(tactic["tp2"]["value"]) / 100)

            # TP3 может быть числом или trailing - обрабатываем оба случая
            if "value" in tactic["tp3"]:
                tp3_val = tactic["tp3"]["value"]
                if isinstance(tp3_val, (int, float)):
                    tp3 = entry_price * (1 + float(tp3_val) / 100)
                else:
                    # Если это trailing (например "atr*0.8"), используем расширенный TP2
                    tp3 = tp2 * 1.5
            else:
                tp3 = tp2 * 1.5
        else:
            stop_loss = entry_price + sl_distance
            tp1 = entry_price * (1 - float(tactic["tp1"]["value"]) / 100)
            tp2 = entry_price * (1 - float(tactic["tp2"]["value"]) / 100)

            # TP3 может быть числом или trailing - обрабатываем оба случая
            if "value" in tactic["tp3"]:
                tp3_val = tactic["tp3"]["value"]
                if isinstance(tp3_val, (int, float)):
                    tp3 = entry_price * (1 - float(tp3_val) / 100)
                else:
                    # Если это trailing (например "atr*0.8"), используем сокращённый TP2
                    tp3 = tp2 * 0.85
            else:
                tp3 = tp2 * 0.85


        return {
            "signal": True,
            "scenario_id": scenario["id"],
            "scenario_name": scenario["name"],
            "strategy": scenario["strategy"],
            "phase": scenario.get("phase", "unknown"),
            "side": scenario["side"],
            "direction": "LONG" if scenario["side"] == "long" else "SHORT",

            "entry_price": entry_price,
            "stop_loss": stop_loss,
            "tp1": tp1,
            "tp2": tp2,
            "tp3": tp3,

            "confidence": confidence,
            "market_regime": market_regime,
            "risk_profile": scenario["risk_profile"],
            "tactic_name": tactic["name"],
            "position_size": tactic.get("position_size", 1.0),

            "validation": validation,
            "influenced_metrics": {
                "adx": metrics.get("adx"),
                "volume_ratio": self._safe_volume_ratio(metrics),
                "trend_1h": metrics.get("trend_1h"),
                "trend_4h": metrics.get("trend_4h")
            },


            "status": "active",
            "timestamp": datetime.now()
        }

    def _calculate_sl_distance(self, sl_config: Dict, metrics: Dict) -> float:
        """Рассчитать расстояние для SL"""
        sl_type = sl_config.get("type", "fixed")
        sl_value = sl_config.get("value", "1.5%")

        price = metrics["price"]
        atr = metrics.get("atr", price * 0.02)

        if sl_type == "dynamic":
            # Парсим "max(1.8%, atr*1.0)" или подобные выражения
            if isinstance(sl_value, str) and "max" in sl_value:
                try:
                    # Извлекаем проценты и ATR множитель
                    # Формат: "max(X.X%, atr*Y.Y)"
                    import re
                    percent_match = re.search(r'(\d+\.?\d*)%', sl_value)
                    atr_match = re.search(r'atr\*(\d+\.?\d*)', sl_value)

                    percent_val = float(percent_match.group(1)) / 100 if percent_match else 0.015
                    atr_multiplier = float(atr_match.group(1)) if atr_match else 1.0

                    percent_sl = price * percent_val
                    atr_sl = atr * atr_multiplier

                    return max(percent_sl, atr_sl)

                except Exception as e:
                    logger.debug(f"⚠️ Ошибка парсинга SL value '{sl_value}': {e}")
                    return price * 0.015
            else:
                # Fallback для других dynamic типов
                return price * 0.015

        elif sl_type == "fixed":
            # Для fixed - просто процент
            try:
                if isinstance(sl_value, str) and "%" in sl_value:
                    percent = float(sl_value.replace("%", "")) / 100
                    return price * percent
                else:
                    return price * 0.015
            except:
                return price * 0.015

        else:
            # Fallback для остальных типов (level, trailing, etc)
            return price * 0.015


    def _safe_volume_ratio(self, metrics: Dict) -> float:
        """Безопасный расчёт volume ratio"""
        try:
            volume = float(metrics.get("volume", 1))
            volume_ma20 = float(metrics.get("volume_ma20", 1))
            return volume / max(volume_ma20, 1)
        except (ValueError, TypeError):
            return 1.0



# Экспорт
__all__ = ["EnhancedScenarioMatcher"]
