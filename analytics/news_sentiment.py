#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
News Sentiment Analyzer для GIO Bot
Анализ крипто-новостей с определением sentiment через AI
"""

import requests
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from config.settings import logger
import os
import hashlib


class NewsSentimentAnalyzer:
    """
    Анализатор sentiment новостей о криптовалютах
    """

    def __init__(self, gemini_interpreter=None):
        """
        Args:
            gemini_interpreter: Экземпляр GeminiInterpreter для AI анализа
        """
        self.gemini = gemini_interpreter

        # CryptoCompare API (бесплатный, не требует API key для основных функций)
        self.cryptocompare_url = "https://min-api.cryptocompare.com/data/v2/news/"

        # Кэш новостей
        self.cache = {}
        self.cache_duration = 600  # 10 минут

        logger.info("✅ NewsSentimentAnalyzer инициализирован")

    async def get_latest_news(self, hours: int = 6, limit: int = 10) -> List[Dict]:
        """
        Получает последние новости о криптовалютах

        Args:
            hours: Период новостей (часов назад)
            limit: Максимальное количество новостей

        Returns:
            Список новостей с метаданными
        """
        try:
            # Проверяем кэш
            cache_key = f"news_{hours}h"
            if self._is_cached(cache_key):
                logger.debug(f"✅ Используем кэш новостей ({hours}h)")
                return self.cache[cache_key]

            # Запрос к CryptoCompare
            params = {"lang": "EN", "sortOrder": "latest"}

            response = requests.get(self.cryptocompare_url, params=params, timeout=10)

            if response.status_code != 200:
                logger.error(f"❌ CryptoCompare API error: {response.status_code}")
                return []

            data = response.json()

            # Проверяем ТОЛЬКО Response, игнорируем Message
            if data.get("Response") == "Error":
                logger.error(
                    f"❌ CryptoCompare response error: {data.get('Message', 'Unknown error')}"
                )
                return []

            # ✅ Успешный ответ — логируем Message как информацию
            if "Message" in data:
                logger.info(f"✅ CryptoCompare: {data['Message']}")

            raw_news = data.get("Data", [])

            # Фильтруем по времени
            cutoff_time = datetime.now() - timedelta(hours=hours)
            cutoff_timestamp = int(cutoff_time.timestamp())

            filtered_news = []
            for item in raw_news:
                published_on = item.get("published_on", 0)

                if published_on >= cutoff_timestamp:
                    news_item = {
                        "id": item.get("id"),
                        "title": item.get("title", "No title"),
                        "body": item.get("body", "")[:200],  # Первые 200 символов
                        "url": item.get("url", ""),
                        "source": item.get("source", "Unknown"),
                        "published_at": datetime.fromtimestamp(published_on),
                        "categories": item.get("categories", "").split("|"),
                        "sentiment": None,  # Будет заполнено AI анализом
                    }
                    filtered_news.append(news_item)

                    if len(filtered_news) >= limit:
                        break

            # Кэшируем результат
            self.cache[cache_key] = filtered_news

            logger.info(f"✅ Получено {len(filtered_news)} новостей за {hours}h")

            return filtered_news

        except Exception as e:
            logger.error(f"❌ get_latest_news error: {e}", exc_info=True)
            return []

    async def analyze_sentiment(self, news_list: List[Dict]) -> List[Dict]:
        """
        Анализирует sentiment для списка новостей через AI

        Args:
            news_list: Список новостей

        Returns:
            Список новостей с добавленным sentiment
        """
        try:
            if not self.gemini:
                logger.warning("⚠️ Gemini недоступен, используем rule-based sentiment")
                return self._rule_based_sentiment(news_list)

            # Анализируем каждую новость через Gemini
            for news in news_list:
                try:
                    # ✅ КЭШИРУЕМ ПО MD5 ХЭШУ ЗАГОЛОВКА (ДЕТЕРМИНИСТИЧНЫЙ!)
                    cache_key = (
                        f"sentiment_{hashlib.md5(news['title'].encode()).hexdigest()}"
                    )

                    if cache_key in self.cache:
                        news["sentiment"] = self.cache[cache_key]["sentiment"]
                        news["sentiment_emoji"] = self.cache[cache_key]["emoji"]
                        logger.debug(
                            f"✅ Используем кэш sentiment для новости: {news['title'][:50]}..."
                        )
                        continue

                    prompt = f"""Analyze the sentiment of this crypto news headline:

            Title: {news['title']}

            Respond with ONLY ONE WORD: BULLISH, BEARISH, or NEUTRAL"""

                    sentiment_raw = await self.gemini.interpret_text(prompt)

                    if sentiment_raw:
                        sentiment_text = (
                            sentiment_raw.strip().upper()
                            if isinstance(sentiment_raw, str)
                            else str(sentiment_raw).strip().upper()
                        )

                        if "BULLISH" in sentiment_text:
                            news["sentiment"] = "BULLISH"
                            news["sentiment_emoji"] = "🟢"
                        elif "BEARISH" in sentiment_text:
                            news["sentiment"] = "BEARISH"
                            news["sentiment_emoji"] = "🔴"
                        else:
                            news["sentiment"] = "NEUTRAL"
                            news["sentiment_emoji"] = "🟡"

                        # ✅ КЭШИРУЕМ РЕЗУЛЬТАТ
                        self.cache[cache_key] = {
                            "sentiment": news["sentiment"],
                            "emoji": news["sentiment_emoji"],
                        }
                    else:
                        # ✅ ИСПОЛЬЗУЕМ RULE-BASED FALLBACK И КЭШИРУЕМ
                        sentiment = self._rule_based_sentiment_single(news["title"])
                        news["sentiment"] = sentiment["sentiment"]
                        news["sentiment_emoji"] = sentiment["emoji"]

                        # ✅ КЭШИРУЕМ FALLBACK РЕЗУЛЬТАТ
                        self.cache[cache_key] = {
                            "sentiment": news["sentiment"],
                            "emoji": news["sentiment_emoji"],
                        }


                except Exception as e:
                    logger.debug(f"⚠️ AI sentiment failed for news, using fallback: {e}")
                    news["sentiment"] = "NEUTRAL"
                    news["sentiment_emoji"] = "🟡"

            return news_list

        except Exception as e:
            logger.error(f"❌ analyze_sentiment error: {e}", exc_info=True)
            return self._rule_based_sentiment(news_list)

    def _rule_based_sentiment(self, news_list: List[Dict]) -> List[Dict]:
        """
        Простой rule-based sentiment анализ (фоллбэк)
        """
        bullish_keywords = [
            "surge",
            "rally",
            "gain",
            "rise",
            "bull",
            "adoption",
            "breakthrough",
            "approval",
            "launch",
            "partnership",
        ]

        bearish_keywords = [
            "crash",
            "drop",
            "fall",
            "bear",
            "concern",
            "risk",
            "decline",
            "plunge",
            "regulatory",
            "hack",
            "scam",
        ]

        for news in news_list:
            title_lower = news["title"].lower()

            bullish_score = sum(1 for word in bullish_keywords if word in title_lower)
            bearish_score = sum(1 for word in bearish_keywords if word in title_lower)

            if bullish_score > bearish_score:
                news["sentiment"] = "BULLISH"
                news["sentiment_emoji"] = "🟢"
            elif bearish_score > bullish_score:
                news["sentiment"] = "BEARISH"
                news["sentiment_emoji"] = "🔴"
            else:
                news["sentiment"] = "NEUTRAL"
                news["sentiment_emoji"] = "🟡"

        return news_list

    def _rule_based_sentiment_single(self, title: str) -> Dict:
        """
        Простой rule-based sentiment для одной новости
        """
        bullish_keywords = [
            "surge", "rally", "gain", "rise", "bull", "adoption",
            "breakthrough", "approval", "launch", "partnership",
        ]

        bearish_keywords = [
            "crash", "drop", "fall", "bear", "concern", "risk",
            "decline", "plunge", "regulatory", "hack", "scam",
        ]

        title_lower = title.lower()

        bullish_score = sum(1 for word in bullish_keywords if word in title_lower)
        bearish_score = sum(1 for word in bearish_keywords if word in title_lower)

        if bullish_score > bearish_score:
            return {"sentiment": "BULLISH", "emoji": "🟢"}
        elif bearish_score > bullish_score:
            return {"sentiment": "BEARISH", "emoji": "🔴"}
        else:
            return {"sentiment": "NEUTRAL", "emoji": "🟡"}


    def calculate_overall_sentiment(self, news_list: List[Dict]) -> Dict:
        """
        Рассчитывает общий sentiment рынка на основе новостей

        Returns:
            {
                'overall': 'BULLISH' | 'BEARISH' | 'NEUTRAL',
                'score': float (-1.0 to 1.0),
                'bullish_count': int,
                'bearish_count': int,
                'neutral_count': int
            }
        """
        try:
            if not news_list:
                return {
                    "overall": "NEUTRAL",
                    "score": 0.0,
                    "bullish_count": 0,
                    "bearish_count": 0,
                    "neutral_count": 0,
                }

            bullish_count = sum(1 for n in news_list if n.get("sentiment") == "BULLISH")
            bearish_count = sum(1 for n in news_list if n.get("sentiment") == "BEARISH")
            neutral_count = sum(1 for n in news_list if n.get("sentiment") == "NEUTRAL")

            total = len(news_list)

            # Рассчитываем score от -1 (bearish) до +1 (bullish)
            score = (bullish_count - bearish_count) / total if total > 0 else 0

            # Определяем overall sentiment
            if score > 0.3:
                overall = "BULLISH"
            elif score < -0.3:
                overall = "BEARISH"
            else:
                overall = "NEUTRAL"

            return {
                "overall": overall,
                "score": round(score, 2),
                "bullish_count": bullish_count,
                "bearish_count": bearish_count,
                "neutral_count": neutral_count,
            }

        except Exception as e:
            logger.error(f"calculate_overall_sentiment error: {e}")
            return {
                "overall": "NEUTRAL",
                "score": 0.0,
                "bullish_count": 0,
                "bearish_count": 0,
                "neutral_count": 0,
            }

    async def generate_detailed_ai_interpretation(
        self,
        news_list: List[Dict],
        overall: Dict,
        symbol: Optional[str] = None
    ) -> str:
        """
        Генерирует ДЕТАЛЬНУЮ AI интерпретацию новостей через Gemini

        Args:
            news_list: Список новостей с sentiment
            overall: Общий sentiment (из calculate_overall_sentiment)
            symbol: Опциональный символ для фокусировки (например, "BTCUSDT")

        Returns:
            Форматированная детальная интерпретация с Summary, Key Insights, Trading Implications
        """
        try:
            if not self.gemini:
                logger.warning("⚠️ Gemini недоступен, возврат базовой интерпретации")
                return self._fallback_detailed_interpretation(overall)

            # 1. Формируем контекст новостей (топ-10)
            news_context_lines = []
            for i, news in enumerate(news_list[:10], 1):
                sentiment = news.get('sentiment', 'NEUTRAL')
                title = news['title'][:100]  # Обрезаем до 100 символов
                source = news.get('source', 'Unknown')

                news_context_lines.append(f"{i}. [{sentiment}] {title} (источник: {source})")

            news_context = "\n".join(news_context_lines)

            # 2. Формируем фокус на символе (если указан)
            symbol_focus = ""
            if symbol:
                # Убираем "USDT" из символа для читаемости
                clean_symbol = symbol.replace("USDT", "").replace("BUSD", "")
                symbol_focus = f" с фокусом на {clean_symbol}"

            # 3. Формируем prompt для Gemini
            prompt = f"""Ты — профессиональный криптовалютный аналитик. Проанализируй следующие новости{symbol_focus} и дай ДЕТАЛЬНУЮ интерпретацию на русском языке.

    НОВОСТИ:
    {news_context}

    ОБЩИЙ SENTIMENT:
    - Бычьих новостей: {overall.get('bullish_count', 0)}
    - Медвежьих новостей: {overall.get('bearish_count', 0)}
    - Нейтральных новостей: {overall.get('neutral_count', 0)}
    - Средний score: {overall.get('score', 0):.2f} (от -1.0 до +1.0)

    ИНСТРУКЦИЯ: Предоставь анализ СТРОГО в следующем формате:

    📝 Summary:
    [2-3 предложения общего резюме новостей. Какие главные темы? Что происходит в криптоиндустрии?]

    💡 Key Insights:
    • [Инсайт 1 — самое важное наблюдение]
    • [Инсайт 2 — второе по важности]
    • [Инсайт 3 — третье наблюдение]

    🎯 Trading Implications:
    [2-3 предложения о том, как это влияет на торговлю. Какие торговые возможности? Какие риски?]

    ВАЖНО:
    - Пиши кратко и по делу (максимум 400 символов на всё)
    - Используй профессиональную терминологию
    - Фокусируйся на практических выводах для трейдеров
    - НЕ используй заголовки вроде "📝 Summary:" в тексте — только содержание"""

            # 4. Вызываем Gemini API
            ai_response = await self.gemini.analyze_text(prompt)

            if ai_response and len(ai_response.strip()) > 50:
                # ✅ Успешный ответ от Gemini
                logger.info(f"✅ Gemini детальная интерпретация получена ({len(ai_response)} символов)")

                # Форматируем ответ
                return self._format_ai_interpretation(ai_response, overall)
            else:
                # ⚠️ Пустой или короткий ответ — используем fallback
                logger.warning("⚠️ Gemini вернул пустой/короткий ответ, используем fallback")
                return self._fallback_detailed_interpretation(overall)

        except Exception as e:
            logger.error(f"❌ generate_detailed_ai_interpretation error: {e}", exc_info=True)
            return self._fallback_detailed_interpretation(overall)


    def _format_ai_interpretation(self, ai_response: str, overall: Dict) -> str:
        """Форматирует AI ответ в читаемый вид"""
        try:
            # Определяем market impact и risk на основе overall sentiment
            score = overall.get('score', 0)

            if score > 0.5:
                impact = "Bullish"
                impact_score = int(60 + (score * 40))  # 60-100
                risk = "Medium-Low"
            elif score > 0.2:
                impact = "Slightly Bullish"
                impact_score = int(55 + (score * 25))  # 55-65
                risk = "Medium"
            elif score < -0.5:
                impact = "Bearish"
                impact_score = int(40 - (abs(score) * 40))  # 0-40
                risk = "Medium-High"
            elif score < -0.2:
                impact = "Slightly Bearish"
                impact_score = int(45 - (abs(score) * 25))  # 35-45
                risk = "Medium"
            else:
                impact = "Neutral"
                impact_score = 50
                risk = "Medium"

            # Форматируем вывод
            lines = [
                "🤖 AI INTERPRETATION",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "",
                ai_response.strip(),
                "",
                f"➡️ Market Impact: {impact} ({impact_score}/100)",
                "",
                f"🟡 Risk: {risk}",
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ]

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"❌ _format_ai_interpretation error: {e}")
            return self._fallback_detailed_interpretation(overall)


    def _fallback_detailed_interpretation(self, overall: Dict) -> str:
        """Базовая детальная интерпретация если Gemini недоступен"""
        try:
            score = overall.get('score', 0)
            bullish_count = overall.get('bullish_count', 0)
            bearish_count = overall.get('bearish_count', 0)
            neutral_count = overall.get('neutral_count', 0)

            # Определяем sentiment
            if score > 0.3:
                sentiment_emoji = "🟢"
                sentiment_text = "Бычий"
                action = "🚀 Рассмотри лонг-позиции на сильных активах"
            elif score < -0.3:
                sentiment_emoji = "🔴"
                sentiment_text = "Медвежий"
                action = "⏸️ Осторожно с лонгами, возможны дальнейшие падения"
            else:
                sentiment_emoji = "🟡"
                sentiment_text = "Нейтральный"
                action = "⏸️ Ожидай более чётких сигналов перед открытием позиций"

            # Определяем market impact
            if abs(score) > 0.5:
                impact = "Strong" if score > 0 else "Strong Bearish"
                impact_score = int(50 + (score * 50))
            else:
                impact = "Neutral"
                impact_score = 50

            # Определяем risk
            risk = "High" if abs(score) > 0.6 else "Medium" if abs(score) > 0.3 else "Low"

            lines = [
                "🤖 AI INTERPRETATION",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
                "",
                f"📝 Summary:",
                f"Анализ {bullish_count + bearish_count + neutral_count} новостей показывает {sentiment_text.lower()} настроение рынка ({sentiment_emoji}). "
                f"Бычьих новостей: {bullish_count}, медвежьих: {bearish_count}, нейтральных: {neutral_count}.",
                "",
                f"💡 Key Insights:",
                f"  • Общий sentiment score: {score:+.2f} (от -1.0 до +1.0)",
                f"  • {'Преобладают позитивные новости' if score > 0 else 'Преобладают негативные новости' if score < 0 else 'Баланс позитивных и негативных новостей'}",
                f"  • {'Рынок настроен оптимистично' if score > 0.3 else 'Рынок настроен пессимистично' if score < -0.3 else 'Рынок в неопределённости'}",
                "",
                f"🎯 Trading Implications:",
                f"Рынок демонстрирует {sentiment_text.lower()} настрой. {action}.",
                "",
                f"➡️ Market Impact: {impact} ({impact_score}/100)",
                "",
                f"🟡 Risk: {risk}",
                "",
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
            ]

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"❌ _fallback_detailed_interpretation error: {e}")
            return """🤖 AI INTERPRETATION
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    ➡️ Market Impact: Neutral (50/100)

    🟡 Risk: Medium

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""


    def _is_cached(self, key: str) -> bool:
        """Проверяет актуальность кэша"""
        if key not in self.cache:
            return False

        # Проверяем время жизни кэша
        # (упрощённо, можно добавить timestamp tracking)
        return True

    def format_news_report(self, news_list: List[Dict], overall: Dict) -> str:
        """Форматирует отчёт по новостям для Telegram"""
        if not news_list:
            return "📰 Нет свежих новостей"

        lines = []
        lines.append("📰 **CRYPTO NEWS SENTIMENT**")
        lines.append("━━━━━━━━━━━━━━━━━━━━━━\n")

        # Overall sentiment
        overall_emoji = (
            "🟢"
            if overall["overall"] == "BULLISH"
            else "🔴" if overall["overall"] == "BEARISH" else "🟡"
        )
        lines.append(
            f"📊 **Overall Market Sentiment:** {overall_emoji} **{overall['overall']}**"
        )
        lines.append(f"├─ Score: {overall['score']:+.2f}")
        lines.append(
            f"├─ Bullish: {overall['bullish_count']} | Bearish: {overall['bearish_count']}"
        )
        lines.append(f"└─ Neutral: {overall['neutral_count']}\n")

        lines.append("━━━━━━━━━━━━━━━━━━━━━━\n")

        # Топ-5 новостей
        lines.append("📰 **LATEST NEWS:**\n")

        for i, news in enumerate(news_list[:5], 1):
            emoji = news.get("sentiment_emoji", "🟡")
            title = news["title"][:80]  # Обрезаем длинные заголовки
            source = news.get("source", "Unknown")

            time_ago = self._time_ago(news["published_at"])

            lines.append(f"{emoji} **{title}...**")
            lines.append(f"├─ Source: {source}")
            lines.append(f"└─ {time_ago}\n")

        return "\n".join(lines)

    

    def _time_ago(self, dt: datetime) -> str:
        """Возвращает строку 'X hours ago'"""
        delta = datetime.now() - dt

        if delta.days > 0:
            return f"{delta.days}d ago"
        elif delta.seconds >= 3600:
            hours = delta.seconds // 3600
            return f"{hours}h ago"
        else:
            minutes = delta.seconds // 60
            return f"{minutes}m ago"
