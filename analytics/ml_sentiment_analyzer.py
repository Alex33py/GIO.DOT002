#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced ML/NLP Sentiment Analyzer для GIO Crypto Bot
Использует FinBERT + Crypto-BERT + Topic Modeling
"""

import asyncio
import aiohttp
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict, deque
import re
from config.settings import logger

# ML/NLP Libraries
try:
    from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
    import torch
    TRANSFORMERS_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ transformers не установлен. Установите: pip install transformers torch")
    TRANSFORMERS_AVAILABLE = False

try:
    from sklearn.decomposition import LatentDirichletAllocation
    from sklearn.feature_extraction.text import CountVectorizer
    import spacy
    SKLEARN_AVAILABLE = True
except ImportError:
    logger.warning("⚠️ sklearn/spacy не установлен. Установите: pip install scikit-learn spacy")
    SKLEARN_AVAILABLE = False


class MLSentimentAnalyzer:
    """
    Advanced ML/NLP Sentiment Analyzer

    Features:
    - FinBERT для финансовых новостей
    - Crypto-BERT для крипто-специфичных текстов
    - Topic modeling (LDA)
    - Named Entity Recognition (NER)
    - Sentiment momentum tracking
    - Fear & Greed Index calculation
    """

    def __init__(self, use_gpu: bool = False):
        """
        Инициализация ML Sentiment Analyzer

        Args:
            use_gpu: Использовать GPU для inference (если доступен)
        """
        self.use_gpu = use_gpu and torch.cuda.is_available() if TRANSFORMERS_AVAILABLE else False
        self.device = "cuda" if self.use_gpu else "cpu"

        # Models
        self.finbert_pipeline = None
        self.crypto_bert_pipeline = None
        self.nlp = None
        self.lda_model = None
        self.vectorizer = None

        # Sentiment history для momentum
        self.sentiment_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Cache
        self.cache: Dict[str, Dict] = {}
        self.cache_ttl = 300  # 5 minutes

        # Crypto-specific keywords
        self.positive_keywords = {
            "bullish", "moon", "pump", "rally", "surge", "breakout", "adoption",
            "partnership", "integration", "upgrade", "listing", "institutional",
            "accumulation", "whale", "buy", "long", "support", "golden cross",
            "all-time high", "ath", "breakthrough", "momentum", "strong",
        }

        self.negative_keywords = {
            "bearish", "dump", "crash", "fall", "drop", "correction", "fud", "fear",
            "uncertain", "doubt", "sell", "short", "resistance", "death cross",
            "hack", "scam", "regulation", "ban", "lawsuit", "investigation",
            "weak", "decline", "plunge", "collapse",
        }

        logger.info("✅ MLSentimentAnalyzer инициализирован")

    async def initialize(self):
        """Загрузка ML моделей"""
        try:
            if not TRANSFORMERS_AVAILABLE:
                logger.warning("⚠️ Transformers недоступен, используем fallback")
                return False

            logger.info("🔄 Загрузка ML моделей...")

            # 1. FinBERT (ProsusAI/finbert)
            try:
                logger.info("📥 Загрузка FinBERT...")
                self.finbert_pipeline = pipeline(
                    "sentiment-analysis",
                    model="ProsusAI/finbert",
                    device=0 if self.use_gpu else -1,
                    truncation=True,
                    max_length=512,
                )
                logger.info("   ✅ FinBERT загружен")
            except Exception as e:
                logger.warning(f"   ⚠️ FinBERT не загружен: {e}")

            # 2. Crypto-BERT (ElKulako/cryptobert)
            try:
                logger.info("📥 Загрузка CryptoBERT...")
                self.crypto_bert_pipeline = pipeline(
                    "sentiment-analysis",
                    model="ElKulako/cryptobert",
                    device=0 if self.use_gpu else -1,
                    truncation=True,
                    max_length=512,
                )
                logger.info("   ✅ CryptoBERT загружен")
            except Exception as e:
                logger.warning(f"   ⚠️ CryptoBERT не загружен: {e}")

            # 3. spaCy для NER
            if SKLEARN_AVAILABLE:
                try:
                    logger.info("📥 Загрузка spaCy...")
                    self.nlp = spacy.load("en_core_web_sm")
                    logger.info("   ✅ spaCy загружен")
                except Exception as e:
                    logger.warning(f"   ⚠️ spaCy не загружен: {e}")

            # 4. LDA для topic modeling
            if SKLEARN_AVAILABLE:
                self.vectorizer = CountVectorizer(
                    max_features=100, stop_words="english", max_df=0.95, min_df=2
                )
                self.lda_model = LatentDirichletAllocation(n_components=5, random_state=42)

            logger.info("✅ Все ML модели загружены")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки ML моделей: {e}")
            return False

    async def analyze_news(self, news: List[Dict]) -> Dict:
        """
        Полный анализ новостей с ML/NLP

        Args:
            news: Список новостей [{title, body, published_on, source}]

        Returns:
            Dict с результатами анализа
        """
        try:
            if not news:
                return self._get_default_sentiment()

            analysis_start = datetime.utcnow()

            # 1. Извлечение текстов
            texts = []
            for article in news:
                title = article.get("title", "")
                body = article.get("body", "")
                text = f"{title}. {body}"
                texts.append(text)

            # 2. FinBERT Analysis
            finbert_scores = await self._analyze_with_finbert(texts)

            # 3. CryptoBERT Analysis
            cryptobert_scores = await self._analyze_with_cryptobert(texts)

            # 4. Keyword Analysis
            keyword_scores = self._analyze_keywords(texts)

            # 5. Named Entity Recognition
            entities = await self._extract_entities(texts[:10])  # Top 10 for NER

            # 6. Topic Modeling
            topics = await self._extract_topics(texts)

            # 7. Sentiment Momentum
            momentum = self._calculate_sentiment_momentum(news)

            # 8. Fear & Greed Index
            fear_greed_index = self._calculate_fear_greed_index(
                finbert_scores, cryptobert_scores, keyword_scores, momentum
            )

            # 9. Aggregate scores
            final_score = self._aggregate_scores(
                finbert_scores, cryptobert_scores, keyword_scores
            )

            analysis_time = (datetime.utcnow() - analysis_start).total_seconds()

            result = {
                "sentiment_score": final_score,
                "sentiment_label": self._score_to_label(final_score),
                "finbert_score": finbert_scores.get("mean", 0),
                "cryptobert_score": cryptobert_scores.get("mean", 0),
                "keyword_score": keyword_scores.get("mean", 0),
                "sentiment_momentum": momentum,
                "fear_greed_index": fear_greed_index,
                "entities": entities,
                "topics": topics,
                "news_count": len(news),
                "analysis_time": analysis_time,
                "timestamp": datetime.utcnow().isoformat(),
            }

            logger.info(
                f"📊 ML Sentiment: {final_score:.2f} "
                f"({result['sentiment_label']}) | "
                f"FGI: {fear_greed_index:.1f} | "
                f"Momentum: {momentum:.2f}"
            )

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка ML sentiment анализа: {e}")
            return self._get_default_sentiment()

    async def _analyze_with_finbert(self, texts: List[str]) -> Dict:
        """Анализ с FinBERT"""
        if not self.finbert_pipeline:
            return {"mean": 0.0, "std": 0.0, "scores": []}

        try:
            scores = []
            for text in texts[:50]:  # Limit для performance
                text_truncated = text[:512]
                result = self.finbert_pipeline(text_truncated)[0]

                label = result["label"].lower()
                confidence = result["score"]

                if label == "positive":
                    score = confidence
                elif label == "negative":
                    score = -confidence
                else:
                    score = 0.0

                scores.append(score)

            return {
                "mean": np.mean(scores) if scores else 0.0,
                "std": np.std(scores) if scores else 0.0,
                "scores": scores,
            }

        except Exception as e:
            logger.error(f"❌ FinBERT error: {e}")
            return {"mean": 0.0, "std": 0.0, "scores": []}

    async def _analyze_with_cryptobert(self, texts: List[str]) -> Dict:
        """Анализ с CryptoBERT"""
        if not self.crypto_bert_pipeline:
            return {"mean": 0.0, "std": 0.0, "scores": []}

        try:
            scores = []
            for text in texts[:50]:
                text_truncated = text[:512]
                result = self.crypto_bert_pipeline(text_truncated)[0]

                label = result["label"].lower()
                confidence = result["score"]

                if "pos" in label:
                    score = confidence
                elif "neg" in label:
                    score = -confidence
                else:
                    score = 0.0

                scores.append(score)

            return {
                "mean": np.mean(scores) if scores else 0.0,
                "std": np.std(scores) if scores else 0.0,
                "scores": scores,
            }

        except Exception as e:
            logger.error(f"❌ CryptoBERT error: {e}")
            return {"mean": 0.0, "std": 0.0, "scores": []}

    def _analyze_keywords(self, texts: List[str]) -> Dict:
        """Анализ ключевых слов"""
        scores = []

        for text in texts:
            text_lower = text.lower()
            positive_count = sum(1 for kw in self.positive_keywords if kw in text_lower)
            negative_count = sum(1 for kw in self.negative_keywords if kw in text_lower)

            total = positive_count + negative_count
            if total > 0:
                score = (positive_count - negative_count) / total
            else:
                score = 0.0

            scores.append(score)

        return {
            "mean": np.mean(scores) if scores else 0.0,
            "std": np.std(scores) if scores else 0.0,
            "scores": scores,
        }

    async def _extract_entities(self, texts: List[str]) -> Dict:
        """Named Entity Recognition"""
        if not self.nlp:
            return {}

        try:
            entities = defaultdict(int)

            for text in texts:
                doc = self.nlp(text[:1000])
                for ent in doc.ents:
                    if ent.label_ in ["ORG", "PERSON", "PRODUCT", "GPE"]:
                        entities[ent.text] += 1

            top_entities = dict(
                sorted(entities.items(), key=lambda x: x[1], reverse=True)[:10]
            )

            return top_entities

        except Exception as e:
            logger.error(f"❌ NER error: {e}")
            return {}

    async def _extract_topics(self, texts: List[str]) -> List[str]:
        """Topic modeling с LDA"""
        if not self.lda_model or len(texts) < 5:
            return []

        try:
            X = self.vectorizer.fit_transform(texts)
            self.lda_model.fit(X)

            feature_names = self.vectorizer.get_feature_names_out()
            topics = []

            for topic_idx, topic in enumerate(self.lda_model.components_):
                top_words = [feature_names[i] for i in topic.argsort()[-5:][::-1]]
                topics.append(", ".join(top_words))

            return topics[:3]

        except Exception as e:
            logger.error(f"❌ Topic modeling error: {e}")
            return []

    def _calculate_sentiment_momentum(self, news: List[Dict]) -> float:
        """Расчёт momentum sentiment"""
        try:
            now = datetime.utcnow()
            cutoff_12h = now - timedelta(hours=12)
            cutoff_24h = now - timedelta(hours=24)

            recent_news = []
            older_news = []

            for article in news:
                pub_time = datetime.fromtimestamp(article.get("published_on", 0))

                if pub_time > cutoff_12h:
                    recent_news.append(article)
                elif pub_time > cutoff_24h:
                    older_news.append(article)

            if not recent_news or not older_news:
                return 0.0

            recent_score = self._quick_sentiment(recent_news)
            older_score = self._quick_sentiment(older_news)

            return recent_score - older_score

        except Exception as e:
            logger.error(f"❌ Momentum calculation error: {e}")
            return 0.0

    def _quick_sentiment(self, news: List[Dict]) -> float:
        """Быстрый sentiment для momentum"""
        scores = []

        for article in news:
            text = f"{article.get('title', '')} {article.get('body', '')}".lower()
            positive_count = sum(1 for kw in self.positive_keywords if kw in text)
            negative_count = sum(1 for kw in self.negative_keywords if kw in text)

            total = positive_count + negative_count
            if total > 0:
                score = (positive_count - negative_count) / total
                scores.append(score)

        return np.mean(scores) if scores else 0.0

    def _calculate_fear_greed_index(
        self, finbert: Dict, cryptobert: Dict, keywords: Dict, momentum: float
    ) -> float:
        """Расчёт Fear & Greed Index (0-100)"""
        try:
            finbert_score = (finbert.get("mean", 0) + 1) * 50
            cryptobert_score = (cryptobert.get("mean", 0) + 1) * 50
            keyword_score = (keywords.get("mean", 0) + 1) * 50
            momentum_score = (momentum + 1) * 50

            fgi = (
                finbert_score * 0.35
                + cryptobert_score * 0.35
                + keyword_score * 0.20
                + momentum_score * 0.10
            )

            return max(0, min(100, fgi))

        except Exception as e:
            logger.error(f"❌ FGI calculation error: {e}")
            return 50.0

    def _aggregate_scores(
        self, finbert: Dict, cryptobert: Dict, keywords: Dict
    ) -> float:
        """Агрегация scores"""
        scores = []

        if finbert.get("mean") is not None:
            scores.append(finbert["mean"])

        if cryptobert.get("mean") is not None:
            scores.append(cryptobert["mean"])

        if keywords.get("mean") is not None:
            scores.append(keywords["mean"])

        if not scores:
            return 0.0

        weights = [0.4, 0.4, 0.2][: len(scores)]
        return sum(s * w for s, w in zip(scores, weights)) / sum(weights)

    def _score_to_label(self, score: float) -> str:
        """Конвертация score в label"""
        if score > 0.6:
            return "VERY_BULLISH"
        elif score > 0.2:
            return "BULLISH"
        elif score > -0.2:
            return "NEUTRAL"
        elif score > -0.6:
            return "BEARISH"
        else:
            return "VERY_BEARISH"

    def _get_default_sentiment(self) -> Dict:
        """Default sentiment"""
        return {
            "sentiment_score": 0.0,
            "sentiment_label": "NEUTRAL",
            "finbert_score": 0.0,
            "cryptobert_score": 0.0,
            "keyword_score": 0.0,
            "sentiment_momentum": 0.0,
            "fear_greed_index": 50.0,
            "entities": {},
            "topics": [],
            "news_count": 0,
            "analysis_time": 0.0,
            "timestamp": datetime.utcnow().isoformat(),
        }


# Экспорт
__all__ = ["MLSentimentAnalyzer"]
