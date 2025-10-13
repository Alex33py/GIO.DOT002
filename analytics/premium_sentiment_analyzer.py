#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Premium Sentiment Analyzer с РАСШИРЕННЫМИ взвешенными ключевыми словами
ОБНОВЛЁННАЯ ВЕРСИЯ от 04.10.2025
"""

import re
from typing import Dict, List, Optional
from datetime import datetime
from config.settings import logger


class PremiumSentimentAnalyzer:
    """
    Премиум анализатор sentiment с весами для ключевых слов
    """

    def __init__(self):
        # ========================================
        # РАСШИРЕННЫЕ КЛЮЧЕВЫЕ СЛОВА С ВЕСАМИ
        # ========================================
        self.keyword_weights = {
            # ===== КРИТИЧЕСКИ ВАЖНЫЕ (вес: 3.0+) =====
            'ETF approval': 3.5,
            'ETF approved': 3.5,
            'SEC approval': 3.0,
            'institutional adoption': 3.0,
            'BlackRock': 2.8,
            'Fidelity': 2.5,

            # Регуляторные позитивные
            'legal clarity': 2.0,
            'compliant': 1.5,
            'regulatory approval': 2.5,

            # ===== ОЧЕНЬ ВАЖНЫЕ ПОЗИТИВНЫЕ (вес: 2.0-2.5) =====
            'adoption': 2.0,
            'partnership': 2.0,
            'integration': 1.8,
            'breakthrough': 2.2,
            'milestone': 2.0,
            'launch': 1.8,
            'upgrade': 1.8,
            'innovation': 2.0,

            # Биржи позитивные
            'Binance': 2.0,
            'Coinbase': 2.0,
            'listed': 1.5,

            # ===== ВАЖНЫЕ ПОЗИТИВНЫЕ (вес: 1.5) =====
            'bullish': 1.5,
            'moon': 1.8,
            'pump': 1.3,
            'rally': 1.6,
            'surge': 1.6,
            'breakout': 1.7,
            'gains': 1.4,
            'profit': 1.3,
            'green': 1.2,
            'rocket': 1.5,
            'explosive': 1.7,
            'momentum': 1.5,
            'strength': 1.4,
            'support': 1.3,

            # Технические позитивные
            'golden cross': 2.0,
            'oversold bounce': 1.6,
            'strong support': 1.5,
            'accumulation': 1.6,
            'whale buying': 2.0,
            'institutional buying': 2.2,
            'positive funding': 1.4,

            # Новости позитивные
            'success': 1.5,
            'expansion': 1.6,
            'growth': 1.5,
            'investment': 1.7,
            'funding secured': 2.0,
            'record high': 2.0,
            'all-time high': 2.2,
            'ATH': 2.2,

            # ===== КРИТИЧЕСКИ НЕГАТИВНЫЕ (вес: -3.0+) =====
            'ban': -3.0,
            'banned': -3.0,
            'hack': -3.5,
            'hacked': -3.5,
            'exploit': -3.0,
            'exploited': -3.0,
            'bankruptcy': -3.5,
            'bankrupt': -3.5,
            'insolvent': -3.0,
            'SEC lawsuit': -3.0,
            'SEC charges': -3.0,
            'SEC investigation': -2.5,
            'regulatory crackdown': -2.8,
            'fraud': -3.0,
            'scam': -3.0,
            'ponzi': -3.5,

            # FTX/биржевые коллапсы
            'FTX collapse': -3.0,
            'exchange collapse': -3.0,
            'trading halted': -2.5,
            'suspended trading': -2.5,
            'delisting': -2.0,
            'delisted': -2.0,

            # ===== ОЧЕНЬ ВАЖНЫЕ НЕГАТИВНЫЕ (вес: -2.0-2.5) =====
            'crash': -2.5,
            'collapse': -2.5,
            'plunge': -2.2,
            'dump': -2.0,
            'selloff': -2.0,
            'sell-off': -2.0,
            'capitulation': -2.5,

            # Регуляторные негативные
            'illegal': -2.5,
            'investigation': -2.0,
            'charges': -2.2,
            'lawsuit': -2.0,

            # ===== ВАЖНЫЕ НЕГАТИВНЫЕ (вес: -1.5) =====
            'bearish': -1.5,
            'decline': -1.4,
            'fall': -1.3,
            'drop': -1.4,
            'red': -1.2,
            'fear': -1.5,
            'panic': -1.8,
            'resistance': -1.2,

            # Технические негативные
            'death cross': -2.0,
            'overbought': -1.3,
            'weak support': -1.4,
            'distribution': -1.5,
            'breakdown': -1.6,
            'whale dumping': -2.0,
            'institutional selling': -2.2,
            'negative funding': -1.4,

            # Новости негативные
            'failure': -1.8,
            'delay': -1.3,
            'postponed': -1.3,
            'rejected': -1.8,
            'denied': -1.8,
            'controversy': -1.5,
            'criticism': -1.4,
            'concern': -1.2,
            'risk': -1.3,
            'warning': -1.5,
            'loss': -1.6,
            'loss of funds': -2.5,

            # ===== НЕЙТРАЛЬНЫЕ, НО ВАЖНЫЕ (вес: 1.0) =====
            'announcement': 1.0,
            'update': 1.0,
            'scheduled': 0.8,
            'pending': 0.5,
            'expected': 0.8,
            'unchanged': 0.0,
            'sideways': 0.0,
            'consolidation': 0.0,
            'range-bound': 0.0,
            'flat': 0.0,
        }

        # ========================================
        # МОДИФИКАТОРЫ ИНТЕНСИВНОСТИ
        # ========================================
        self.intensity_modifiers = {
            # Усилители (множитель > 1.0)
            'major': 1.8,
            'massive': 2.0,
            'huge': 1.7,
            'significant': 1.5,
            'historic': 1.9,
            'unprecedented': 2.0,
            'critical': 1.8,
            'severe': 1.7,
            'extreme': 1.8,

            # Ослабители (множитель < 1.0)
            'minor': 0.6,
            'slight': 0.5,
            'small': 0.6,
            'moderate': 0.8,
            'limited': 0.7,
            'partial': 0.7,

            # Нейтральные
            'potential': 0.9,
            'possible': 0.8,
            'alleged': 0.7,
            'rumored': 0.6,
        }

        logger.info("✅ PremiumSentimentAnalyzer инициализирован (РАСШИРЕННАЯ ВЕРСИЯ)")

    def analyze_news(self, news_list: List[Dict]) -> Dict:
        """
        Анализ списка новостей с взвешенным sentiment

        Args:
            news_list: список новостей с полями title, body, published_on

        Returns:
            Dict с sentiment score, категоризацией и детальным анализом
        """
        try:
            if not news_list:
                return self._empty_result()

            # Фильтрация по времени (последние 24 часа)
            recent_news = self._filter_recent_news(news_list, hours=24)

            if not recent_news:
                logger.debug("⚠️ Нет новостей за последние 24 часа")
                return self._empty_result()

            # Анализ каждой новости
            analyzed_news = []
            total_weighted_score = 0.0
            category_scores = {'BTC': 0.0, 'ETH': 0.0, 'ALT': 0.0}

            for news in recent_news:
                analysis = self._analyze_single_news(news)
                analyzed_news.append(analysis)
                total_weighted_score += analysis['weighted_score']

                # Категоризация по символу
                category = self._categorize_news(news)
                category_scores[category] += analysis['weighted_score']

            # Нормализация score (-100 до +100)
            normalized_score = self._normalize_score(
                total_weighted_score,
                len(recent_news)
            )

            # Определение общего sentiment
            sentiment = self._determine_sentiment(normalized_score)

            # Ключевые события
            key_events = self._extract_key_events(analyzed_news)

            result = {
                'overall_score': normalized_score,
                'sentiment': sentiment,
                'total_news': len(recent_news),
                'category_scores': category_scores,
                'key_events': key_events,
                'analyzed_news': analyzed_news[:10],  # топ-10 важных
                'timestamp': datetime.now().isoformat()
            }

            logger.info(
                f"📰 Sentiment анализ: {sentiment} "
                f"(score: {normalized_score:.1f}, новостей: {len(recent_news)})"
            )

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка анализа sentiment: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return self._empty_result()

    def _analyze_single_news(self, news: Dict) -> Dict:
        """Анализ одной новости с взвешенными ключевыми словами"""
        text = f"{news.get('title', '')} {news.get('body', '')}".lower()

        keyword_hits = []
        base_score = 0.0

        # Поиск ключевых слов
        for keyword, weight in self.keyword_weights.items():
            if keyword.lower() in text:
                # Проверка модификаторов интенсивности
                modifier = self._check_intensity_modifiers(text, keyword)
                final_weight = weight * modifier

                keyword_hits.append({
                    'keyword': keyword,
                    'weight': weight,
                    'modifier': modifier,
                    'final_weight': final_weight
                })

                base_score += final_weight

        return {
            'title': news.get('title', ''),
            'published': news.get('published_on', 0),
            'source': news.get('source', 'unknown'),
            'base_score': base_score,
            'weighted_score': base_score,
            'keyword_hits': keyword_hits,
            'url': news.get('url', '')
        }

    def _check_intensity_modifiers(self, text: str, keyword: str) -> float:
        """Проверка модификаторов интенсивности рядом с ключевым словом"""
        # Ищем модификаторы в окне ±10 слов от ключевого слова
        keyword_pos = text.find(keyword.lower())
        if keyword_pos == -1:
            return 1.0

        window_start = max(0, keyword_pos - 50)
        window_end = min(len(text), keyword_pos + 50)
        context = text[window_start:window_end]

        # Проверяем все модификаторы
        max_modifier = 1.0
        for modifier, multiplier in self.intensity_modifiers.items():
            if modifier in context:
                # Берём максимальный модификатор
                if abs(multiplier - 1.0) > abs(max_modifier - 1.0):
                    max_modifier = multiplier

        return max_modifier

    def _categorize_news(self, news: Dict) -> str:
        """Категоризация новости по символу"""
        text = f"{news.get('title', '')} {news.get('body', '')}".lower()

        # Проверка на упоминания конкретных монет
        btc_keywords = ['bitcoin', 'btc', 'btcusd', 'btcusdt']
        eth_keywords = ['ethereum', 'eth', 'ethusd', 'ethusdt', 'vitalik']

        btc_score = sum(1 for kw in btc_keywords if kw in text)
        eth_score = sum(1 for kw in eth_keywords if kw in text)

        if btc_score > eth_score:
            return 'BTC'
        elif eth_score > 0:
            return 'ETH'
        else:
            return 'ALT'

    def _filter_recent_news(self, news_list: List[Dict], hours: int = 24) -> List[Dict]:
        """Фильтрация новостей за последние N часов"""
        current_time = datetime.now().timestamp()
        cutoff_time = current_time - (hours * 3600)

        filtered = [
            news for news in news_list
            if news.get('published_on', 0) >= cutoff_time
        ]

        logger.debug(f"🔍 Отфильтровано {len(filtered)} новостей за последние {hours}ч из {len(news_list)}")
        return filtered

    def _normalize_score(self, total_score: float, news_count: int) -> float:
        """Нормализация score в диапазон -100 до +100"""
        if news_count == 0:
            return 0.0

        avg_score = total_score / news_count

        # УЛУЧШЕННОЕ масштабирование:
        # Средний score обычно в диапазоне [-10, 10]
        # Масштабируем с учётом количества новостей
        scale_factor = min(20, 15 + (news_count / 10))
        normalized = max(-100, min(100, avg_score * scale_factor))

        return round(normalized, 2)

    def _determine_sentiment(self, score: float) -> str:
        """Определение категории sentiment по score"""
        if score >= 60:
            return 'very_bullish'
        elif score >= 25:
            return 'bullish'
        elif score >= -25:
            return 'neutral'
        elif score >= -60:
            return 'bearish'
        else:
            return 'very_bearish'

    def _extract_key_events(self, analyzed_news: List[Dict]) -> List[Dict]:
        """Извлечение ключевых событий (топ-5 по весу)"""
        sorted_news = sorted(
            analyzed_news,
            key=lambda x: abs(x['weighted_score']),
            reverse=True
        )

        return [
            {
                'title': news['title'],
                'score': round(news['weighted_score'], 2),
                'keywords': [hit['keyword'] for hit in news['keyword_hits'][:3]],
                'url': news['url']
            }
            for news in sorted_news[:5]
        ]

    def _empty_result(self) -> Dict:
        """Пустой результат при отсутствии данных"""
        return {
            'overall_score': 0.0,
            'sentiment': 'neutral',
            'total_news': 0,
            'category_scores': {'BTC': 0.0, 'ETH': 0.0, 'ALT': 0.0},
            'key_events': [],
            'analyzed_news': [],
            'timestamp': datetime.now().isoformat()
        }
