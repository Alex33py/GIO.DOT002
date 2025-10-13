# -*- coding: utf-8 -*-
"""
Расширенная система вето для GIO Crypto Bot
Защита от плохих торговых решений с интеллектуальным анализом рисков
"""

import asyncio
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import deque, defaultdict

from config.settings import (
    logger, FUNDING_RATE_VETO_THRESHOLD, VOLUME_ANOMALY_VETO_THRESHOLD,
    SPREAD_VETO_THRESHOLD, LIQUIDATION_CASCADE_VETO_COUNT, MARKET_STABILITY_THRESHOLD
)
from config.constants import VetoReasonEnum, AlertTypeEnum, TrendDirectionEnum, Colors
from utils.helpers import current_epoch_ms, safe_float, format_percentage
from utils.validators import validate_market_data_completeness


class VetoSeverityEnum(Enum):
    """Уровни серьёзности вето"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class VetoTrigger:
    """Триггер системы вето"""
    reason: VetoReasonEnum
    severity: VetoSeverityEnum
    confidence: float
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: int = field(default_factory=current_epoch_ms)
    affected_symbols: List[str] = field(default_factory=list)
    duration_estimate_ms: int = 300000  # 5 минут по умолчанию
    auto_recovery: bool = True


@dataclass
class VetoAnalysisResult:
    """Результат анализа системы вето"""
    is_vetoed: bool
    active_vetos: List[VetoTrigger]
    risk_score: float  # 0.0 - 1.0
    market_stability: float  # 0.0 - 1.0
    recommendation: str
    analysis_timestamp: int
    next_check_time: int
    veto_history_summary: Dict[str, Any]


class EnhancedVetoSystem:
    """Расширенная система вето с интеллектуальным анализом рисков"""

    def __init__(self):
        """Инициализация системы вето"""
        # Активные вето
        self.active_vetos: Dict[str, VetoTrigger] = {}

        # История вето (последние 1000)
        self.veto_history = deque(maxlen=1000)

        # Данные для анализа
        self.funding_rate_history = deque(maxlen=100)
        self.volume_history = deque(maxlen=500)
        self.spread_history = deque(maxlen=200)
        self.liquidation_events = deque(maxlen=1000)
        self.market_anomalies = deque(maxlen=200)

        # Настройки чувствительности
        self.sensitivity_settings = {
            "funding_rate": 1.0,        # Множитель чувствительности
            "volume_anomaly": 1.0,
            "spread": 1.0,
            "liquidation": 1.0,
            "market_stability": 1.0,
            "news_conflict": 0.8,       # Пониженная чувствительность к новостям
        }

        # Статистика срабатываний
        self.veto_stats = {
            "total_vetos": 0,
            "prevented_bad_trades": 0,
            "false_positives": 0,
            "accuracy_rate": 0.0,
            "avg_veto_duration": 0.0,
            "most_common_reason": None,
            "vetos_by_reason": defaultdict(int),
            "vetos_by_severity": defaultdict(int),
        }

        # Адаптивные пороги (самообучение)
        self.adaptive_thresholds = {
            "funding_rate": FUNDING_RATE_VETO_THRESHOLD,
            "volume_anomaly": VOLUME_ANOMALY_VETO_THRESHOLD,
            "spread": SPREAD_VETO_THRESHOLD,
            "liquidation_cascade": LIQUIDATION_CASCADE_VETO_COUNT,
            "market_stability": MARKET_STABILITY_THRESHOLD,
        }

        logger.info("✅ EnhancedVetoSystem инициализирована")

    async def analyze_market_conditions(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        volume_profile: Any = None,
        news_sentiment: Dict = None
    ) -> VetoAnalysisResult:
        """Комплексный анализ рыночных условий для определения вето"""
        try:
            current_time = current_epoch_ms()

            # Проверяем полноту рыночных данных
            data_completeness = validate_market_data_completeness(market_data)
            if not any(data_completeness.values()):
                return self._create_no_data_result(current_time)

            # Выполняем различные проверки
            veto_triggers = []

            # 1. Анализ funding rate
            funding_veto = await self._check_funding_rate(market_data, symbol)
            if funding_veto:
                veto_triggers.append(funding_veto)

            # 2. Анализ аномалий объёма
            volume_veto = await self._check_volume_anomaly(market_data, volume_profile, symbol)
            if volume_veto:
                veto_triggers.append(volume_veto)

            # 3. Анализ спреда
            spread_veto = await self._check_spread_conditions(market_data, symbol)
            if spread_veto:
                veto_triggers.append(spread_veto)

            # 4. Анализ каскадов ликвидации
            liquidation_veto = await self._check_liquidation_cascade(market_data, symbol)
            if liquidation_veto:
                veto_triggers.append(liquidation_veto)

            # 5. Анализ стабильности рынка
            stability_veto = await self._check_market_stability(market_data, symbol)
            if stability_veto:
                veto_triggers.append(stability_veto)

            # 6. Анализ манипуляций orderbook
            manipulation_veto = await self._check_orderbook_manipulation(market_data, symbol)
            if manipulation_veto:
                veto_triggers.append(manipulation_veto)

            # 7. Анализ конфликтов новостей
            if news_sentiment:
                news_veto = await self._check_news_conflicts(news_sentiment, symbol)
                if news_veto:
                    veto_triggers.append(news_veto)

            # Обновляем активные вето
            await self._update_active_vetos(veto_triggers, current_time)

            # Рассчитываем общий риск-скор
            risk_score = self._calculate_risk_score(veto_triggers, market_data)

            # Оценка стабильности рынка
            market_stability = self._calculate_market_stability(market_data, volume_profile)

            # Определяем итоговое решение
            is_vetoed = len(self.active_vetos) > 0 or risk_score > 0.7

            # Генерируем рекомендацию
            recommendation = self._generate_recommendation(veto_triggers, risk_score, market_stability)

            # Создаём результат
            result = VetoAnalysisResult(
                is_vetoed=is_vetoed,
                active_vetos=list(self.active_vetos.values()),
                risk_score=round(risk_score, 3),
                market_stability=round(market_stability, 3),
                recommendation=recommendation,
                analysis_timestamp=current_time,
                next_check_time=current_time + 60000,  # Следующая проверка через минуту
                veto_history_summary=self._get_veto_history_summary()
            )

            # Логируем результат если есть активные вето
            if is_vetoed:
                self._log_veto_result(result, symbol)

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка анализа veto системы: {e}")
            return self._create_error_result(current_time, str(e))

    async def _check_funding_rate(self, market_data: Dict, symbol: str) -> Optional[VetoTrigger]:
        """Проверка funding rate на экстремальные значения"""
        try:
            funding_data = market_data.get("funding_rate", {})
            if not funding_data:
                return None

            current_rate = safe_float(funding_data.get("funding_rate", 0))

            # Сохраняем в истории
            self.funding_rate_history.append({
                "rate": current_rate,
                "timestamp": current_epoch_ms(),
                "symbol": symbol
            })

            # Применяем адаптивный порог
            threshold = self.adaptive_thresholds["funding_rate"] * self.sensitivity_settings["funding_rate"]

            if abs(current_rate) > threshold:
                severity = self._determine_funding_severity(current_rate, threshold)

                return VetoTrigger(
                    reason=VetoReasonEnum.HIGH_FUNDING_RATE,
                    severity=severity,
                    confidence=min(1.0, abs(current_rate) / threshold),
                    message=f"Экстремальный funding rate: {format_percentage(current_rate)} (порог: ±{format_percentage(threshold)})",
                    data={
                        "current_rate": current_rate,
                        "threshold": threshold,
                        "rate_direction": "positive" if current_rate > 0 else "negative"
                    },
                    affected_symbols=[symbol],
                    duration_estimate_ms=1800000,  # 30 минут
                    auto_recovery=True
                )

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка проверки funding rate: {e}")
            return None

    def _determine_funding_severity(self, rate: float, threshold: float) -> VetoSeverityEnum:
        """Определение серьёзности funding rate вето"""
        rate_ratio = abs(rate) / threshold

        if rate_ratio >= 3.0:
            return VetoSeverityEnum.CRITICAL
        elif rate_ratio >= 2.0:
            return VetoSeverityEnum.HIGH
        elif rate_ratio >= 1.5:
            return VetoSeverityEnum.MEDIUM
        else:
            return VetoSeverityEnum.LOW

    async def _check_volume_anomaly(
        self,
        market_data: Dict,
        volume_profile: Any,
        symbol: str
    ) -> Optional[VetoTrigger]:
        """Проверка аномалий объёма"""
        try:
            # Получаем текущий объём из ticker
            ticker = market_data.get("ticker", {})
            current_volume = safe_float(ticker.get("volume_24h", 0))

            if current_volume <= 0:
                return None

            # Сохраняем в истории
            self.volume_history.append({
                "volume": current_volume,
                "timestamp": current_epoch_ms(),
                "symbol": symbol
            })

            # Рассчитываем среднее за последние записи
            if len(self.volume_history) < 10:
                return None

            recent_volumes = [entry["volume"] for entry in list(self.volume_history)[-20:]]
            avg_volume = sum(recent_volumes) / len(recent_volumes)

            if avg_volume <= 0:
                return None

            # Определяем аномалию
            volume_ratio = current_volume / avg_volume
            threshold = self.adaptive_thresholds["volume_anomaly"] * self.sensitivity_settings["volume_anomaly"]

            # Проверяем как резкий рост, так и резкое падение
            if volume_ratio > threshold or volume_ratio < (1.0 / threshold):
                anomaly_type = "spike" if volume_ratio > threshold else "drop"
                severity = self._determine_volume_severity(volume_ratio, threshold, anomaly_type)

                return VetoTrigger(
                    reason=VetoReasonEnum.EXTREME_VOLUME_ANOMALY,
                    severity=severity,
                    confidence=min(1.0, max(volume_ratio, 1.0/volume_ratio) / threshold),
                    message=f"Аномалия объёма: {anomaly_type} {volume_ratio:.1f}x от среднего",
                    data={
                        "current_volume": current_volume,
                        "avg_volume": avg_volume,
                        "ratio": volume_ratio,
                        "anomaly_type": anomaly_type,
                        "threshold": threshold
                    },
                    affected_symbols=[symbol],
                    duration_estimate_ms=600000,  # 10 минут
                    auto_recovery=True
                )

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка проверки volume anomaly: {e}")
            return None

    def _determine_volume_severity(
        self,
        volume_ratio: float,
        threshold: float,
        anomaly_type: str
    ) -> VetoSeverityEnum:
        """Определение серьёзности volume anomaly"""
        effective_ratio = volume_ratio if anomaly_type == "spike" else 1.0 / volume_ratio
        severity_ratio = effective_ratio / threshold

        if severity_ratio >= 5.0:
            return VetoSeverityEnum.CRITICAL
        elif severity_ratio >= 3.0:
            return VetoSeverityEnum.HIGH
        elif severity_ratio >= 2.0:
            return VetoSeverityEnum.MEDIUM
        else:
            return VetoSeverityEnum.LOW

    async def _check_spread_conditions(self, market_data: Dict, symbol: str) -> Optional[VetoTrigger]:
        """Проверка условий спреда"""
        try:
            orderbook = market_data.get("orderbook", {})
            if not orderbook:
                return None

            # Получаем spread в basis points
            spread_bps = safe_float(orderbook.get("spread_bps", 0))
            mid_price = safe_float(orderbook.get("mid_price", 0))

            if spread_bps <= 0 or mid_price <= 0:
                return None

            # Сохраняем в истории
            self.spread_history.append({
                "spread_bps": spread_bps,
                "mid_price": mid_price,
                "timestamp": current_epoch_ms(),
                "symbol": symbol
            })

            # Конвертируем порог в basis points
            threshold_bps = self.adaptive_thresholds["spread"] * 10000 * self.sensitivity_settings["spread"]

            if spread_bps > threshold_bps:
                severity = self._determine_spread_severity(spread_bps, threshold_bps)

                return VetoTrigger(
                    reason=VetoReasonEnum.WIDE_SPREAD,
                    severity=severity,
                    confidence=min(1.0, spread_bps / threshold_bps),
                    message=f"Широкий спред: {spread_bps:.1f} bps (порог: {threshold_bps:.1f} bps)",
                    data={
                        "spread_bps": spread_bps,
                        "threshold_bps": threshold_bps,
                        "mid_price": mid_price,
                        "spread_percentage": spread_bps / 10000
                    },
                    affected_symbols=[symbol],
                    duration_estimate_ms=300000,  # 5 минут
                    auto_recovery=True
                )

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка проверки spread: {e}")
            return None

    def _determine_spread_severity(self, spread_bps: float, threshold_bps: float) -> VetoSeverityEnum:
        """Определение серьёзности spread вето"""
        spread_ratio = spread_bps / threshold_bps

        if spread_ratio >= 4.0:
            return VetoSeverityEnum.CRITICAL
        elif spread_ratio >= 2.5:
            return VetoSeverityEnum.HIGH
        elif spread_ratio >= 1.5:
            return VetoSeverityEnum.MEDIUM
        else:
            return VetoSeverityEnum.LOW

    async def _check_liquidation_cascade(self, market_data: Dict, symbol: str) -> Optional[VetoTrigger]:
        """Проверка каскадов ликвидации"""
        try:
            # Для упрощения, используем анализ резких движений цены как индикатор ликвидации
            ticker = market_data.get("ticker", {})
            price_change = safe_float(ticker.get("price_24h_pcnt", 0))

            if abs(price_change) == 0:
                return None

            # Добавляем событие в историю
            liquidation_event = {
                "price_change": price_change,
                "timestamp": current_epoch_ms(),
                "symbol": symbol,
                "severity": "high" if abs(price_change) > 10 else "medium" if abs(price_change) > 5 else "low"
            }

            self.liquidation_events.append(liquidation_event)

            # Подсчитываем количество значительных событий за последний час
            current_time = current_epoch_ms()
            hour_ago = current_time - 3600000

            recent_events = [
                event for event in self.liquidation_events
                if event["timestamp"] > hour_ago and abs(event["price_change"]) > 3
            ]

            threshold = self.adaptive_thresholds["liquidation_cascade"] * self.sensitivity_settings["liquidation"]

            if len(recent_events) > threshold:
                cascade_severity = self._determine_liquidation_severity(len(recent_events), threshold)

                return VetoTrigger(
                    reason=VetoReasonEnum.LIQUIDATION_CASCADE,
                    severity=cascade_severity,
                    confidence=min(1.0, len(recent_events) / (threshold * 2)),
                    message=f"Каскад ликвидации: {len(recent_events)} событий за час (порог: {threshold})",
                    data={
                        "events_count": len(recent_events),
                        "threshold": threshold,
                        "max_price_change": max(abs(e["price_change"]) for e in recent_events),
                        "timeframe": "1h"
                    },
                    affected_symbols=[symbol],
                    duration_estimate_ms=1200000,  # 20 минут
                    auto_recovery=True
                )

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка проверки liquidation cascade: {e}")
            return None

    def _determine_liquidation_severity(self, events_count: int, threshold: float) -> VetoSeverityEnum:
        """Определение серьёзности liquidation cascade"""
        cascade_ratio = events_count / threshold

        if cascade_ratio >= 3.0:
            return VetoSeverityEnum.CRITICAL
        elif cascade_ratio >= 2.0:
            return VetoSeverityEnum.HIGH
        elif cascade_ratio >= 1.5:
            return VetoSeverityEnum.MEDIUM
        else:
            return VetoSeverityEnum.LOW

    async def _check_market_stability(self, market_data: Dict, symbol: str) -> Optional[VetoTrigger]:
        """Проверка стабильности рынка"""
        try:
            stability_score = self._calculate_market_stability(market_data, None)
            threshold = self.adaptive_thresholds["market_stability"] * self.sensitivity_settings["market_stability"]

            if stability_score < threshold:
                instability_level = threshold - stability_score
                severity = self._determine_stability_severity(stability_score, threshold)

                return VetoTrigger(
                    reason=VetoReasonEnum.MARKET_INSTABILITY,
                    severity=severity,
                    confidence=min(1.0, instability_level / threshold),
                    message=f"Нестабильность рынка: {stability_score:.3f} (порог: {threshold:.3f})",
                    data={
                        "stability_score": stability_score,
                        "threshold": threshold,
                        "instability_level": instability_level
                    },
                    affected_symbols=[symbol],
                    duration_estimate_ms=900000,  # 15 минут
                    auto_recovery=True
                )

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка проверки market stability: {e}")
            return None

    def _determine_stability_severity(self, stability_score: float, threshold: float) -> VetoSeverityEnum:
        """Определение серьёзности market instability"""
        instability_ratio = (threshold - stability_score) / threshold

        if instability_ratio >= 0.8:
            return VetoSeverityEnum.CRITICAL
        elif instability_ratio >= 0.6:
            return VetoSeverityEnum.HIGH
        elif instability_ratio >= 0.4:
            return VetoSeverityEnum.MEDIUM
        else:
            return VetoSeverityEnum.LOW

    async def _check_orderbook_manipulation(self, market_data: Dict, symbol: str) -> Optional[VetoTrigger]:
        """Проверка манипуляций orderbook"""
        try:
            orderbook = market_data.get("orderbook", {})
            if not orderbook:
                return None

            bids = orderbook.get("bids", [])
            asks = orderbook.get("asks", [])

            if not bids or not asks:
                return None

            # Анализируем дисбаланс в топе стакана
            top_bid_volume = sum(safe_float(bid.get("size", 0)) for bid in bids[:5])
            top_ask_volume = sum(safe_float(ask.get("size", 0)) for ask in asks[:5])

            if top_bid_volume == 0 or top_ask_volume == 0:
                return None

            imbalance_ratio = max(top_bid_volume, top_ask_volume) / min(top_bid_volume, top_ask_volume)

            # Пороговое значение для подозрения на манипуляцию
            manipulation_threshold = 10.0

            if imbalance_ratio > manipulation_threshold:
                manipulation_severity = self._determine_manipulation_severity(imbalance_ratio)

                return VetoTrigger(
                    reason=VetoReasonEnum.ORDERBOOK_MANIPULATION,
                    severity=manipulation_severity,
                    confidence=min(1.0, imbalance_ratio / manipulation_threshold / 2),
                    message=f"Подозрение на манипуляцию orderbook: дисбаланс {imbalance_ratio:.1f}x",
                    data={
                        "imbalance_ratio": imbalance_ratio,
                        "top_bid_volume": top_bid_volume,
                        "top_ask_volume": top_ask_volume,
                        "stronger_side": "bid" if top_bid_volume > top_ask_volume else "ask"
                    },
                    affected_symbols=[symbol],
                    duration_estimate_ms=600000,  # 10 минут
                    auto_recovery=True
                )

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка проверки orderbook manipulation: {e}")
            return None

    def _determine_manipulation_severity(self, imbalance_ratio: float) -> VetoSeverityEnum:
        """Определение серьёзности manipulation вето"""
        if imbalance_ratio >= 50.0:
            return VetoSeverityEnum.CRITICAL
        elif imbalance_ratio >= 25.0:
            return VetoSeverityEnum.HIGH
        elif imbalance_ratio >= 15.0:
            return VetoSeverityEnum.MEDIUM
        else:
            return VetoSeverityEnum.LOW

    async def _check_news_conflicts(self, news_sentiment: Dict, symbol: str) -> Optional[VetoTrigger]:
        """Проверка конфликтных новостей"""
        try:
            # Получаем sentiment для символа
            symbol_sentiment = news_sentiment.get(symbol)
            if not symbol_sentiment:
                return None

            # Проверяем на конфликтные сигналы
            bullish_count = symbol_sentiment.bullish_count
            bearish_count = symbol_sentiment.bearish_count
            total_count = symbol_sentiment.total_news_count

            if total_count < 3:  # Недостаточно новостей для анализа
                return None

            # Рассчитываем степень конфликта
            if bullish_count > 0 and bearish_count > 0:
                conflict_ratio = min(bullish_count, bearish_count) / max(bullish_count, bearish_count)

                # Высокий конфликт когда соотношение близко к 1:1
                if conflict_ratio > 0.6:  # 60% конфликта
                    conflict_severity = self._determine_news_conflict_severity(conflict_ratio, symbol_sentiment.confidence)

                    return VetoTrigger(
                        reason=VetoReasonEnum.NEWS_CONFLICT,
                        severity=conflict_severity,
                        confidence=conflict_ratio * self.sensitivity_settings["news_conflict"],
                        message=f"Конфликт новостей: {bullish_count} bullish vs {bearish_count} bearish",
                        data={
                            "bullish_count": bullish_count,
                            "bearish_count": bearish_count,
                            "total_count": total_count,
                            "conflict_ratio": conflict_ratio,
                            "overall_sentiment": symbol_sentiment.overall_sentiment,
                            "confidence": symbol_sentiment.confidence
                        },
                        affected_symbols=[symbol],
                        duration_estimate_ms=1800000,  # 30 минут
                        auto_recovery=True
                    )

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка проверки news conflicts: {e}")
            return None

    def _determine_news_conflict_severity(self, conflict_ratio: float, news_confidence: float) -> VetoSeverityEnum:
        """Определение серьёзности news conflict"""
        # Учитываем как степень конфликта, так и уверенность новостного анализа
        severity_score = conflict_ratio * news_confidence

        if severity_score >= 0.9:
            return VetoSeverityEnum.HIGH
        elif severity_score >= 0.7:
            return VetoSeverityEnum.MEDIUM
        else:
            return VetoSeverityEnum.LOW

    async def _update_active_vetos(self, new_triggers: List[VetoTrigger], current_time: int):
        """Обновление активных вето"""
        try:
            # Добавляем новые триггеры
            for trigger in new_triggers:
                veto_key = f"{trigger.reason.value}_{trigger.affected_symbols[0] if trigger.affected_symbols else 'global'}"
                self.active_vetos[veto_key] = trigger

                # Добавляем в историю
                self.veto_history.append(trigger)

                # Обновляем статистику
                self._update_veto_stats(trigger)

            # Удаляем истёкшие вето (если включено auto_recovery)
            expired_keys = []
            for key, veto in self.active_vetos.items():
                if veto.auto_recovery and (current_time - veto.timestamp) > veto.duration_estimate_ms:
                    expired_keys.append(key)

            for key in expired_keys:
                expired_veto = self.active_vetos.pop(key)
                logger.info(f"⏰ Вето истекло: {expired_veto.reason.value} для {expired_veto.affected_symbols}")

        except Exception as e:
            logger.error(f"❌ Ошибка обновления active vetos: {e}")

    def _update_veto_stats(self, trigger: VetoTrigger):
        """Обновление статистики вето"""
        try:
            self.veto_stats["total_vetos"] += 1
            self.veto_stats["vetos_by_reason"][trigger.reason.value] += 1
            self.veto_stats["vetos_by_severity"][trigger.severity.value] += 1

            # Определяем наиболее частую причину
            most_common = max(self.veto_stats["vetos_by_reason"], key=self.veto_stats["vetos_by_reason"].get)
            self.veto_stats["most_common_reason"] = most_common

        except Exception as e:
            logger.error(f"❌ Ошибка обновления veto stats: {e}")

    def _calculate_risk_score(self, veto_triggers: List[VetoTrigger], market_data: Dict) -> float:
        """Расчёт общего риск-скора"""
        try:
            if not veto_triggers:
                return 0.0

            # Базовый риск от триггеров
            severity_weights = {
                VetoSeverityEnum.LOW: 0.2,
                VetoSeverityEnum.MEDIUM: 0.4,
                VetoSeverityEnum.HIGH: 0.7,
                VetoSeverityEnum.CRITICAL: 1.0
            }

            trigger_risks = []
            for trigger in veto_triggers:
                severity_weight = severity_weights.get(trigger.severity, 0.3)
                risk = severity_weight * trigger.confidence
                trigger_risks.append(risk)

            # Комбинируем риски (не простое среднее, а учитываем множественные факторы)
            if len(trigger_risks) == 1:
                base_risk = trigger_risks[0]
            else:
                # Используем формулу для комбинирования независимых рисков
                combined_risk = 1.0
                for risk in trigger_risks:
                    combined_risk *= (1.0 - risk)
                base_risk = 1.0 - combined_risk

            # Дополнительные факторы риска из market_data
            market_risk_factors = self._assess_market_risk_factors(market_data)
            final_risk = base_risk * (1.0 + market_risk_factors * 0.3)

            return min(1.0, final_risk)

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта risk score: {e}")
            return 0.5

    def _assess_market_risk_factors(self, market_data: Dict) -> float:
        """Оценка дополнительных факторов риска из market_data"""
        try:
            risk_factors = []

            # Фактор волатильности
            ticker = market_data.get("ticker", {})
            price_change = abs(safe_float(ticker.get("price_24h_pcnt", 0)))
            volatility_factor = min(1.0, price_change / 20.0)  # Нормализуем к 20%
            risk_factors.append(volatility_factor)

            # Фактор объёма (аномально низкий или высокий)
            volume_24h = safe_float(ticker.get("volume_24h", 0))
            if len(self.volume_history) > 5:
                recent_volumes = [entry["volume"] for entry in list(self.volume_history)[-5:]]
                avg_volume = sum(recent_volumes) / len(recent_volumes)
                if avg_volume > 0:
                    volume_deviation = abs(volume_24h - avg_volume) / avg_volume
                    volume_factor = min(1.0, volume_deviation / 2.0)  # Нормализуем к 200%
                    risk_factors.append(volume_factor)

            # Фактор спреда
            orderbook = market_data.get("orderbook", {})
            spread_bps = safe_float(orderbook.get("spread_bps", 0))
            if spread_bps > 0:
                spread_factor = min(1.0, spread_bps / 100.0)  # Нормализуем к 100 bps
                risk_factors.append(spread_factor)

            return sum(risk_factors) / max(len(risk_factors), 1)

        except Exception as e:
            logger.error(f"❌ Ошибка оценки market risk factors: {e}")
            return 0.0

    def _calculate_market_stability(self, market_data: Dict, volume_profile: Any) -> float:
        """Расчёт стабильности рынка"""
        try:
            stability_factors = []

            # Фактор спреда (узкий спред = более стабильный рынок)
            orderbook = market_data.get("orderbook", {})
            spread_bps = safe_float(orderbook.get("spread_bps", 0))
            if spread_bps > 0:
                spread_stability = max(0.0, 1.0 - (spread_bps / 50.0))  # 50 bps как базовый уровень
                stability_factors.append(spread_stability)

            # Фактор волатильности (низкая волатильность = более стабильный)
            ticker = market_data.get("ticker", {})
            price_change = abs(safe_float(ticker.get("price_24h_pcnt", 0)))
            volatility_stability = max(0.0, 1.0 - (price_change / 10.0))  # 10% как базовый уровень
            stability_factors.append(volatility_stability)

            # Фактор объёма (стабильный объём = более стабильный рынок)
            if len(self.volume_history) >= 5:
                recent_volumes = [entry["volume"] for entry in list(self.volume_history)[-5:]]
                volume_std = np.std(recent_volumes) if len(recent_volumes) > 1 else 0
                volume_mean = np.mean(recent_volumes)
                if volume_mean > 0:
                    volume_cv = volume_std / volume_mean  # Коэффициент вариации
                    volume_stability = max(0.0, 1.0 - volume_cv)
                    stability_factors.append(volume_stability)

            # Фактор funding rate (близость к нулю = более стабильный)
            funding_data = market_data.get("funding_rate", {})
            funding_rate = abs(safe_float(funding_data.get("funding_rate", 0)))
            funding_stability = max(0.0, 1.0 - (funding_rate / 0.01))  # 1% как базовый уровень
            stability_factors.append(funding_stability)

            if not stability_factors:
                return 0.5  # Нейтральная стабильность по умолчанию

            return sum(stability_factors) / len(stability_factors)

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта market stability: {e}")
            return 0.5

    def _generate_recommendation(
        self,
        veto_triggers: List[VetoTrigger],
        risk_score: float,
        market_stability: float
    ) -> str:
        """Генерация рекомендации на основе анализа"""
        try:
            if not veto_triggers and risk_score < 0.3:
                return "✅ Рыночные условия благоприятны для торговли"

            recommendations = []

            # Анализ по типам вето
            high_severity_count = len([t for t in veto_triggers if t.severity in [VetoSeverityEnum.HIGH, VetoSeverityEnum.CRITICAL]])

            if high_severity_count > 0:
                recommendations.append("🚨 Обнаружены критические риски - торговля не рекомендуется")

            if risk_score > 0.7:
                recommendations.append("⚠️ Высокий общий риск - дождитесь улучшения условий")
            elif risk_score > 0.4:
                recommendations.append("⚡ Умеренный риск - торгуйте с повышенной осторожностью")

            if market_stability < 0.3:
                recommendations.append("📉 Нестабильный рынок - избегайте крупных позиций")
            elif market_stability < 0.6:
                recommendations.append("⚖️ Умеренная стабильность - используйте тайт стоп-лоссы")

            # Специфические рекомендации по типам вето
            for trigger in veto_triggers:
                if trigger.reason == VetoReasonEnum.HIGH_FUNDING_RATE:
                    recommendations.append("💰 Высокий funding rate - ожидайте коррекции")
                elif trigger.reason == VetoReasonEnum.EXTREME_VOLUME_ANOMALY:
                    recommendations.append("📊 Аномальный объём - возможны резкие движения")
                elif trigger.reason == VetoReasonEnum.LIQUIDATION_CASCADE:
                    recommendations.append("⚡ Каскад ликвидации - дождитесь стабилизации")

            return " | ".join(recommendations) if recommendations else "⚠️ Рекомендуется осторожность"

        except Exception as e:
            logger.error(f"❌ Ошибка генерации рекомендации: {e}")
            return "❌ Ошибка анализа - торговля не рекомендуется"

    def _get_veto_history_summary(self) -> Dict[str, Any]:
        """Получение сводки истории вето"""
        try:
            if not self.veto_history:
                return {"total_count": 0}

            recent_time = current_epoch_ms() - 3600000  # Последний час
            recent_vetos = [v for v in self.veto_history if v.timestamp > recent_time]

            return {
                "total_count": len(self.veto_history),
                "recent_hour_count": len(recent_vetos),
                "most_common_reason": self.veto_stats.get("most_common_reason"),
                "total_by_severity": dict(self.veto_stats["vetos_by_severity"]),
                "accuracy_rate": self.veto_stats.get("accuracy_rate", 0.0)
            }

        except Exception as e:
            logger.error(f"❌ Ошибка получения veto history summary: {e}")
            return {"error": str(e)}

    def _create_no_data_result(self, current_time: int) -> VetoAnalysisResult:
        """Создание результата при отсутствии данных"""
        return VetoAnalysisResult(
            is_vetoed=True,  # Вето при отсутствии данных
            active_vetos=[
                VetoTrigger(
                    reason=VetoReasonEnum.LOW_LIQUIDITY,
                    severity=VetoSeverityEnum.HIGH,
                    confidence=1.0,
                    message="Недостаточно рыночных данных для анализа",
                    affected_symbols=[],
                    duration_estimate_ms=300000
                )
            ],
            risk_score=0.8,
            market_stability=0.1,
            recommendation="❌ Недостаточно данных - торговля не рекомендуется",
            analysis_timestamp=current_time,
            next_check_time=current_time + 60000,
            veto_history_summary={"no_data": True}
        )

    def _create_error_result(self, current_time: int, error_msg: str) -> VetoAnalysisResult:
        """Создание результата при ошибке анализа"""
        return VetoAnalysisResult(
            is_vetoed=True,  # Вето при ошибке
            active_vetos=[
                VetoTrigger(
                    reason=VetoReasonEnum.MARKET_INSTABILITY,
                    severity=VetoSeverityEnum.MEDIUM,
                    confidence=0.5,
                    message=f"Ошибка анализа veto системы: {error_msg}",
                    affected_symbols=[],
                    duration_estimate_ms=600000
                )
            ],
            risk_score=0.6,
            market_stability=0.3,
            recommendation="⚠️ Ошибка анализа - торговля не рекомендуется",
            analysis_timestamp=current_time,
            next_check_time=current_time + 120000,  # Больше времени до следующей проверки
            veto_history_summary={"error": error_msg}
        )

    def _log_veto_result(self, result: VetoAnalysisResult, symbol: str):
        """Логирование результата вето"""
        try:
            active_reasons = [veto.reason.value for veto in result.active_vetos]
            severity_colors = {
                VetoSeverityEnum.LOW: Colors.INFO,
                VetoSeverityEnum.MEDIUM: Colors.ALERT,
                VetoSeverityEnum.HIGH: Colors.BEARISH,
                VetoSeverityEnum.CRITICAL: Colors.VETO
            }

            if result.active_vetos:
                max_severity = max(veto.severity for veto in result.active_vetos)
                color = severity_colors.get(max_severity, Colors.ALERT)
            else:
                color = Colors.ALERT

            logger.warning(
                f"{color}🛑 VETO АКТИВИРОВАНО{Colors.END} для {symbol}: "
                f"{', '.join(active_reasons)} | Risk: {result.risk_score:.2f} | "
                f"Stability: {result.market_stability:.2f}"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка логирования veto result: {e}")

    def clear_expired_vetos(self):
        """Принудительная очистка истёкших вето"""
        try:
            current_time = current_epoch_ms()
            expired_count = 0

            expired_keys = []
            for key, veto in self.active_vetos.items():
                if (current_time - veto.timestamp) > veto.duration_estimate_ms:
                    expired_keys.append(key)

            for key in expired_keys:
                self.active_vetos.pop(key)
                expired_count += 1

            if expired_count > 0:
                logger.info(f"🧹 Очищено {expired_count} истёкших вето")

            return expired_count

        except Exception as e:
            logger.error(f"❌ Ошибка очистки expired vetos: {e}")
            return 0

    def get_veto_stats(self) -> Dict[str, Any]:
        """Получение детальной статистики системы вето"""
        try:
            return {
                "active_vetos_count": len(self.active_vetos),
                "active_vetos": {key: {
                    "reason": veto.reason.value,
                    "severity": veto.severity.value,
                    "confidence": veto.confidence,
                    "age_minutes": (current_epoch_ms() - veto.timestamp) / 60000,
                    "symbols": veto.affected_symbols
                } for key, veto in self.active_vetos.items()},
                "history_stats": self.veto_stats.copy(),
                "adaptive_thresholds": self.adaptive_thresholds.copy(),
                "sensitivity_settings": self.sensitivity_settings.copy(),
                "data_counts": {
                    "funding_rate_history": len(self.funding_rate_history),
                    "volume_history": len(self.volume_history),
                    "spread_history": len(self.spread_history),
                    "liquidation_events": len(self.liquidation_events)
                }
            }

        except Exception as e:
            logger.error(f"❌ Ошибка получения veto stats: {e}")
            return {"error": str(e)}


# Экспорт классов
__all__ = [
    'EnhancedVetoSystem',
    'VetoTrigger',
    'VetoAnalysisResult',
    'VetoSeverityEnum',
]
