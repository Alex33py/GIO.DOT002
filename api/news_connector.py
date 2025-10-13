# -*- coding: utf-8 -*-
"""
Улучшенный коннектор новостей с фильтрацией по символам и весами ключевых слов
"""

import aiohttp
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from config.settings import logger, NEWS_CONFIG

class UnifiedNewsConnector:
    """Унифицированный коннектор для новостей с умным sentiment анализом"""

    # Веса ключевых слов для sentiment
    KEYWORD_WEIGHTS = {
        # Позитивные
        'ETF': 2.0,
        'adoption': 1.5,
        'bullish': 1.3,
        'partnership': 1.4,
        'integration': 1.2,
        'upgrade': 1.3,
        'approval': 1.8,

        # Негативные
        'SEC': -1.5,
        'lawsuit': -1.8,
        'hack': -2.0,
        'scam': -2.0,
        'bearish': -1.3,
        'regulation': -1.0,
        'ban': -1.7,
        'crash': -1.5
    }

    # Символы для фильтрации
    SYMBOL_KEYWORDS = {
        'BTC': ['bitcoin', 'btc', 'satoshi'],
        'ETH': ['ethereum', 'eth', 'vitalik', 'ether'],
        'BNB': ['binance', 'bnb', 'bsc'],
        'SOL': ['solana', 'sol'],
        'XRP': ['ripple', 'xrp'],
        'ADA': ['cardano', 'ada'],
        'DOGE': ['dogecoin', 'doge', 'shib'],
        'ALT': []  # Для остальных альткоинов
    }

    def __init__(self):
        self.session = None
        self.news_cache = {}  # Кэш по символам: {'BTC': [], 'ETH': [], 'ALT': []}
        self.cache_expiry = {}
        logger.info("✅ UnifiedNewsConnector инициализирован с фильтрацией по символам")

    async def ensure_session(self):
        """Создание HTTP сессии"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def get_news_by_symbol(self, symbol: str = 'BTC', hours: int = 24) -> List[Dict]:
        """
        Получение новостей для конкретного символа
        """
        await self.ensure_session()

        # Проверяем кэш
        if symbol in self.news_cache:
            if symbol in self.cache_expiry and datetime.now() < self.cache_expiry[symbol]:
                logger.debug(f"📰 Возврат новостей из кэша для {symbol}")
                return self.news_cache[symbol]

        # Собираем новости со всех источников
        all_news = []

        # CryptoCompare
        try:
            cc_news = await self._get_cryptocompare_news(symbol, hours)
            all_news.extend(cc_news)
        except Exception as e:
            logger.error(f"❌ Ошибка CryptoCompare для {symbol}: {e}")

        # CryptoPanic
        try:
            cp_news = await self._get_cryptopanic_news(symbol, hours)
            all_news.extend(cp_news)
        except Exception as e:
            logger.error(f"❌ Ошибка CryptoPanic для {symbol}: {e}")

        # Фильтруем по символу и добавляем взвешенный sentiment
        filtered_news = self._filter_and_score_news(all_news, symbol)

        # Кэшируем на 10 минут
        self.news_cache[symbol] = filtered_news
        self.cache_expiry[symbol] = datetime.now() + timedelta(minutes=10)

        logger.info(f"📰 Загружено {len(filtered_news)} новостей для {symbol}")
        return filtered_news

    def _filter_and_score_news(self, news_list: List[Dict], symbol: str) -> List[Dict]:
        """
        Фильтрация новостей по символу и добавление взвешенного sentiment
        """
        filtered = []
        symbol_keywords = self.SYMBOL_KEYWORDS.get(symbol, [])

        for news in news_list:
            title = news.get('title', '').lower()
            body = news.get('body', '').lower()
            full_text = title + ' ' + body

            # Проверяем наличие ключевых слов символа
            if symbol != 'ALT':
                is_relevant = any(keyword.lower() in full_text for keyword in symbol_keywords)
                if not is_relevant:
                    continue

            # Вычисляем взвешенный sentiment
            weighted_sentiment = self._calculate_weighted_sentiment(full_text)
            news['weighted_sentiment'] = weighted_sentiment
            news['symbol'] = symbol

            filtered.append(news)

        # Сортируем по времени (новые первыми)
        filtered.sort(key=lambda x: x.get('published_on', 0), reverse=True)

        return filtered

    def _calculate_weighted_sentiment(self, text: str) -> float:
        """
        Расчёт взвешенного sentiment на основе ключевых слов
        """
        sentiment_score = 0.0
        text_lower = text.lower()

        for keyword, weight in self.KEYWORD_WEIGHTS.items():
            if keyword.lower() in text_lower:
                sentiment_score += weight
                logger.debug(f"🔍 Найдено ключевое слово '{keyword}' с весом {weight}")

        # Нормализуем в диапазон [-1, 1]
        normalized = max(min(sentiment_score / 5.0, 1.0), -1.0)

        return normalized

    async def _get_cryptocompare_news(self, symbol: str, hours: int) -> List[Dict]:
        """Получение новостей из CryptoCompare"""
        # Реализация аналогична существующей, но с фильтрацией
        # (код сокращён для краткости)
        return []

    async def _get_cryptopanic_news(self, symbol: str, hours: int) -> List[Dict]:
        """Получение новостей из CryptoPanic"""
        # Реализация аналогична существующей
        return []

    async def close(self):
        """Закрытие сессии"""
        if self.session and not self.session.closed:
            await self.session.close()
