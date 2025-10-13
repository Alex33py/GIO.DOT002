# -*- coding: utf-8 -*-
"""
Система алертов для GIO Crypto Bot
Отслеживание: ликвидаций, всплесков объёмов, дисбалансов стакана
"""

from typing import Dict, List, Optional
from collections import deque
from datetime import datetime, timedelta
from config.settings import logger

class AlertSystem:
    """Система уведомлений о рыночных аномалиях"""

    def __init__(self):
        self.liquidation_history = deque(maxlen=100)
        self.volume_history = {}  # {symbol: deque([vol, vol, ...])}
        self.alerts_sent = {}  # Предотвращение дублирования алертов
        logger.info("✅ AlertSystem инициализирована")

    async def check_liquidations(self, symbol: str, liquidations: List[Dict]) -> Optional[Dict]:
        """
        Проверка каскадных ликвидаций
        Алерт если за последние 5 минут > 5 крупных ликвидаций
        """
        if not liquidations:
            return None

        now = datetime.now()
        recent_liq = [
            liq for liq in liquidations
            if datetime.fromtimestamp(liq.get('timestamp', 0) / 1000) > now - timedelta(minutes=5)
        ]

        if len(recent_liq) >= 5:
            total_volume = sum(liq.get('qty', 0) for liq in recent_liq)

            alert = {
                'type': 'liquidation_cascade',
                'symbol': symbol,
                'count': len(recent_liq),
                'total_volume': total_volume,
                'severity': 'high' if len(recent_liq) > 10 else 'medium',
                'timestamp': now.isoformat()
            }

            logger.warning(f"🚨 АЛЕРТ: Каскад ликвидаций {symbol}! Количество: {len(recent_liq)}, Объём: ${total_volume:,.0f}")
            return alert

        return None

    async def check_volume_spike(self, symbol: str, current_volume: float) -> Optional[Dict]:
        """
        Проверка всплеска объёма
        Алерт если текущий объём > 3x средний за последний час
        """
        if symbol not in self.volume_history:
            self.volume_history[symbol] = deque(maxlen=60)  # 60 измерений

        vol_hist = self.volume_history[symbol]
        vol_hist.append(current_volume)

        if len(vol_hist) < 10:
            return None  # Недостаточно данных

        avg_volume = sum(vol_hist) / len(vol_hist)

        if current_volume > avg_volume * 3.0:
            alert = {
                'type': 'volume_spike',
                'symbol': symbol,
                'current_volume': current_volume,
                'average_volume': avg_volume,
                'ratio': current_volume / avg_volume,
                'severity': 'high' if current_volume > avg_volume * 5 else 'medium',
                'timestamp': datetime.now().isoformat()
            }

            logger.warning(f"🚨 АЛЕРТ: Всплеск объёма {symbol}! Текущий: {current_volume:,.0f}, Средний: {avg_volume:,.0f}, Рост: {current_volume/avg_volume:.1f}x")
            return alert

        return None

    async def check_orderbook_imbalance(self, symbol: str, bids: float, asks: float) -> Optional[Dict]:
        """
        Проверка дисбаланса стакана
        Алерт если соотношение bid/ask > 70%/30% или < 30%/70%
        """
        if not bids or not asks:
            return None

        total = bids + asks
        bid_ratio = bids / total
        ask_ratio = asks / total

        threshold = 0.70

        if bid_ratio > threshold:
            alert = {
                'type': 'orderbook_imbalance',
                'symbol': symbol,
                'direction': 'bullish',
                'bid_ratio': bid_ratio,
                'ask_ratio': ask_ratio,
                'severity': 'high' if bid_ratio > 0.80 else 'medium',
                'timestamp': datetime.now().isoformat()
            }

            logger.warning(f"🚨 АЛЕРТ: Дисбаланс стакана {symbol}! Bids: {bid_ratio:.1%}, Asks: {ask_ratio:.1%} (бычий сигнал)")
            return alert

        elif ask_ratio > threshold:
            alert = {
                'type': 'orderbook_imbalance',
                'symbol': symbol,
                'direction': 'bearish',
                'bid_ratio': bid_ratio,
                'ask_ratio': ask_ratio,
                'severity': 'high' if ask_ratio > 0.80 else 'medium',
                'timestamp': datetime.now().isoformat()
            }

            logger.warning(f"🚨 АЛЕРТ: Дисбаланс стакана {symbol}! Bids: {bid_ratio:.1%}, Asks: {ask_ratio:.1%} (медвежий сигнал)")
            return alert

        return None

    async def check_news_sentiment_extreme(self, symbol: str, sentiment: float) -> Optional[Dict]:
        """
        Проверка экстремального sentiment в новостях
        Алерт если sentiment < -0.7 или > 0.7
        """
        if abs(sentiment) > 0.7:
            alert = {
                'type': 'extreme_news_sentiment',
                'symbol': symbol,
                'sentiment': sentiment,
                'direction': 'very_bullish' if sentiment > 0.7 else 'very_bearish',
                'severity': 'high',
                'timestamp': datetime.now().isoformat()
            }

            emotion = "📈 ОЧЕНЬ БЫЧИЙ" if sentiment > 0.7 else "📉 ОЧЕНЬ МЕДВЕЖИЙ"
            logger.warning(f"🚨 АЛЕРТ: {emotion} sentiment для {symbol}! Score: {sentiment:.2f}")
            return alert

        return None

    def check_liquidation_cascade(self, symbol: str, liquidations: List[Dict]) -> Optional[Dict]:
        """
        Проверка каскада ликвидаций

        Args:
            symbol: Символ
            liquidations: Список ликвидаций за последние 5 минут

        Returns:
            Алерт если обнаружен каскад
        """
        try:
            if len(liquidations) < 5:
                return None

            # Суммируем объём ликвидаций
            total_liquidated = sum(liq.get('quantity', 0) * liq.get('price', 0) for liq in liquidations)

            # Порог - 1M USD за 5 минут
            if total_liquidated > 1000000:
                return {
                    'type': 'liquidation_cascade',
                    'symbol': symbol,
                    'severity': 'critical',
                    'liquidation_count': len(liquidations),
                    'total_volume_usd': total_liquidated,
                    'message': f"🔴 КАСКАД ЛИКВИДАЦИЙ {symbol}: ${total_liquidated:,.0f} ({len(liquidations)} ликвидаций за 5 мин)",
                    'timestamp': current_epoch_ms()
                }

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка проверки ликвидаций: {e}")
            return None

    def check_volume_spike(self, symbol: str, current_volume: float, avg_volume: float) -> Optional[Dict]:
        """
        Проверка всплеска объёма

        Args:
            symbol: Символ
            current_volume: Текущий объём
            avg_volume: Средний объём

        Returns:
            Алерт если обнаружен всплеск
        """
        try:
            if avg_volume <= 0:
                return None

            volume_ratio = current_volume / avg_volume

            # Всплеск > 3x от среднего
            if volume_ratio > 3.0:
                return {
                    'type': 'volume_spike',
                    'symbol': symbol,
                    'severity': 'high' if volume_ratio > 5.0 else 'medium',
                    'volume_ratio': volume_ratio,
                    'current_volume': current_volume,
                    'avg_volume': avg_volume,
                    'message': f"📊 ВСПЛЕСК ОБЪЁМА {symbol}: {volume_ratio:.1f}x (${current_volume:,.0f} vs ${avg_volume:,.0f})",
                    'timestamp': current_epoch_ms()
                }

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка проверки объёма: {e}")
            return None

    def check_orderbook_imbalance(self, symbol: str, orderbook: Dict) -> Optional[Dict]:
        """
        Проверка дисбаланса в стакане

        Args:
            symbol: Символ
            orderbook: Данные стакана (bids, asks)

        Returns:
            Алерт если обнаружен сильный дисбаланс
        """
        try:
            bids = orderbook.get('bids', [])
            asks = orderbook.get('asks', [])

            if not bids or not asks:
                return None

            # Суммируем объём top 10 уровней
            top_bid_volume = sum(float(bid[1]) for bid in bids[:10])
            top_ask_volume = sum(float(ask[1]) for ask in asks[:10])

            total_volume = top_bid_volume + top_ask_volume

            if total_volume <= 0:
                return None

            bid_ratio = top_bid_volume / total_volume

            # Сильный дисбаланс > 70% в одну сторону
            if bid_ratio > 0.70 or bid_ratio < 0.30:
                severity = 'high' if (bid_ratio > 0.80 or bid_ratio < 0.20) else 'medium'
                direction = 'BID (покупка)' if bid_ratio > 0.5 else 'ASK (продажа)'

                return {
                    'type': 'orderbook_imbalance',
                    'symbol': symbol,
                    'severity': severity,
                    'bid_ratio': bid_ratio,
                    'ask_ratio': 1 - bid_ratio,
                    'direction': direction,
                    'message': f"⚖️ ДИСБАЛАНС СТАКАНА {symbol}: {direction} доминирует ({bid_ratio:.1%} vs {1-bid_ratio:.1%})",
                    'timestamp': current_epoch_ms()
                }

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка проверки дисбаланса: {e}")
            return None



    async def check_volume_spike(
        self,
        symbol: str,
        current_volume: float,
        avg_volume: float,
        threshold: float = 2.0
    ) -> Optional[Dict]:
        """
        Проверка всплеска объёма
        
        Args:
            symbol: Торговая пара
            current_volume: Текущий объём
            avg_volume: Средний объём
            threshold: Порог (2.0 = 200% от среднего)
            
        Returns:
            Алерт или None
        """
        try:
            if avg_volume == 0:
                return None
            
            ratio = current_volume / avg_volume
            
            if ratio > threshold:
                return {
                    'type': 'volume_spike',
                    'severity': 'high' if ratio > 3.0 else 'medium',
                    'symbol': symbol,
                    'ratio': round(ratio, 2),
                    'current': current_volume,
                    'average': avg_volume,
                    'message': f'📊 {symbol} всплеск объёма: {ratio:.1f}x от среднего',
                    'timestamp': datetime.now().isoformat()
                }
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки объёма: {e}")
            return None

    async def check_liquidation_alert(
        self, 
        symbol: str, 
        liquidations_24h: float,
        threshold_usd: float = 10_000_000
    ) -> Optional[Dict]:
        """Алерт крупных ликвидаций"""
        try:
            if liquidations_24h > threshold_usd:
                severity = 'critical' if liquidations_24h > 50_000_000 else 'high'
                
                return {
                    'type': 'liquidation',
                    'severity': severity,
                    'symbol': symbol,
                    'amount_usd': liquidations_24h,
                    'message': f'🚨 Крупные ликвидации {symbol}: ${liquidations_24h:,.0f}',
                    'timestamp': datetime.now().isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка проверки ликвидаций: {e}")
            return None
    
    async def check_orderbook_imbalance(
        self,
        symbol: str,
        bid_volume: float,
        ask_volume: float,
        threshold: float = 0.7
    ) -> Optional[Dict]:
        """Алерт дисбаланса стакана"""
        try:
            total = bid_volume + ask_volume
            if total == 0:
                return None
            
            bid_ratio = bid_volume / total
            ask_ratio = ask_volume / total
            
            if bid_ratio > threshold:
                return {
                    'type': 'orderbook_imbalance',
                    'severity': 'medium',
                    'symbol': symbol,
                    'direction': 'bullish',
                    'bid_ratio': round(bid_ratio, 3),
                    'ask_ratio': round(ask_ratio, 3),
                    'message': f'📊 {symbol} дисбаланс: {bid_ratio:.1%} BID (бычий)',
                    'timestamp': datetime.now().isoformat()
                }
            elif ask_ratio > threshold:
                return {
                    'type': 'orderbook_imbalance',
                    'severity': 'medium',
                    'symbol': symbol,
                    'direction': 'bearish',
                    'bid_ratio': round(bid_ratio, 3),
                    'ask_ratio': round(ask_ratio, 3),
                    'message': f'📊 {symbol} дисбаланс: {ask_ratio:.1%} ASK (медвежий)',
                    'timestamp': datetime.now().isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка проверки дисбаланса: {e}")
            return None
    
    async def check_news_tone_shift(
        self,
        symbol: str,
        current_sentiment: float,
        avg_sentiment_24h: float,
        threshold: float = 0.3
    ) -> Optional[Dict]:
        """Алерт резкого изменения тона новостей"""
        try:
            shift = abs(current_sentiment - avg_sentiment_24h)
            
            if shift > threshold:
                direction = 'positive' if current_sentiment > avg_sentiment_24h else 'negative'
                severity = 'critical' if shift > 0.5 else 'high'
                
                return {
                    'type': 'news_tone_shift',
                    'severity': severity,
                    'symbol': symbol,
                    'direction': direction,
                    'shift': round(shift, 3),
                    'message': f'📰 {symbol} изменение тона новостей: {direction.upper()}',
                    'timestamp': datetime.now().isoformat()
                }
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка проверки тона новостей: {e}")
            return None
    
    async def check_all_alerts(
        self,
        symbol: str,
        market_data: Dict
    ) -> List[Dict]:
        """Проверить все типы алертов"""
        alerts = []
        
        try:
            # Проверка объёма
            if 'volume_24h' in market_data and 'avg_volume' in market_data:
                volume_alert = await self.check_volume_spike(
                    symbol,
                    market_data['volume_24h'],
                    market_data['avg_volume']
                )
                if volume_alert:
                    alerts.append(volume_alert)
            
            # Проверка ликвидаций
            if 'liquidations_24h' in market_data:
                liq_alert = await self.check_liquidation_alert(
                    symbol,
                    market_data['liquidations_24h']
                )
                if liq_alert:
                    alerts.append(liq_alert)
            
            # Проверка дисбаланса
            if 'bid_volume' in market_data and 'ask_volume' in market_data:
                imbalance_alert = await self.check_orderbook_imbalance(
                    symbol,
                    market_data['bid_volume'],
                    market_data['ask_volume']
                )
                if imbalance_alert:
                    alerts.append(imbalance_alert)
            
            # Проверка тона новостей
            if 'current_sentiment' in market_data and 'avg_sentiment_24h' in market_data:
                news_alert = await self.check_news_tone_shift(
                    symbol,
                    market_data['current_sentiment'],
                    market_data['avg_sentiment_24h']
                )
                if news_alert:
                    alerts.append(news_alert)
            
            return alerts
            
        except Exception as e:
            logger.error(f"❌ Ошибка проверки алертов: {e}")
            return []


# Экспорт
__all__ = ['AlertSystem']