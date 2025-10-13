#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Премиум система алертов для ликвидаций, всплесков объемов и дисбалансов
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import deque
from config.settings import logger


class PremiumAlertSystem:
    """
    Премиум система алертов с мониторингом:
    - Ликвидаций (крупных)
    - Всплесков объемов
    - Дисбалансов orderbook
    - Sentiment новостей
    """

    def __init__(self):
        # Пороги для алертов
        self.liquidation_threshold_usd = 1_000_000  # $1M+
        self.volume_spike_multiplier = 3.0  # 3x от среднего
        self.imbalance_threshold = 2.0  # ratio 2:1

        # История для расчета средних
        self.volume_history = {}  # symbol -> deque of volumes
        self.history_window = 20  # последние 20 периодов

        # Кэш алертов (чтобы не дублировать)
        self.recent_alerts = deque(maxlen=100)

        logger.info("✅ PremiumAlertSystem инициализирована")

    async def check_liquidations(
        self,
        symbol: str,
        liquidations: List[Dict]
    ) -> Optional[Dict]:
        """
        Проверка крупных ликвидаций

        Args:
            symbol: торговая пара
            liquidations: список ликвидаций с полями side, price, quantity

        Returns:
            Dict с алертом если найдена крупная ликвидация
        """
        try:
            if not liquidations:
                return None

            # Фильтрация крупных ликвидаций
            large_liquidations = []

            for liq in liquidations:
                value_usd = float(liq.get('price', 0)) * float(liq.get('quantity', 0))

                if value_usd >= self.liquidation_threshold_usd:
                    large_liquidations.append({
                        'side': liq.get('side', 'unknown'),
                        'price': float(liq.get('price', 0)),
                        'quantity': float(liq.get('quantity', 0)),
                        'value_usd': value_usd,
                        'timestamp': liq.get('timestamp', datetime.now().isoformat())
                    })

            if not large_liquidations:
                return None

            # Суммирование по сторонам
            long_liq_total = sum(
                liq['value_usd'] for liq in large_liquidations
                if liq['side'] == 'long'
            )
            short_liq_total = sum(
                liq['value_usd'] for liq in large_liquidations
                if liq['side'] == 'short'
            )

            total_liquidated = long_liq_total + short_liq_total

            # Определение доминирующей стороны
            if long_liq_total > short_liq_total * 1.5:
                dominant_side = 'long'
                implication = 'bearish'
            elif short_liq_total > long_liq_total * 1.5:
                dominant_side = 'short'
                implication = 'bullish'
            else:
                dominant_side = 'mixed'
                implication = 'neutral'

            alert = {
                'type': 'LIQUIDATION',
                'symbol': symbol,
                'severity': 'HIGH' if total_liquidated > 5_000_000 else 'MEDIUM',
                'total_liquidated_usd': total_liquidated,
                'long_liquidations': long_liq_total,
                'short_liquidations': short_liq_total,
                'dominant_side': dominant_side,
                'market_implication': implication,
                'count': len(large_liquidations),
                'timestamp': datetime.now().isoformat()
            }

            # Проверка дубликатов
            if not self._is_duplicate_alert(alert):
                self.recent_alerts.append(alert)

                logger.warning(
                    f"🚨 LIQUIDATION ALERT {symbol}: "
                    f"${total_liquidated:,.0f} liquidated "
                    f"({dominant_side} dominant → {implication})"
                )

                return alert

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка проверки ликвидаций {symbol}: {e}")
            return None

    async def check_volume_spike(
        self,
        symbol: str,
        current_volume: float
    ) -> Optional[Dict]:
        """
        Проверка всплесков объема

        Args:
            symbol: торговая пара
            current_volume: текущий объем за период

        Returns:
            Dict с алертом если обнаружен всплеск
        """
        try:
            # Инициализация истории для символа
            if symbol not in self.volume_history:
                self.volume_history[symbol] = deque(maxlen=self.history_window)

            history = self.volume_history[symbol]

            # Недостаточно истории для анализа
            if len(history) < 5:
                history.append(current_volume)
                return None

            # Расчет среднего и стандартного отклонения
            avg_volume = sum(history) / len(history)
            std_dev = (
                sum((v - avg_volume) ** 2 for v in history) / len(history)
            ) ** 0.5

            # Проверка на всплеск
            spike_multiplier = current_volume / avg_volume if avg_volume > 0 else 0

            if spike_multiplier >= self.volume_spike_multiplier:
                # Определение силы всплеска
                z_score = (current_volume - avg_volume) / std_dev if std_dev > 0 else 0

                if z_score >= 3:
                    severity = 'EXTREME'
                elif z_score >= 2:
                    severity = 'HIGH'
                else:
                    severity = 'MEDIUM'

                alert = {
                    'type': 'VOLUME_SPIKE',
                    'symbol': symbol,
                    'severity': severity,
                    'current_volume': current_volume,
                    'average_volume': avg_volume,
                    'spike_multiplier': round(spike_multiplier, 2),
                    'z_score': round(z_score, 2),
                    'timestamp': datetime.now().isoformat()
                }

                if not self._is_duplicate_alert(alert):
                    self.recent_alerts.append(alert)

                    logger.warning(
                        f"🚨 VOLUME SPIKE {symbol}: "
                        f"{spike_multiplier:.2f}x average "
                        f"({severity})"
                    )

                    history.append(current_volume)
                    return alert

            # Обновление истории
            history.append(current_volume)
            return None

        except Exception as e:
            logger.error(f"❌ Ошибка проверки volume spike {symbol}: {e}")
            return None

    async def check_orderbook_imbalance(
        self,
        symbol: str,
        imbalance_data: Dict
    ) -> Optional[Dict]:
        """
        Проверка сильных дисбалансов в orderbook

        Args:
            symbol: торговая пара
            imbalance_data: данные из ExoChartsVolumeProfileL2

        Returns:
            Dict с алертом если обнаружен сильный дисбаланс
        """
        try:
            ratio = imbalance_data.get('ratio', 1.0)
            imbalance_type = imbalance_data.get('type', 'balanced')
            strength = imbalance_data.get('strength', 0)

            # Проверка на сильный дисбаланс
            if ratio >= self.imbalance_threshold or ratio <= 1 / self.imbalance_threshold:

                if ratio >= 3.0 or ratio <= 0.33:
                    severity = 'EXTREME'
                elif ratio >= 2.5 or ratio <= 0.4:
                    severity = 'HIGH'
                else:
                    severity = 'MEDIUM'

                # Определение направления
                if imbalance_type == 'strong_bid':
                    direction = 'BULLISH'
                    side_ratio = f"{ratio:.2f}:1 (bid dominance)"
                elif imbalance_type == 'strong_ask':
                    direction = 'BEARISH'
                    side_ratio = f"1:{1/ratio:.2f} (ask dominance)"
                else:
                    direction = 'NEUTRAL'
                    side_ratio = "balanced"

                alert = {
                    'type': 'ORDERBOOK_IMBALANCE',
                    'symbol': symbol,
                    'severity': severity,
                    'direction': direction,
                    'bid_ask_ratio': ratio,
                    'side_ratio': side_ratio,
                    'strength': strength,
                    'timestamp': datetime.now().isoformat()
                }

                if not self._is_duplicate_alert(alert):
                    self.recent_alerts.append(alert)

                    logger.warning(
                        f"🚨 ORDERBOOK IMBALANCE {symbol}: "
                        f"{side_ratio} → {direction} ({severity})"
                    )

                    return alert

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка проверки imbalance {symbol}: {e}")
            return None

    async def check_sentiment_alert(
        self,
        sentiment_data: Dict
    ) -> Optional[Dict]:
        """
        Проверка экстремальных изменений sentiment

        Args:
            sentiment_data: результат от PremiumSentimentAnalyzer

        Returns:
            Dict с алертом если sentiment экстремальный
        """
        try:
            score = sentiment_data.get('overall_score', 0)
            sentiment = sentiment_data.get('sentiment', 'neutral')

            # Алерт только на экстремальные значения
            if abs(score) >= 60:

                if abs(score) >= 80:
                    severity = 'EXTREME'
                else:
                    severity = 'HIGH'

                key_events = sentiment_data.get('key_events', [])[:3]

                alert = {
                    'type': 'SENTIMENT_EXTREME',
                    'severity': severity,
                    'sentiment': sentiment,
                    'score': score,
                    'key_events': key_events,
                    'total_news': sentiment_data.get('total_news', 0),
                    'timestamp': datetime.now().isoformat()
                }

                if not self._is_duplicate_alert(alert):
                    self.recent_alerts.append(alert)

                    logger.warning(
                        f"🚨 SENTIMENT ALERT: {sentiment.upper()} "
                        f"(score: {score:.1f}) - {severity}"
                    )

                    return alert

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка проверки sentiment alert: {e}")
            return None

    def _is_duplicate_alert(self, alert: Dict) -> bool:
        """Проверка на дублирование алертов (в течение 5 минут)"""
        alert_signature = f"{alert['type']}_{alert.get('symbol', 'global')}"
        cutoff_time = datetime.now() - timedelta(minutes=5)

        for recent_alert in self.recent_alerts:
            if recent_alert.get('type') == alert['type'] and \
               recent_alert.get('symbol') == alert.get('symbol'):
                alert_time = datetime.fromisoformat(recent_alert['timestamp'])
                if alert_time > cutoff_time:
                    return True

        return False

    def get_recent_alerts(self, limit: int = 10) -> List[Dict]:
        """Получение последних алертов"""
        return list(self.recent_alerts)[-limit:]
