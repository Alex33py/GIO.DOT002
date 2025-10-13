#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Enhanced Sentiment Analyzer v2.0 - с VADER и биграммами
Объединённый продвинутый анализ новостей с фильтрацией по символу,
взвешиванием ключевых слов, VADER sentiment и биграммами
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import re
from config.settings import logger

# Попытка импорта VADER
try:
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    VADER_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ VADER не установлен. Установите: pip install vaderSentiment")
    VADER_AVAILABLE = False


# ========== БИГРАММЫ (ФРАЗЫ ИЗ 2 СЛОВ) ==========
BIGRAM_WEIGHTS = {
    # Сильный позитив (+8.0 и выше)
    "etf approval": 10.0,
    "etf approved": 10.0,
    "sec approval": 9.0,
    "sec approved": 9.0,
    "institutional adoption": 8.5,
    "major partnership": 8.0,
    "regulatory clarity": 7.0,
    "mainnet launch": 7.5,
    "bitcoin etf": 9.0,
    "ethereum etf": 8.5,
    # Средний позитив (+4.0 - +7.0)
    "integration complete": 5.5,
    "exchange listing": 5.0,
    "price surge": 5.5,
    "bullish momentum": 6.0,
    "development update": 4.0,
    "network upgrade": 5.0,
    # Сильный негатив (-8.0 и ниже)
    "etf rejection": -10.0,
    "etf rejected": -10.0,
    "sec lawsuit": -9.0,
    "major hack": -10.0,
    "security breach": -9.5,
    "exchange collapse": -10.0,
    "fraud investigation": -8.5,
    "regulatory crackdown": -8.0,
    "market crash": -8.5,
    # Средний негатив (-4.0 - -7.0)
    "project delay": -5.0,
    "price crash": -7.0,
    "vulnerability discovered": -6.0,
    "network outage": -5.5,
    "regulatory warning": -6.0,
}


# ========== УНИГРАММЫ (ОТДЕЛЬНЫЕ СЛОВА) ==========
KEYWORD_WEIGHTS = {
    # Позитивные (усиливают bullish)
    "etf": 5.0,
    "approved": 3.0,
    "approval": 3.0,
    "adoption": 2.5,
    "partnership": 2.0,
    "upgrade": 2.0,
    "bullish": 2.5,
    "positive": 1.5,
    "growth": 1.8,
    "rally": 2.5,
    "surge": 2.5,
    "institutional": 2.0,
    "breakthrough": 2.0,
    "pump": 1.5,
    "moon": 1.0,
    "integration": 1.8,
    "listing": 1.5,
    # Негативные (усиливают bearish)
    "sec": -2.5,  # ← ВНИМАНИЕ: может быть и позитивным в контексте "SEC approval"!
    "regulation": -1.5,
    "ban": -4.0,
    "lawsuit": -3.5,
    "hack": -5.0,
    "scam": -4.0,
    "crash": -3.5,
    "bearish": -2.5,
    "negative": -1.5,
    "decline": -2.0,
    "dump": -2.5,
    "ftx": -3.0,
    "bankruptcy": -4.0,
    "fraud": -4.5,
    "breach": -4.5,
    "collapse": -5.0,
    # Нейтральные но важные (влияют на вес новостей)
    "binance": 1.5,
    "coinbase": 1.2,
    "microstrategy": 1.8,
    "blackrock": 2.5,
    "grayscale": 1.5,
    "bitcoin": 0.8,
    "ethereum": 0.8,
}


# Символы и их ключевые слова
SYMBOL_KEYWORDS = {
    "BTC": ["bitcoin", "btc", "btcusd", "btcusdt", "xbt"],
    "ETH": ["ethereum", "eth", "ether", "ethusdt", "vitalik"],
    "BNB": ["binance", "bnb"],
    "SOL": ["solana", "sol"],
    "XRP": ["ripple", "xrp"],
    "ADA": ["cardano", "ada"],
    "DOGE": ["dogecoin", "doge"],
    "ALT": ["altcoin", "alt", "crypto", "cryptocurrency", "defi", "nft"],
}


class UnifiedSentimentAnalyzer:
    """
    Объединённый Enhanced Sentiment Analyzer v2.0:
    - VADER для базового sentiment
    - Биграммы (фразы из 2 слов) с приоритетом
    - Униграммы (отдельные слова)
    - Фильтрация новостей по символу (BTC, ETH, ALT)
    - Агрегация sentiment за период
    - Генерация новостных алертов
    - Кэширование и history tracking
    """

    def __init__(self):
        """Инициализация"""

        # VADER для базового sentiment (если доступен)
        if VADER_AVAILABLE:
            self.vader = SentimentIntensityAnalyzer()
            logger.info("✅ VADER SentimentAnalyzer инициализирован")
        else:
            self.vader = None
            logger.warning("⚠️ VADER недоступен, используем только keyword weights")

        # Веса ключевых слов
        self.bigram_weights = BIGRAM_WEIGHTS
        self.keyword_weights = KEYWORD_WEIGHTS

        # Категории символов
        self.symbol_categories = SYMBOL_KEYWORDS

        # Кэш новостей по символам
        self.news_cache = {"BTC": [], "ETH": [], "ALT": []}

        # История sentiment (для трекинга трендов)
        self.sentiment_history = defaultdict(list)

        logger.info("✅ UnifiedSentimentAnalyzer v2.0 инициализирован")
        logger.info(f"   📊 Биграммы: {len(self.bigram_weights)}")
        logger.info(f"   📊 Униграммы: {len(self.keyword_weights)}")

    # ========== VADER + KEYWORD WEIGHTS ==========

    def get_base_sentiment_vader(self, text: str) -> float:
        """
        Получение базового sentiment через VADER

        Args:
            text: Текст новости

        Returns:
            Sentiment от -1.0 до +1.0
        """
        if not self.vader or not text:
            return 0.0

        try:
            scores = self.vader.polarity_scores(text)
            # Используем compound score (от -1 до +1)
            return scores["compound"]
        except Exception as e:
            logger.debug(f"⚠️ VADER ошибка: {e}")
            return 0.0

    def calculate_keyword_weights_v2(self, text: str) -> Dict:
        """
        Расчёт весов ключевых слов (биграммы + униграммы)
        Биграммы имеют ПРИОРИТЕТ над униграммами!

        Args:
            text: Текст новости (заголовок + body)

        Returns:
            Dict с информацией о найденных ключевых словах
        """
        text_lower = text.lower()

        total_weight = 0.0
        matched_bigrams = []
        matched_unigrams = []

        # 1. Проверяем БИГРАММЫ (приоритет!)
        for bigram, weight in self.bigram_weights.items():
            if bigram in text_lower:
                total_weight += weight
                matched_bigrams.append({"phrase": bigram, "weight": weight})

        # 2. Проверяем УНИГРАММЫ (только если биграмм не нашли для этого слова)
        for unigram, weight in self.keyword_weights.items():
            # Пропускаем, если это слово уже есть в найденных биграммах
            if any(unigram in bigram["phrase"] for bigram in matched_bigrams):
                continue

            # Ищем целое слово (не часть другого слова)
            pattern = r"\b" + re.escape(unigram) + r"\b"
            if re.search(pattern, text_lower):
                total_weight += weight
                matched_unigrams.append({"word": unigram, "weight": weight})

        return {
            "total_weight": total_weight,
            "matched_bigrams": matched_bigrams,
            "matched_unigrams": matched_unigrams,
            "total_matches": len(matched_bigrams) + len(matched_unigrams),
        }

    def calculate_enhanced_sentiment(self, news_item: Dict) -> float:
        """
        Расчёт улучшенного sentiment с VADER + биграммы + униграммы

        Args:
            news_item: Новость (модифицируется in-place)

        Returns:
            Enhanced sentiment score (-1.0 до 1.0)
        """
        try:
            title = news_item.get("title", "").lower()
            body = news_item.get("body", "").lower()
            text = f"{title} {body}"

            # 1. Базовый sentiment через VADER (если доступен)
            vader_sentiment = self.get_base_sentiment_vader(text) if self.vader else 0.0

            # 2. Веса ключевых слов (биграммы + униграммы)
            keyword_analysis = self.calculate_keyword_weights_v2(text)
            keyword_weight = keyword_analysis["total_weight"]

            # Нормализуем keyword_weight к диапазону [-1, 1]
            # Предполагаем, что макс. вес ~20-30
            normalized_keyword_weight = max(-1.0, min(1.0, keyword_weight / 15.0))

            # 3. Комбинируем: 40% VADER + 60% keywords
            if self.vader:
                enhanced_sentiment = (vader_sentiment * 0.4) + (
                    normalized_keyword_weight * 0.6
                )
            else:
                # Если VADER нет, используем только keywords
                enhanced_sentiment = normalized_keyword_weight

            # Ограничиваем диапазон
            enhanced_sentiment = max(-1.0, min(1.0, enhanced_sentiment))

            # Добавляем информацию в новость (in-place)
            news_item["enhanced_sentiment"] = enhanced_sentiment
            news_item["vader_sentiment"] = vader_sentiment
            news_item["keyword_weight"] = keyword_weight
            news_item["matched_bigrams"] = keyword_analysis["matched_bigrams"]
            news_item["matched_unigrams"] = keyword_analysis["matched_unigrams"]
            news_item["matched_keywords"] = [
                b["phrase"] for b in keyword_analysis["matched_bigrams"]
            ] + [u["word"] for u in keyword_analysis["matched_unigrams"]]

            if (
                keyword_analysis["matched_bigrams"]
                or keyword_analysis["matched_unigrams"]
            ):
                logger.debug(
                    f"📊 Новость: {title[:50]}... | "
                    f"VADER: {vader_sentiment:.2f} | "
                    f"Keywords: {keyword_weight:.1f} | "
                    f"Final: {enhanced_sentiment:.2f} | "
                    f"Bigrams: {len(keyword_analysis['matched_bigrams'])} | "
                    f"Unigrams: {len(keyword_analysis['matched_unigrams'])}"
                )

            return enhanced_sentiment

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта sentiment: {e}")
            return 0.0

    # ========== ОСТАЛЬНЫЕ МЕТОДЫ (БЕЗ ИЗМЕНЕНИЙ) ==========

    def analyze_news(self, news_list: List[Dict], symbol: str = None) -> Dict:
        """
        Анализ новостей с фильтрацией по символу

        Args:
            news_list: Список новостей
            symbol: Символ для фильтрации (BTC, ETH, ALT) или None для всех

        Returns:
            Dict с sentiment анализом
        """
        try:
            # Фильтруем новости по символу
            filtered_news = self.filter_news_by_symbol(news_list, symbol)

            if not filtered_news:
                return {
                    "sentiment": "neutral",
                    "score": 0.0,
                    "news_count": 0,
                    "positive_count": 0,
                    "negative_count": 0,
                    "neutral_count": 0,
                    "weighted_score": 0.0,
                    "top_keywords": [],
                }

            # Рассчитываем enhanced sentiment для каждой новости
            for news in filtered_news:
                self.calculate_enhanced_sentiment(news)

            # Рассчитываем агрегированный sentiment
            sentiment_data = self._calculate_weighted_sentiment(filtered_news)

            # Добавляем топ ключевых слов
            sentiment_data["top_keywords"] = self._extract_top_keywords(filtered_news)

            logger.info(
                f"📰 Sentiment {symbol or 'ALL'}: {sentiment_data['sentiment']} "
                f"(score: {sentiment_data['weighted_score']:.2f}, новостей: {len(filtered_news)})"
            )

            return sentiment_data

        except Exception as e:
            logger.error(f"❌ Ошибка analyze_news: {e}")
            return {
                "sentiment": "neutral",
                "score": 0.0,
                "news_count": 0,
                "weighted_score": 0.0,
            }

    def filter_news_by_symbol(self, news_list: List[Dict], symbol: str) -> List[Dict]:
        """
        Фильтрация новостей по символу

        Args:
            news_list: Список новостей
            symbol: Символ (BTC, ETH, ALT) или None

        Returns:
            Отфильтрованный список новостей
        """
        try:
            if not symbol:
                return news_list  # Возвращаем все новости

            # Получаем ключевые слова для символа
            keywords = self.symbol_categories.get(symbol.upper(), [])

            if not keywords and symbol.upper() != "ALT":
                logger.warning(f"⚠️ Нет ключевых слов для символа {symbol}")
                return news_list

            filtered = []

            for news in news_list:
                title = news.get("title", "").lower()
                body = news.get("body", "").lower()
                text = f"{title} {body}"

                # Специальная логика для ALT
                if symbol.upper() == "ALT":
                    # Для ALT берём все, что не относится к BTC/ETH
                    is_btc = any(kw in text for kw in self.symbol_categories["BTC"])
                    is_eth = any(kw in text for kw in self.symbol_categories["ETH"])

                    if not is_btc and not is_eth:
                        news["matched_symbol"] = symbol
                        filtered.append(news)
                else:
                    # Для конкретных символов проверяем наличие ключевых слов
                    if any(keyword in text for keyword in keywords):
                        news["matched_symbol"] = symbol
                        filtered.append(news)

            logger.debug(
                f"📰 Отфильтровано {len(filtered)}/{len(news_list)} новостей для {symbol}"
            )
            return filtered

        except Exception as e:
            logger.error(f"❌ Ошибка фильтрации новостей: {e}")
            return news_list

    def _calculate_weighted_sentiment(self, news_list: List[Dict]) -> Dict:
        """
        Расчёт агрегированного sentiment с учётом весов

        Returns:
            Dict с детальным sentiment анализом
        """
        positive_count = 0
        negative_count = 0
        neutral_count = 0

        total_score = 0.0
        weighted_score = 0.0

        for news in news_list:
            # Используем enhanced_sentiment если есть
            sentiment_value = news.get("enhanced_sentiment", 0.0)

            # Классифицируем
            if sentiment_value > 0.2:
                positive_count += 1
                total_score += 1
            elif sentiment_value < -0.2:
                negative_count += 1
                total_score -= 1
            else:
                neutral_count += 1

            weighted_score += sentiment_value

        # Определяем общий sentiment
        if weighted_score > 0.3:
            sentiment = "bullish"
        elif weighted_score < -0.3:
            sentiment = "bearish"
        else:
            sentiment = "neutral"

        # Нормализуем weighted_score к диапазону [-10, 10]
        normalized_score = weighted_score * 10  # Уже в диапазоне [-1, 1]
        normalized_score = max(-10, min(10, normalized_score))

        return {
            "sentiment": sentiment,
            "score": round(total_score, 2),
            "weighted_score": round(normalized_score, 2),
            "news_count": len(news_list),
            "positive_count": positive_count,
            "negative_count": negative_count,
            "neutral_count": neutral_count,
        }

    def _extract_top_keywords(self, news_list: List[Dict], top_n: int = 5) -> List[str]:
        """Извлечение топ-N ключевых слов из новостей"""
        keyword_counts = {}

        for news in news_list:
            matched = news.get("matched_keywords", [])
            for keyword in matched:
                keyword_counts[keyword] = keyword_counts.get(keyword, 0) + 1

        # Сортируем по частоте
        sorted_keywords = sorted(
            keyword_counts.items(), key=lambda x: x[1], reverse=True
        )

        return [kw for kw, count in sorted_keywords[:top_n]]

    # ========== ДОПОЛНИТЕЛЬНЫЕ МЕТОДЫ (БЕЗ ИЗМЕНЕНИЙ) ==========

    def get_symbol_sentiment(self, symbol: str, news_list: List[Dict] = None) -> Dict:
        """Получение sentiment для конкретного символа"""
        try:
            category = (
                "BTC"
                if "BTC" in symbol.upper()
                else "ETH" if "ETH" in symbol.upper() else "ALT"
            )

            if news_list:
                return self.analyze_news(news_list, category)
            else:
                cached_news = self.news_cache.get(category, [])
                return self.analyze_news(cached_news, category)

        except Exception as e:
            logger.error(f"❌ Ошибка get_symbol_sentiment: {e}")
            return {
                "sentiment": "neutral",
                "score": 0.0,
                "weighted_score": 0.0,
                "news_count": 0,
            }

    def get_aggregated_sentiment(self, symbol: str, hours: int = 24) -> Dict:
        """Получение агрегированного sentiment за период"""
        try:
            cutoff_time = datetime.now().timestamp() - (hours * 3600)

            cached_news = self.news_cache.get(symbol.upper(), [])
            recent_news = [
                news
                for news in cached_news
                if news.get("published_on", 0) > cutoff_time
            ]

            if not recent_news:
                return {
                    "symbol": symbol,
                    "avg_sentiment": 0.0,
                    "sentiment_trend": "neutral",
                    "news_count": 0,
                    "positive_count": 0,
                    "negative_count": 0,
                    "neutral_count": 0,
                    "period_hours": hours,
                }

            result = self.analyze_news(recent_news, symbol)
            result["period_hours"] = hours
            result["symbol"] = symbol
            result["sentiment_trend"] = result.get("sentiment", "neutral")
            result["avg_sentiment"] = result.get("weighted_score", 0.0) / 10.0

            logger.info(
                f"📊 Sentiment для {symbol} ({hours}h): "
                f"{result['avg_sentiment']:.2f} ({result['sentiment_trend']}) | "
                f"Новостей: {result['news_count']} "
                f"(+{result['positive_count']}/-{result['negative_count']}/={result['neutral_count']})"
            )

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка агрегации sentiment: {e}")
            return {
                "symbol": symbol,
                "avg_sentiment": 0.0,
                "sentiment_trend": "neutral",
            }

    def update_news_cache(self, news_list: List[Dict]):
        """Обновление кэша новостей с разделением по категориям"""
        try:
            self.news_cache = {"BTC": [], "ETH": [], "ALT": []}

            for news in news_list:
                title = news.get("title", "").lower()
                body = news.get("body", "").lower()
                text = f"{title} {body}"

                if any(kw in text for kw in self.symbol_categories["BTC"]):
                    self.news_cache["BTC"].append(news)
                elif any(kw in text for kw in self.symbol_categories["ETH"]):
                    self.news_cache["ETH"].append(news)
                else:
                    self.news_cache["ALT"].append(news)

            logger.info(
                f"✅ Кэш обновлён: BTC={len(self.news_cache['BTC'])}, "
                f"ETH={len(self.news_cache['ETH'])}, ALT={len(self.news_cache['ALT'])}"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка update_news_cache: {e}")

    def process_news_batch(
        self, news_list: List[Dict], symbols: List[str] = None
    ) -> Dict:
        """Обработка батча новостей для всех символов"""
        try:
            if symbols is None:
                symbols = ["BTC", "ETH", "ALT"]

            results = {}

            for news in news_list:
                self.calculate_enhanced_sentiment(news)

            self.update_news_cache(news_list)

            for symbol in symbols:
                filtered_news = self.filter_news_by_symbol(news_list, symbol)
                sentiment = self.analyze_news(filtered_news, symbol)

                results[symbol] = {"news": filtered_news, "sentiment": sentiment}

            logger.info(
                f"✅ Обработано {len(news_list)} новостей для {len(symbols)} символов"
            )

            return results

        except Exception as e:
            logger.error(f"❌ Ошибка обработки батча новостей: {e}")
            return {}

    def get_news_alerts(self, symbol: str) -> List[Dict]:
        """Получение алертов на основе новостей"""
        try:
            alerts = []

            cached_news = self.news_cache.get(symbol.upper(), [])
            recent_news = [
                news
                for news in cached_news
                if (datetime.now().timestamp() - news.get("published_on", 0)) < 3600
            ]

            for news in recent_news:
                sentiment = news.get("enhanced_sentiment", 0.0)
                keywords = news.get("matched_keywords", [])

                if sentiment > 0.7:
                    alerts.append(
                        {
                            "type": "positive_news",
                            "symbol": symbol,
                            "severity": "high",
                            "message": f"🟢 Сильно позитивные новости: {news.get('title', '')[:80]}...",
                            "sentiment": sentiment,
                            "keywords": keywords,
                            "timestamp": news.get("published_on", 0),
                        }
                    )

                elif sentiment < -0.7:
                    alerts.append(
                        {
                            "type": "negative_news",
                            "symbol": symbol,
                            "severity": "high",
                            "message": f"🔴 Сильно негативные новости: {news.get('title', '')[:80]}...",
                            "sentiment": sentiment,
                            "keywords": keywords,
                            "timestamp": news.get("published_on", 0),
                        }
                    )

                important_keywords = [
                    "etf",
                    "sec",
                    "hack",
                    "ban",
                    "approved",
                    "approval",
                ]
                if any(kw in keywords for kw in important_keywords):
                    alerts.append(
                        {
                            "type": "important_keyword",
                            "symbol": symbol,
                            "severity": "medium",
                            "message": f"⚠️ Важные ключевые слова: {', '.join([k for k in keywords if k in important_keywords])}",
                            "sentiment": sentiment,
                            "keywords": keywords,
                            "timestamp": news.get("published_on", 0),
                        }
                    )

            if alerts:
                logger.info(f"🚨 Найдено {len(alerts)} новостных алертов для {symbol}")

            return alerts

        except Exception as e:
            logger.error(f"❌ Ошибка генерации новостных алертов: {e}")
            return []


# Алиасы для совместимости
EnhancedNewsAnalyzer = UnifiedSentimentAnalyzer
EnhancedSentimentAnalyzer = UnifiedSentimentAnalyzer
ProfessionalNewsAnalyzer = UnifiedSentimentAnalyzer

# Экспорт
__all__ = [
    "UnifiedSentimentAnalyzer",
    "EnhancedSentimentAnalyzer",
    "EnhancedNewsAnalyzer",
    "KEYWORD_WEIGHTS",
    "BIGRAM_WEIGHTS",
    "SYMBOL_KEYWORDS",
]
