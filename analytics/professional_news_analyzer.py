# -*- coding: utf-8 -*-
"""
Профессиональный анализатор новостей (базовая версия)
Используется как fallback для EnhancedNewsAnalyzer
"""

from typing import Dict, List, Optional
from datetime import datetime
from config.settings import logger


class ProfessionalNewsAnalyzer:
    """Профессиональный анализатор новостей"""

    def __init__(self):
        self.news_cache = []
        self.sentiment_weights = {
            'positive': 1.0,
            'negative': -1.0,
            'neutral': 0.0
        }

        # ========== ДОБАВЛЕНО: keyword_weights ==========
        self.keyword_weights = {
            # Позитивные ключевые слова с весами
            'bullish': 0.8,
            'breakout': 0.7,
            'rally': 0.7,
            'surge': 0.6,
            'moon': 0.5,
            'pump': 0.5,
            'gain': 0.4,
            'profit': 0.4,
            'buy': 0.3,
            'long': 0.3,

            # Негативные ключевые слова с весами
            'bearish': -0.8,
            'crash': -0.8,
            'dump': -0.7,
            'drop': -0.6,
            'fall': -0.6,
            'loss': -0.5,
            'sell': -0.4,
            'short': -0.3,
            'decline': -0.3,

            # Критические события (высокий вес)
            'hack': -1.0,
            'ban': -0.9,
            'regulation': -0.5,
            'SEC': -0.4,
            'lawsuit': -0.6,
            'approval': 0.7,
            'ETF': 0.6,
            'partnership': 0.5
        }

        logger.info("✅ ProfessionalNewsAnalyzer инициализирован")

    def analyze_news(self, news_list: List[Dict]) -> Dict:
        """
        Анализ списка новостей

        Args:
            news_list: Список новостей

        Returns:
            Результаты анализа
        """
        try:
            if not news_list:
                return {
                    'total_count': 0,
                    'avg_sentiment': 0.0,
                    'sentiment_trend': 'neutral',
                    'positive_count': 0,
                    'negative_count': 0,
                    'neutral_count': 0
                }

            # Подсчёт sentiment
            sentiments = []
            positive_count = 0
            negative_count = 0
            neutral_count = 0

            for news in news_list:
                sentiment = news.get('sentiment', 0.0)
                sentiments.append(sentiment)

                if sentiment > 0.2:
                    positive_count += 1
                elif sentiment < -0.2:
                    negative_count += 1
                else:
                    neutral_count += 1

            # Средний sentiment
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

            # Тренд
            if avg_sentiment > 0.3:
                trend = 'bullish'
            elif avg_sentiment < -0.3:
                trend = 'bearish'
            else:
                trend = 'neutral'

            # Сохраняем в кэш
            self.news_cache = news_list

            result = {
                'total_count': len(news_list),
                'avg_sentiment': avg_sentiment,
                'sentiment_trend': trend,
                'positive_count': positive_count,
                'negative_count': negative_count,
                'neutral_count': neutral_count,
                'timestamp': datetime.now().timestamp()
            }

            logger.debug(
                f"📰 Анализ новостей: {len(news_list)} шт, "
                f"sentiment={avg_sentiment:.2f} ({trend})"
            )

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка анализа новостей: {e}")
            return {
                'total_count': 0,
                'avg_sentiment': 0.0,
                'sentiment_trend': 'neutral'
            }

    def get_sentiment_for_symbol(self, symbol: str) -> float:
        """
        Получить sentiment для конкретного символа

        Args:
            symbol: Символ (BTC, ETH, etc)

        Returns:
            Sentiment score (-1.0 до 1.0)
        """
        try:
            # Простая фильтрация по заголовку
            symbol_keywords = {
                'BTC': ['bitcoin', 'btc'],
                'ETH': ['ethereum', 'eth'],
                'BNB': ['binance', 'bnb']
            }

            keywords = symbol_keywords.get(symbol, [symbol.lower()])

            relevant_news = [
                news for news in self.news_cache
                if any(kw in news.get('title', '').lower() for kw in keywords)
            ]

            if not relevant_news:
                return 0.0

            sentiments = [news.get('sentiment', 0.0) for news in relevant_news]
            avg_sentiment = sum(sentiments) / len(sentiments)

            return avg_sentiment

        except Exception as e:
            logger.error(f"❌ Ошибка получения sentiment для {symbol}: {e}")
            return 0.0

    def get_recent_news(self, hours: int = 24) -> List[Dict]:
        """
        Получить последние новости за период

        Args:
            hours: Количество часов

        Returns:
            Список новостей
        """
        try:
            cutoff_time = datetime.now().timestamp() - (hours * 3600)

            recent = [
                news for news in self.news_cache
                if news.get('published_on', 0) > cutoff_time
            ]

            return recent

        except Exception as e:
            logger.error(f"❌ Ошибка получения последних новостей: {e}")
            return []

    def analyze_weighted_sentiment(self, text: str) -> Dict:
        """
        Анализ sentiment с учётом весов ключевых слов

        Args:
            text: Текст для анализа

        Returns:
            Результат анализа с весами
        """
        try:
            text_lower = text.lower()

            total_weight = 0.0
            matched_keywords = []

            # Ищем ключевые слова с весами
            for keyword, weight in self.keyword_weights.items():
                if keyword.lower() in text_lower:
                    total_weight += weight
                    matched_keywords.append({
                        'keyword': keyword,
                        'weight': weight
                    })

            # Базовый sentiment (простой подсчёт)
            positive_words = ['good', 'great', 'bullish', 'up', 'growth', 'gain', 'profit', 'win']
            negative_words = ['bad', 'bearish', 'down', 'loss', 'drop', 'fall', 'decline', 'crash']

            pos_count = sum(1 for word in positive_words if word in text_lower)
            neg_count = sum(1 for word in negative_words if word in text_lower)

            if pos_count + neg_count > 0:
                base_score = (pos_count - neg_count) / (pos_count + neg_count)
            else:
                base_score = 0.0

            # Применяем веса
            weight_adjustment = total_weight * 0.1  # Масштабируем
            final_score = base_score + weight_adjustment

            # Ограничиваем [-1, 1]
            final_score = max(-1.0, min(1.0, final_score))

            # Определяем метку
            if final_score > 0.3:
                sentiment = 'positive'
            elif final_score < -0.3:
                sentiment = 'negative'
            else:
                sentiment = 'neutral'

            return {
                'base_score': round(base_score, 3),
                'weight_adjustment': round(weight_adjustment, 3),
                'final_score': round(final_score, 3),
                'sentiment': sentiment,
                'matched_keywords': matched_keywords,
                'keyword_count': len(matched_keywords)
            }

        except Exception as e:
            logger.error(f"❌ Ошибка умного sentiment анализа: {e}")
            return {
                'base_score': 0.0,
                'weight_adjustment': 0.0,
                'final_score': 0.0,
                'sentiment': 'neutral',
                'matched_keywords': [],
                'keyword_count': 0
            }

    def get_impact_score(self, news_item: Dict) -> float:
        """
        Оценка важности новости

        Args:
            news_item: Новость

        Returns:
            Impact score (0.0 - 1.0)
        """
        try:
            # Базовая оценка
            sentiment = abs(news_item.get('sentiment', 0.0))

            # Проверяем важные ключевые слова
            title = news_item.get('title', '').lower()
            important_keywords = ['sec', 'etf', 'hack', 'ban', 'regulation', 'approval']

            keyword_bonus = 0.3 if any(kw in title for kw in important_keywords) else 0.0

            impact = min(1.0, sentiment + keyword_bonus)

            return impact

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта impact score: {e}")
            return 0.0


# Экспорт
__all__ = ['ProfessionalNewsAnalyzer']
