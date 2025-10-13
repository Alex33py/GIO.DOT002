# -*- coding: utf-8 -*-
"""
Decision Matrix для комплексного анализа торговых условий
Реализация всех политик: mtf, news, triggers, veto
"""

from typing import Dict, List, Optional
from datetime import datetime
from config.settings import logger

class DecisionMatrix:
    """
    Матрица принятия решений на основе множественных факторов
    """

    def __init__(self):
        # Веса политик (сумма = 1.0)
        self.weights = {
            'mtf_policy': 0.35,      # Мульти-таймфрейм анализ
            'news_policy': 0.20,     # Новостной сентимент
            'triggers_policy': 0.25, # Технические триггеры
            'volume_policy': 0.10,   # Объёмный анализ
            'risk_policy': 0.10      # Риск-менеджмент
        }

        # Veto условия (блокируют сигнал)
        self.veto_conditions = {
            'funding_rate_high': 0.01,      # > 1%
            'spread_too_wide': 0.005,       # > 0.5%
            'low_liquidity': 100000,        # < $100k
            'extreme_volatility': 5.0,      # > 5% ATR
            'orderbook_imbalance': 0.80     # > 80% дисбаланс
        }

        logger.info("✅ DecisionMatrix инициализирована")

    def evaluate(self, scenario: Dict, market_data: Dict, indicators: Dict,
                 news_data: Dict, veto_checks: Dict) -> Dict:
        """
        Комплексная оценка торговой возможности

        Returns:
            {
                'score': float (0-1),
                'decision': str ('deal', 'risky_entry', 'observation', 'reject'),
                'breakdown': Dict (детализация по политикам),
                'veto_triggered': bool,
                'veto_reasons': List[str]
            }
        """

        # 1. Проверяем VETO условия (приоритет #1)
        veto_result = self._evaluate_veto(veto_checks, market_data)
        if veto_result['triggered']:
            return {
                'score': 0.0,
                'decision': 'reject',
                'breakdown': {},
                'veto_triggered': True,
                'veto_reasons': veto_result['reasons']
            }

        # 2. Оцениваем каждую политику
        breakdown = {}

        # MTF Policy
        mtf_score = self._evaluate_mtf_policy(scenario, indicators)
        breakdown['mtf_policy'] = {
            'score': mtf_score,
            'weight': self.weights['mtf_policy'],
            'weighted_score': mtf_score * self.weights['mtf_policy']
        }

        # News Policy
        news_score = self._evaluate_news_policy(scenario, news_data, market_data)
        breakdown['news_policy'] = {
            'score': news_score,
            'weight': self.weights['news_policy'],
            'weighted_score': news_score * self.weights['news_policy']
        }

        # Triggers Policy
        triggers_score = self._evaluate_triggers_policy(scenario, indicators, market_data)
        breakdown['triggers_policy'] = {
            'score': triggers_score,
            'weight': self.weights['triggers_policy'],
            'weighted_score': triggers_score * self.weights['triggers_policy']
        }

        # Volume Policy
        volume_score = self._evaluate_volume_policy(market_data, indicators)
        breakdown['volume_policy'] = {
            'score': volume_score,
            'weight': self.weights['volume_policy'],
            'weighted_score': volume_score * self.weights['volume_policy']
        }

        # Risk Policy
        risk_score = self._evaluate_risk_policy(scenario, market_data, indicators)
        breakdown['risk_policy'] = {
            'score': risk_score,
            'weight': self.weights['risk_policy'],
            'weighted_score': risk_score * self.weights['risk_policy']
        }

        # 3. Итоговый score
        total_score = sum([p['weighted_score'] for p in breakdown.values()])

        # 4. Принимаем решение
        if total_score >= 0.75:
            decision = 'deal'
        elif total_score >= 0.55:
            decision = 'risky_entry'
        elif total_score >= 0.35:
            decision = 'observation'
        else:
            decision = 'reject'

        logger.info(f"📊 Decision Matrix: {decision.upper()} (score: {total_score:.2f})")

        return {
            'score': total_score,
            'decision': decision,
            'breakdown': breakdown,
            'veto_triggered': False,
            'veto_reasons': []
        }

    def _evaluate_veto(self, veto_checks: Dict, market_data: Dict) -> Dict:
        """Проверка VETO условий"""
        reasons = []

        # Funding rate
        funding_rate = market_data.get('funding_rate', 0)
        if abs(funding_rate) > self.veto_conditions['funding_rate_high']:
            reasons.append(f"Высокая ставка фондирования: {funding_rate:.4f}")

        # Spread
        spread = market_data.get('spread_percent', 0)
        if spread > self.veto_conditions['spread_too_wide']:
            reasons.append(f"Широкий спред: {spread:.3f}%")

        # Liquidity
        liquidity = market_data.get('liquidity_24h', float('inf'))
        if liquidity < self.veto_conditions['low_liquidity']:
            reasons.append(f"Низкая ликвидность: ${liquidity:,.0f}")

        # Volatility
        atr_percent = market_data.get('atr_percent', 0)
        if atr_percent > self.veto_conditions['extreme_volatility']:
            reasons.append(f"Экстремальная волатильность: {atr_percent:.2f}%")

        # Orderbook imbalance
        ob_imbalance = market_data.get('orderbook_imbalance', 0.5)
        if ob_imbalance > self.veto_conditions['orderbook_imbalance']:
            reasons.append(f"Сильный дисбаланс стакана: {ob_imbalance:.1%}")

        # Внешние veto
        if veto_checks.get('has_veto', False):
            reasons.extend(veto_checks.get('veto_reasons', []))

        return {
            'triggered': len(reasons) > 0,
            'reasons': reasons
        }

    def _evaluate_mtf_policy(self, scenario: Dict, indicators: Dict) -> float:
        """
        Оценка мульти-таймфрейм политики
        Требует совпадения трендов на всех ТФ
        """
        required_trend = scenario.get('mtf_trend', 'bullish')

        trends = {
            '1h': indicators.get('trend_1h', 'neutral'),
            '4h': indicators.get('trend_4h', 'neutral'),
            '1d': indicators.get('trend_1d', 'neutral')
        }

        # Подсчёт совпадений
        matches = sum(1 for tf_trend in trends.values() if tf_trend == required_trend)

        # Дополнительная проверка силы тренда
        trend_strength = indicators.get('trend_strength', 0.5)

        # Базовый score по совпадениям
        if matches == 3:
            base_score = 1.0
        elif matches == 2:
            base_score = 0.7
        elif matches == 1:
            base_score = 0.4
        else:
            base_score = 0.2

        # Корректировка на силу тренда
        final_score = base_score * (0.7 + trend_strength * 0.3)

        logger.debug(f"🔍 MTF Policy: {matches}/3 трендов совпали, strength: {trend_strength:.2f}, score: {final_score:.2f}")

        return final_score

    def _evaluate_news_policy(self, scenario: Dict, news_data: Dict, market_data: Dict) -> float:
        """
        Оценка новостной политики
        Учитывает sentiment и релевантность
        """
        direction = scenario.get('direction', 'long')
        sentiment = news_data.get('weighted_sentiment', 0)  # от -1 до +1
        relevance = news_data.get('relevance_score', 0.5)  # 0-1

        # Совпадение направления с sentiment
        if direction == 'long':
            direction_match = max(0, sentiment)  # позитивный sentiment
        else:
            direction_match = max(0, -sentiment)  # негативный sentiment

        # Итоговый score = совпадение * релевантность
        score = direction_match * relevance

        # Бонус за экстремальный sentiment
        if abs(sentiment) > 0.7:
            score = min(score * 1.2, 1.0)

        logger.debug(f"📰 News Policy: sentiment={sentiment:.2f}, relevance={relevance:.2f}, score={score:.2f}")

        return score

    def _evaluate_triggers_policy(self, scenario: Dict, indicators: Dict, market_data: Dict) -> float:
        """
        Оценка политики триггеров
        T1: технический паттерн
        T2: объёмное подтверждение
        T3: CVD подтверждение
        """
        triggers_fired = 0
        trigger_details = []

        direction = scenario.get('direction', 'long')

        # T1: Технический триггер (RSI + MACD)
        rsi = indicators.get('rsi_1h', 50)
        macd_histogram = indicators.get('macd_histogram_1h', 0)

        if direction == 'long':
            if 30 < rsi < 50 and macd_histogram > 0:
                triggers_fired += 1
                trigger_details.append("T1: RSI oversold + MACD bullish")
        else:
            if 50 < rsi < 70 and macd_histogram < 0:
                triggers_fired += 1
                trigger_details.append("T1: RSI overbought + MACD bearish")

        # T2: Объёмный триггер
        volume_ratio = market_data.get('volume_ratio', 1.0)
        if volume_ratio > 1.5:
            triggers_fired += 1
            trigger_details.append(f"T2: Volume spike {volume_ratio:.1f}x")

        # T3: CVD триггер
        cvd = market_data.get('cvd', 0)
        cvd_aligned = (direction == 'long' and cvd > 0) or (direction == 'short' and cvd < 0)
        if cvd_aligned:
            triggers_fired += 1
            trigger_details.append(f"T3: CVD aligned ({cvd:,.0f})")

        score = triggers_fired / 3.0

        logger.debug(f"🎯 Triggers Policy: {triggers_fired}/3 сработало, score={score:.2f}, детали: {trigger_details}")

        return score

    def _evaluate_volume_policy(self, market_data: Dict, indicators: Dict) -> float:
        """Оценка объёмной политики"""
        volume_ratio = market_data.get('volume_ratio', 1.0)
        volume_profile_score = indicators.get('volume_profile_score', 0.5)

        # Комбинируем объём и профиль
        score = (volume_ratio / 5.0) * 0.5 + volume_profile_score * 0.5
        score = min(score, 1.0)

        return score

    def _evaluate_risk_policy(self, scenario: Dict, market_data: Dict, indicators: Dict) -> float:
        """Оценка риск-политики"""
        # R/R ratio
        rr_ratio = scenario.get('rr_ratio', 0)
        if rr_ratio < 1.5:
            return 0.3  # Плохое R/R
        elif rr_ratio < 2.0:
            return 0.6
        elif rr_ratio < 3.0:
            return 0.8
        else:
            return 1.0  # Отличное R/R
