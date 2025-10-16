#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Scenario Matcher - Объединённая версия с полной функциональностью
"""

import os
import json
from typing import Dict, List, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
from config.settings import logger, DATA_DIR


class SignalStatus(Enum):
    """Статусы торговых сигналов"""

    DEAL = "deal"
    RISKY_ENTRY = "risky_entry"
    OBSERVATION = "observation"


@dataclass
class ScenarioMatch:
    """Результат сопоставления сценария"""

    scenario_id: int
    scenario_name: str
    score: float
    status: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    timestamp: str
    veto_warnings: List[str]


class UnifiedScenarioMatcher:
    """
    Объединённый Scenario Matcher с полной функциональностью:
    - Загрузка JSON сценариев
    - Проверка MTF, ExoCharts, News, CVD, Clusters, Triggers
    - Расчёт weighted score
    - Классификация: deal / risky_entry / observation
    """

    def __init__(
        self,
        scenarios_path: str = None,
        deal_threshold: float = 0.40,
        risky_threshold: float = 0.30,
        observation_threshold: float = 0.20,
    ):
        """
        Args:
            scenarios_path: Путь к JSON-файлу со сценариями (опционально)
            deal_threshold: Порог для статуса DEAL (50%)
            risky_threshold: Порог для статуса RISKY_ENTRY (40%)
            observation_threshold: Порог для статуса OBSERVATION (30%)
        """

        # === ЗАГРУЗКА ОБОИХ ФАЙЛОВ СЦЕНАРИЕВ ===
        self.scenarios = []

        # Пути к файлам
        v3_path = os.path.join(
            DATA_DIR, "scenarios", "gio_scenarios_100_with_features_v3.json"
        )
        v2_path = os.path.join(DATA_DIR, "scenarios", "gio_scenarios_v2.json")

        # Счётчики
        v3_count = 0
        v2_count = 0

        # 1. ЗАГРУЖАЕМ V3 (100 сценариев)
        try:
            if os.path.exists(v3_path):
                logger.info(f"📂 Загрузка v3 сценариев из: {v3_path}")
                with open(v3_path, "r", encoding="utf-8") as f:
                    v3_data = json.load(f)

                # Извлекаем сценарии
                if isinstance(v3_data, dict) and "scenarios" in v3_data:
                    v3_scenarios = v3_data["scenarios"]
                elif isinstance(v3_data, list):
                    v3_scenarios = v3_data
                else:
                    v3_scenarios = []

                # Добавляем к общему списку
                self.scenarios.extend(v3_scenarios)
                v3_count = len(v3_scenarios)
                logger.info(f"✅ Загружено {v3_count} сценариев из v3")
            else:
                logger.warning(f"⚠️ Файл v3 не найден: {v3_path}")

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки v3 сценариев: {e}")

        # 2. ЗАГРУЖАЕМ V2 (12 сценариев)
        try:
            if os.path.exists(v2_path):
                logger.info(f"📂 Загрузка v2 сценариев из: {v2_path}")
                with open(v2_path, "r", encoding="utf-8") as f:
                    v2_data = json.load(f)

                # Извлекаем сценарии
                if isinstance(v2_data, dict) and "scenarios" in v2_data:
                    v2_scenarios = v2_data["scenarios"]
                elif isinstance(v2_data, list):
                    v2_scenarios = v2_data
                else:
                    v2_scenarios = []

                # ВАЖНО: Изменяем ID сценариев v2, чтобы избежать конфликтов
                # SCN_001 → SCN_101, SCN_002 → SCN_102, и т.д.
                for scenario in v2_scenarios:
                    original_id = scenario.get("id", "")

                    # Парсим номер из ID (например, "SCN_001" → 1)
                    if original_id.startswith("SCN_"):
                        try:
                            scenario_num = int(original_id.split("_")[1])
                            # Добавляем 100 к номеру
                            new_id = f"SCN_{scenario_num + 100:03d}"
                            scenario["id"] = new_id

                            # Добавляем метку источника
                            scenario["source"] = "v2_detailed"

                        except (ValueError, IndexError):
                            # Если не удалось распарсить, оставляем как есть
                            scenario["source"] = "v2_detailed"

                # Добавляем к общему списку
                self.scenarios.extend(v2_scenarios)
                v2_count = len(v2_scenarios)
                logger.info(
                    f"✅ Загружено {v2_count} сценариев из v2 (ID: SCN_101-SCN_112)"
                )
            else:
                logger.warning(f"⚠️ Файл v2 не найден: {v2_path}")

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки v2 сценариев: {e}")

        # 3. ИТОГОВАЯ СТАТИСТИКА
        total_count = len(self.scenarios)

        if total_count == 0:
            logger.error("❌ НЕ ЗАГРУЖЕНО НИ ОДНОГО СЦЕНАРИЯ!")
        else:
            logger.info(
                f"✅ UnifiedScenarioMatcher инициализирован "
                f"({total_count} сценариев: {v3_count} v3 + {v2_count} v2, "
                f"пороги: deal={deal_threshold:.0%}, risky={risky_threshold:.0%})"
            )

        # Пороги классификации
        self.deal_threshold = deal_threshold
        self.risky_threshold = risky_threshold
        self.observation_threshold = observation_threshold

        # Сохраняем путь (для совместимости)
        self.scenarios_path = v3_path if v3_count > 0 else v2_path

    def load_scenarios(self, scenarios: Optional[List[Dict]] = None):
        """
        Загрузка сценариев из JSON или приём готового списка

        Args:
            scenarios: Готовый список сценариев (опционально)
        """
        try:
            # Если переданы готовые сценарии - используем их
            if scenarios is not None and isinstance(scenarios, list):
                self.scenarios = scenarios
                logger.info(f"✅ Получено {len(scenarios)} сценариев извне")
                return

            # Иначе - загружаем из JSON
            logger.info(f"🔍 Попытка загрузки сценариев из: {self.scenarios_path}")

            if not os.path.exists(self.scenarios_path):
                logger.error(f"❌ Файл сценариев не найден: {self.scenarios_path}")
                self.scenarios = []
                return

            with open(self.scenarios_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Проверка структуры JSON
            if isinstance(data, list):
                # JSON - это список сценариев
                self.scenarios = data
                logger.info(
                    f"✅ Загружено {len(self.scenarios)} сценариев из JSON (list)"
                )
            elif isinstance(data, dict) and "scenarios" in data:
                # JSON - это объект с ключом "scenarios"
                self.scenarios = data["scenarios"]
                logger.info(
                    f"✅ Загружено {len(self.scenarios)} сценариев из JSON (dict.scenarios)"
                )
            else:
                # Неизвестная структура
                logger.error(
                    f"❌ Неизвестная структура JSON. "
                    f"Тип: {type(data)}, "
                    f"Ключи: {list(data.keys()) if isinstance(data, dict) else 'N/A'}"
                )
                self.scenarios = []

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки сценариев: {e}", exc_info=True)
            self.scenarios = []

    def match_scenario(
        self,
        symbol: str,
        market_data: Dict,
        indicators: Dict,
        mtf_trends: Dict,
        volume_profile: Dict,
        news_sentiment: Dict,
        veto_checks: Dict,
        cvd_data: Optional[Dict] = None,
    ) -> Optional[Dict]:
        """
        Главная функция сопоставления рыночных условий со сценариями

        Args:
            symbol: Торговая пара (например, BTCUSDT)
            market_data: Текущие рыночные данные (price, volume, etc.)
            indicators: Технические индикаторы (RSI, MACD, ATR)
            mtf_trends: Тренды по таймфреймам (1H, 4H, 1D)
            volume_profile: Volume profile данные (POC, VAH, VAL)
            news_sentiment: Sentiment анализ новостей
            veto_checks: Результаты VETO проверок
            cvd_data: Cumulative Volume Delta (опционально)

        Returns:
            Dict с информацией о найденном сценарии или None
        """
        try:
            logger.debug(f"🔍 Поиск подходящего сценария для {symbol}...")

            # Проверяем VETO - если есть жёсткий запрет, сразу выходим
            if veto_checks.get("has_veto", False):
                logger.warning(
                    f"⛔ Все сценарии отклонены VETO: "
                    f"{veto_checks.get('veto_reasons', [])}"
                )
                return None

            best_match = None
            best_score = 0.0
            matched_features = []

            # Перебираем все сценарии
            for scenario in self.scenarios:
                # Рассчитываем score для сценария
                score = self._calculate_scenario_score(
                    scenario=scenario,
                    market_data=market_data,
                    indicators=indicators,
                    mtf_trends=mtf_trends,
                    volume_profile=volume_profile,
                    news_sentiment=news_sentiment,
                    cvd_data=cvd_data,
                )

                # Собираем matched features
                features = self._get_matched_features(scenario=scenario, score=score)

                # Обновляем лучшее совпадение
                if score > best_score:
                    best_score = score
                    best_match = scenario
                    matched_features = features

            # Проверяем порог observation
            if best_score < self.observation_threshold:
                logger.debug(
                    f"❌ Нет подходящих сценариев для {symbol}. "
                    f"Лучший score: {best_score:.1%}. Пробуем fallback..."
                )

                # ✅ FALLBACK: Базовый сценарий если score слишком низкий
                cvd = market_data.get("cvd", 0)
                ls_ratio = market_data.get("long_short_ratio", 1.0)
                funding = market_data.get("funding_rate", 0)
                rsi = indicators.get("rsi", 50)
                volume_ratio = market_data.get("volume_ratio", 1.0)

                # Bullish scenario
                if cvd > 2 and ls_ratio > 1.2 and rsi < 50:
                    best_match = {
                        "id": "FALLBACK_LONG",
                        "name": "Accumulation (Basic)",
                        "direction": "LONG",
                        "description": "Базовый бычий сценарий на основе CVD и L/S",
                        "tp1_percent": 1.5,
                        "tp2_percent": 3.0,
                        "tp3_percent": 5.0,
                        "sl_percent": 1.0,
                        "conditions": {},
                        "timeframe": "1H",
                    }
                    best_score = 0.25
                    matched_features = ["positive_cvd", "high_ls_ratio", "oversold_rsi"]
                    logger.info(
                        f"✅ Применён FALLBACK LONG для {symbol} (CVD={cvd:.1f}, L/S={ls_ratio:.2f})"
                    )

                # Bearish scenario
                elif cvd < -2 and ls_ratio < 0.9 and rsi > 50:
                    best_match = {
                        "id": "FALLBACK_SHORT",
                        "name": "Distribution (Basic)",
                        "direction": "SHORT",
                        "description": "Базовый медвежий сценарий на основе CVD и L/S",
                        "tp1_percent": 1.5,
                        "tp2_percent": 3.0,
                        "tp3_percent": 5.0,
                        "sl_percent": 1.0,
                        "conditions": {},
                        "timeframe": "1H",
                    }
                    best_score = 0.25
                    matched_features = [
                        "negative_cvd",
                        "low_ls_ratio",
                        "overbought_rsi",
                    ]
                    logger.info(
                        f"✅ Применён FALLBACK SHORT для {symbol} (CVD={cvd:.1f}, L/S={ls_ratio:.2f})"
                    )

                # Ranging/Consolidation
                elif abs(cvd) < 2 and 0.9 <= ls_ratio <= 1.1 and volume_ratio > 1.2:
                    best_match = {
                        "id": "FALLBACK_RANGE",
                        "name": "Consolidation",
                        "direction": "LONG",
                        "description": "Консолидация с повышенными объёмами",
                        "tp1_percent": 1.0,
                        "tp2_percent": 2.0,
                        "tp3_percent": 3.0,
                        "sl_percent": 0.8,
                        "conditions": {},
                        "timeframe": "1H",
                    }
                    best_score = 0.22
                    matched_features = ["neutral_cvd", "balanced_ls", "high_volume"]
                    logger.info(
                        f"✅ Применён FALLBACK RANGE для {symbol} (Neutral market)"
                    )

                # Если fallback тоже не подошёл
                if best_score < self.observation_threshold:
                    logger.debug(f"❌ Fallback тоже не подошёл для {symbol}")
                    return None

            # Определяем статус на основе score
            status = self._determine_status(best_score)

            # Формируем результат
            current_price = market_data.get("close", market_data.get("price", 0))

            result = {
                "scenario_id": best_match.get("id", "unknown"),
                "scenario_name": best_match.get("name")
                or f"{best_match.get('strategy', 'Unknown').title()} {best_match.get('phase', 'Setup').title()}",
                "symbol": symbol,
                "status": status,
                "score": round(best_score * 100, 2),
                "direction": best_match.get("direction", "LONG"),
                "entry_price": current_price,
                "timestamp": datetime.now().isoformat(),
                "matched_features": matched_features,
                "conditions": best_match.get("conditions", {}),
                "description": best_match.get("description", ""),
                "timeframe": best_match.get("timeframe", "1H"),
            }

            # Расчёт TP/SL
            if current_price > 0:
                direction = best_match.get("direction", "LONG")

                # Базовые проценты
                tp1_percent = best_match.get("tp1_percent", 1.5)
                tp2_percent = best_match.get("tp2_percent", 3.0)
                tp3_percent = best_match.get("tp3_percent", 5.0)
                sl_percent = best_match.get("sl_percent", 1.0)

                # СНАЧАЛА РАССЧИТЫВАЕМ TP/SL! ← ВАЖНО!
                if direction.upper() == "LONG":
                    tp1 = round(current_price * (1 + tp1_percent / 100), 2)
                    tp2 = round(current_price * (1 + tp2_percent / 100), 2)
                    tp3 = round(current_price * (1 + tp3_percent / 100), 2)
                    stop_loss = round(current_price * (1 - sl_percent / 100), 2)
                else:  # SHORT
                    tp1 = round(current_price * (1 - tp1_percent / 100), 2)
                    tp2 = round(current_price * (1 - tp2_percent / 100), 2)
                    tp3 = round(current_price * (1 - tp3_percent / 100), 2)
                    stop_loss = round(current_price * (1 + sl_percent / 100), 2)

                # ========== RR ФІЛЬТР (КРИТИЧНО!) ==========
                # Расчёт Risk/Reward для TP2 (основной TP)
                risk = abs(current_price - stop_loss)
                reward = abs(tp2 - current_price)

                if risk > 0:
                    calculated_rr = round(reward / risk, 2)
                else:
                    calculated_rr = 0.0

                # Минимальный порог RR
                min_rr = 1.2

                if calculated_rr < min_rr:
                    logger.info(
                        f"⚠️ {symbol}: Сигнал отклонён (RR={calculated_rr:.2f} < {min_rr}) "
                        f"[Score: {best_score*100:.1f}%, "
                        f"Entry: ${current_price:,.2f}, "
                        f"TP2: ${tp2:,.2f}, "
                        f"SL: ${stop_loss:,.2f}, "
                        f"Risk: ${risk:,.2f}, "
                        f"Reward: ${reward:,.2f}]"
                    )
                    return None  # ← ОТКЛОНЯЕМ СИГНАЛ!

                # Добавляем рассчитанные значения в result
                result["tp1"] = tp1
                result["tp2"] = tp2
                result["tp3"] = tp3
                result["stop_loss"] = stop_loss
                result["risk_reward"] = calculated_rr  # ← ДОБАВЛЯЕМ RR В РЕЗУЛЬТАТ

            else:
                result["tp1"] = 0
                result["tp2"] = 0
                result["tp3"] = 0
                result["stop_loss"] = 0
                result["risk_reward"] = 0.0

            # Логируем результат (ПОСЛЕ RR ФІЛЬТРА!)
            if status == "deal":
                logger.info(
                    f"✅ DEAL сигнал для {symbol}! "
                    f"Score: {result['score']:.1f}%, "
                    f"RR: {result.get('risk_reward', 0):.2f}, "
                    f"Сценарій: {result['scenario_name']}"
                )
            elif status == "risky_entry":
                logger.info(
                    f"⚠️ RISKY ENTRY для {symbol}! "
                    f"Score: {result['score']:.1f}%, "
                    f"RR: {result.get('risk_reward', 0):.2f}, "
                    f"Сценарій: {result['scenario_name']}"
                )
            else:
                logger.debug(
                    f"👀 Наблюдение для {symbol}. "
                    f"Score: {result['score']:.1f}%, "
                    f"Сценарій: {result['scenario_name']}"
                )

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка match_scenario для {symbol}: {e}")
            return None

    def _calculate_scenario_score(
        self,
        scenario: Dict,
        market_data: Dict,
        indicators: Dict,
        mtf_trends: Dict,
        volume_profile: Dict,
        news_sentiment: Dict,
        cvd_data: Optional[Dict],
    ) -> float:
        """
        Расчёт weighted score сценария

        Returns:
            float: score от 0.0 до 1.0
        """
        try:
            # Получаем условия и веса из сценария
            conditions = scenario.get("conditions", {})
            weights = scenario.get("weights", {})

            score = 0.0
            total_weight = 0.0

            # 1. MTF Policy (вес: 30%)
            mtf_score = self._check_mtf_policy(scenario, indicators, mtf_trends)
            mtf_weight = weights.get("mtf", 0.30)
            score += mtf_score * mtf_weight
            total_weight += mtf_weight

            # 2. ExoCharts / Volume Profile (вес: 25%)
            exo_score = self._check_exocharts(scenario, market_data, volume_profile)
            exo_weight = weights.get("exocharts", 0.25)
            score += exo_score * exo_weight
            total_weight += exo_weight

            # 3. Indicators (RSI, MACD, ATR) (вес: 15%)
            ind_score = self._check_indicator_conditions(
                conditions.get("indicators", {}), indicators
            )
            ind_weight = weights.get("indicators", 0.15)
            score += ind_score * ind_weight
            total_weight += ind_weight

            # 4. News Policy (вес: 15%)
            news_score = self._check_news_policy(scenario, news_sentiment)
            news_weight = weights.get("news", 0.15)
            score += news_score * news_weight
            total_weight += news_weight

            # 5. CVD (вес: 10%)
            if cvd_data:
                cvd_score = self._check_cvd(scenario, cvd_data)
                cvd_weight = weights.get("cvd", 0.10)
                score += cvd_score * cvd_weight
                total_weight += cvd_weight

            # 6. Triggers (вес: 10%)
            trigger_score = self._check_triggers(scenario, indicators, market_data)
            trigger_weight = weights.get("triggers", 0.10)
            score += trigger_score * trigger_weight
            total_weight += trigger_weight

            # Нормализуем score
            final_score = score / total_weight if total_weight > 0 else 0.0

            return max(0.0, min(1.0, final_score))

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта score: {e}")
            return 0.0

    def _check_mtf_policy(
        self, scenario: Dict, indicators: Dict, mtf_trends: Dict
    ) -> float:
        """Проверка MTF условий с поддержкой v2 и v3 форматов"""
        try:
            # === ОПРЕДЕЛЯЕМ ФОРМАТ СЦЕНАРИЯ ===
            source = scenario.get("source", "v3")

            # === ПОДДЕРЖКА v2 ФОРМАТА (детальный) ===
            if (
                source == "v2_detailed"
                and "mtf" in scenario
                and isinstance(scenario["mtf"], dict)
            ):
                mtf_config = scenario["mtf"]
                mode = mtf_config.get("mode", "majority")
                required_alignment = mtf_config.get("required_alignment", 2)
                conditions = mtf_config.get("conditions", {})

                # Получаем тренды через универсальный геттер
                trend_1d = self._get_trend(mtf_trends, indicators, "1D")
                trend_4h = self._get_trend(mtf_trends, indicators, "4H")
                trend_1h = self._get_trend(mtf_trends, indicators, "1H")

                # Проверяем соответствие условиям
                aligned_count = 0

                # 1D
                if "1D" in conditions:
                    allowed_trends = conditions["1D"]
                    if trend_1d in allowed_trends:
                        aligned_count += 1

                # 4H
                if "4H" in conditions:
                    allowed_trends = conditions["4H"]
                    if trend_4h in allowed_trends:
                        aligned_count += 1

                # 1H
                if "1H" in conditions:
                    allowed_trends = conditions["1H"]
                    if trend_1h in allowed_trends:
                        aligned_count += 1

                # Оценка на основе mode
                if mode == "majority":
                    if aligned_count >= required_alignment:
                        return 0.9  # ✅ Достаточно выравнивания
                    elif aligned_count == required_alignment - 1:
                        return 0.6  # ⚠️ Почти достаточно
                    else:
                        return 0.3  # ❌ Недостаточно

                elif mode == "counter_trend":
                    # Для контр-трендовых: разные направления ОК
                    if aligned_count >= 1:
                        return 0.7
                    else:
                        return 0.4

                elif mode == "correction_in_range":
                    # Для коррекций в рендже
                    if aligned_count >= 1:
                        return 0.8
                    else:
                        return 0.5

                elif mode == "breakout_retest":
                    # Для breakout retest
                    if aligned_count >= required_alignment:
                        return 0.9
                    else:
                        return 0.5

            # === ПОДДЕРЖКА v3 ФОРМАТА (упрощённый) ===
            else:
                required_opinion = scenario.get("opinion", "bullish")

                if required_opinion == "bullish":
                    required_trend = "uptrend"
                elif required_opinion == "bearish":
                    required_trend = "downtrend"
                else:
                    required_trend = required_opinion

                # Получаем тренды через универсальный геттер
                trend_1h = self._get_trend(mtf_trends, indicators, "1H")
                trend_4h = self._get_trend(mtf_trends, indicators, "4H")
                trend_1d = self._get_trend(mtf_trends, indicators, "1D")

                # Считаем совпадения
                aligned_count = 0
                if trend_1h.lower() == required_trend.lower():
                    aligned_count += 1
                if trend_4h.lower() == required_trend.lower():
                    aligned_count += 1
                if trend_1d.lower() == required_trend.lower():
                    aligned_count += 1

                # Оценка
                if aligned_count == 3:
                    return 1.0
                elif aligned_count == 2:
                    return 0.7
                elif aligned_count == 1:
                    return 0.5
                else:
                    return 0.3

        except Exception as e:
            logger.error(f"❌ Ошибка проверки MTF: {e}")
            return 0.5

    def _check_exocharts(
        self, scenario: Dict, market_data: Dict, volume_profile: Dict
    ) -> float:
        """Проверка ExoCharts / Volume Profile"""
        try:
            current_price = market_data.get("price", 0)
            poc = volume_profile.get("poc", 0) or market_data.get("poc", 0)
            vah = volume_profile.get("vah", 0) or market_data.get("vah", 0)
            val = volume_profile.get("val", 0) or market_data.get("val", 0)

            if not all([current_price, poc, vah, val]):
                return 0.3  # нет данных Volume Profile

            direction = scenario.get("direction", "long")

            if direction == "long":
                # Для лонга хорошо: цена около VAL или чуть выше POC
                if val > 0 and abs(current_price - val) / val < 0.01:  # ±1% от VAL
                    return 0.9
                elif poc > 0 and current_price > poc and current_price < vah:
                    return 0.8
                elif current_price > vah:
                    return 0.6  # цена высоко, риск коррекции

            elif direction == "short":
                # Для шорта хорошо: цена около VAH или чуть ниже POC
                if vah > 0 and abs(current_price - vah) / vah < 0.01:  # ±1% от VAH
                    return 0.9
                elif poc > 0 and current_price < poc and current_price > val:
                    return 0.8
                elif current_price < val:
                    return 0.6  # цена низко, риск отскока

            return 0.5

        except Exception as e:
            logger.error(f"❌ Ошибка проверки ExoCharts: {e}")
            return 0.5

    def _check_indicator_conditions(self, conditions: Dict, indicators: Dict) -> float:
        """Проверка индикаторов (RSI, MACD, ATR)"""
        try:
            score = 0.0
            checks = 0

            # RSI
            if "rsi" in conditions:
                rsi_cond = conditions["rsi"]
                rsi_value = indicators.get("rsi", 50)

                if "min" in rsi_cond and "max" in rsi_cond:
                    if rsi_cond["min"] <= rsi_value <= rsi_cond["max"]:
                        score += 1
                checks += 1

            # MACD
            if "macd" in conditions:
                macd_cond = conditions["macd"]
                macd_histogram = indicators.get("macd_histogram", 0)

                if macd_cond.get("signal") == "bullish" and macd_histogram > 0:
                    score += 1
                elif macd_cond.get("signal") == "bearish" and macd_histogram < 0:
                    score += 1
                checks += 1

            # ATR
            if "atr" in conditions:
                atr_cond = conditions["atr"]
                atr_value = indicators.get("atr", 0)
                atr_threshold = atr_cond.get("min", 0)

                if atr_value >= atr_threshold:
                    score += 1
                checks += 1

            return score / checks if checks > 0 else 0.8  # По умолчанию OK

        except Exception as e:
            logger.error(f"❌ Ошибка проверки индикаторов: {e}")
            return 0.5

    def _check_news_policy(self, scenario: Dict, news_sentiment: Dict) -> float:
        """Проверка новостного sentiment"""
        try:
            sentiment = news_sentiment.get("sentiment", "neutral")
            sentiment_score = news_sentiment.get("score", 0)  # от -10 до +10
            direction = scenario.get("direction", "long")

            if direction == "long" and sentiment in ["bullish", "positive"]:
                return 0.8 + min(0.2, abs(sentiment_score) / 50)
            elif direction == "short" and sentiment in ["bearish", "negative"]:
                return 0.8 + min(0.2, abs(sentiment_score) / 50)
            elif sentiment == "neutral":
                return 0.5
            else:
                return 0.3  # sentiment против направления

        except Exception as e:
            logger.error(f"❌ Ошибка проверки news: {e}")
            return 0.5

    def _check_cvd(self, scenario: Dict, cvd_data: Dict) -> float:
        """Проверка CVD"""
        try:
            cvd = cvd_data.get("cvd", 0)
            direction = scenario.get("direction", "long")

            if direction == "long" and cvd > 0:
                return min(0.7 + (cvd / 1000000) * 0.3, 1.0)
            elif direction == "short" and cvd < 0:
                return min(0.7 + (abs(cvd) / 1000000) * 0.3, 1.0)
            else:
                return 0.4

        except Exception as e:
            logger.error(f"❌ Ошибка проверки CVD: {e}")
            return 0.5

    def _check_triggers(
        self, scenario: Dict, indicators: Dict, market_data: Dict
    ) -> float:
        """Проверка триггеров (T1/T2/T3)"""
        try:
            score = 0.0
            triggers_fired = 0

            # T1: Технический триггер (RSI)
            rsi = indicators.get("rsi_1h", 50) or indicators.get("rsi", 50)
            if scenario.get("direction") == "long" and 30 < rsi < 50:
                triggers_fired += 1
            elif scenario.get("direction") == "short" and 50 < rsi < 70:
                triggers_fired += 1

            # T2: Объёмный триггер
            volume_ratio = market_data.get("volume_ratio", 1.0)
            if volume_ratio > 1.3:
                triggers_fired += 1

            # T3: CVD подтверждение
            cvd = market_data.get("cvd", 0)
            cvd_confirmed = cvd * (1 if scenario.get("direction") == "long" else -1) > 0
            if cvd_confirmed:
                triggers_fired += 1

            score = triggers_fired / 3.0
            return score

        except Exception as e:
            logger.error(f"❌ Ошибка проверки triggers: {e}")
            return 0.5

    def _determine_status(self, score: float) -> str:
        """Определение статуса на основе score"""
        if score >= self.deal_threshold:
            return "deal"
        elif score >= self.risky_threshold:
            return "risky_entry"
        else:
            return "observation"

    def _get_trend(self, mtf_trends: Dict, indicators: Dict, tf_key: str) -> str:
        """Универсальный геттер для тренда с поддержкой разных форматов"""
        # Попробуем разные варианты ключей (1H, 1h, 1D, 1d)
        tf_variants = [tf_key, tf_key.lower(), tf_key.upper()]

        for variant in tf_variants:
            # Пробуем получить из mtf_trends
            if isinstance(mtf_trends, dict) and variant in mtf_trends:
                trend_data = mtf_trends[variant]

                # Если значение - словарь с ключом "trend"
                if isinstance(trend_data, dict):
                    return trend_data.get("trend", "neutral")
                # Если значение - строка напрямую
                elif trend_data:
                    return trend_data

            # Fallback: пробуем получить из indicators
            ind_key = f"trend_{variant.lower()}"
            if ind_key in indicators:
                return indicators[ind_key]

        # Если ничего не нашли - возвращаем neutral
        return "neutral"

    def _get_matched_features(self, scenario: Dict, score: float) -> List[str]:
        """Получение списка matched features для сценария"""
        features = []

        if score >= 0.7:
            features.append("mtf_aligned")
        if score >= 0.6:
            features.append("volume_profile_confirmed")
        if score >= 0.5:
            features.append("positive_news")

        return features


# Алиас для совместимости
ScenarioMatcher = UnifiedScenarioMatcher
EnhancedScenarioMatcher = UnifiedScenarioMatcher
