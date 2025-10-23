# -*- coding: utf-8 -*-
"""
Унифицированный коннектор для новостных API
Поддерживает CryptoPanic и CryptoCompare
С кэшированием и правильной обработкой rate limit
"""

import asyncio
import aiohttp
import json
import re
from datetime import datetime
from typing import Dict, List, Optional, Set
from collections import deque
from pathlib import Path
from config.settings import CRYPTOPANIC_API_KEY, CRYPTOCOMPARE_API_KEY, logger
from config.constants import API_ENDPOINTS, SYMBOL_FILTERS, TIME_FORMATS
from core.exceptions import APIConnectionError
from utils.helpers import current_epoch_ms, datetime_to_epoch_ms
from utils.validators import validate_news_data


class SmartRateLimiter:
    """Умный ограничитель запросов с поддержкой burst режима"""

    def __init__(self, requests_per_minute: int = 30, burst_allowance: int = 10):
        self.requests_per_minute = requests_per_minute
        self.burst_allowance = burst_allowance
        self.requests = deque()
        self.burst_used = 0

    async def acquire(self, priority: str = "normal"):
        """Получение разрешения на запрос"""
        current_time = current_epoch_ms()

        # Очищаем старые запросы (старше минуты)
        while self.requests and current_time - self.requests[0] > 60000:
            self.requests.popleft()

        # Сбрасываем burst счётчик каждую минуту
        if not self.requests:
            self.burst_used = 0

        # Проверяем лимиты
        if len(self.requests) < self.requests_per_minute:
            self.requests.append(current_time)
            return True

        # Проверяем burst режим для приоритетных запросов
        if priority == "high" and self.burst_used < self.burst_allowance:
            self.burst_used += 1
            self.requests.append(current_time)
            return True

        # Ожидаем освобождения слота
        if self.requests:
            wait_time = 60 - (current_time - self.requests[0]) / 1000
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        self.requests.append(current_epoch_ms())
        return True


class UnifiedNewsConnector:
    """Унифицированный коннектор для получения новостей из разных источников"""

    def __init__(self):
        """Инициализация коннектора"""
        self.cryptopanic_key = CRYPTOPANIC_API_KEY
        self.cryptocompare_key = CRYPTOCOMPARE_API_KEY

        # HTTP сессия
        self.session = None

        # Ограничители запросов
        self.rate_limiter = SmartRateLimiter(requests_per_minute=30, burst_allowance=10)

        # Кэш новостей (УЛУЧШЕНО)
        self.cryptopanic_cache = (
            {}
        )  # {cache_key: {'data': [], 'timestamp': int, 'ttl': int}}
        self.cryptocompare_cache = {}
        self.news_cache = deque(maxlen=1000)
        self.seen_news_ids: Set[str] = set()

        # Статистика запросов (УЛУЧШЕНО)
        self.last_cryptopanic_request = 0
        self.last_cryptocompare_request = 0
        self.cryptopanic_retry_after = 0  # Timestamp когда можно снова делать запрос

        logger.info("✅ UnifiedNewsConnector инициализирован")

        # ✅ PERSISTENT CACHE (НОВЫЙ КОД)
        self.cryptopanic_cache_file = Path("data/cryptopanic_cache.json")
        self.cryptocompare_cache_file = Path("data/cryptocompare_cache.json")

        # Создаём директорию data если не существует
        self.cryptopanic_cache_file.parent.mkdir(exist_ok=True)

        # Загружаем CryptoPanic кэш с диска при старте
        if self.cryptopanic_cache_file.exists():
            try:
                with open(self.cryptopanic_cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    self.cryptopanic_cache = cache_data.get("cryptopanic_cache", {})
                    cache_count = len(self.cryptopanic_cache)
                    logger.info(
                        f"✅ CryptoPanic cache loaded from disk ({cache_count} entries)"
                    )
            except Exception as e:
                logger.error(f"❌ Failed to load CryptoPanic cache: {e}")
                self.cryptopanic_cache = {}

        # Загружаем CryptoCompare кэш с диска при старте
        if self.cryptocompare_cache_file.exists():
            try:
                with open(self.cryptocompare_cache_file, "r", encoding="utf-8") as f:
                    cache_data = json.load(f)
                    self.cryptocompare_cache = cache_data.get("cryptocompare_cache", {})
                    cache_count = len(self.cryptocompare_cache)
                    logger.info(
                        f"✅ CryptoCompare cache loaded from disk ({cache_count} entries)"
                    )
            except Exception as e:
                logger.error(f"❌ Failed to load CryptoCompare cache: {e}")
                self.cryptocompare_cache = {}

    async def get_session(self):
        """Получение HTTP сессии"""
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def fetch_unified_news(
        self, symbols: List[str] = None, max_age_hours: int = 24
    ) -> List[Dict]:
        """Получение новостей из всех источников"""
        try:
            symbols = symbols or ["BTC"]
            all_news = []

            # CryptoPanic новости
            try:
                cryptopanic_news = await self.fetch_cryptopanic_news(
                    symbols, max_age_hours
                )
                all_news.extend(cryptopanic_news)
                logger.info(f"📰 CryptoPanic: {len(cryptopanic_news)} новостей")
            except Exception as e:
                logger.error(f"❌ CryptoPanic API ошибка: {e}")

            # CryptoCompare новости
            try:
                cryptocompare_news = await self.fetch_cryptocompare_news()
                all_news.extend(cryptocompare_news)
                logger.info(f"📰 CryptoCompare: {len(cryptocompare_news)} новостей")
            except Exception as e:
                logger.error(f"❌ CryptoCompare API ошибка: {e}")

            # Дедупликация по заголовку и времени
            unique_news = []
            seen = set()

            for news_item in all_news:
                if news_item is None or not isinstance(news_item, dict):
                    continue

                key = (
                    news_item.get("title", "").lower().strip(),
                    news_item.get("published_at", 0),
                )

                if key not in seen and key[0]:
                    seen.add(key)
                    unique_news.append(news_item)

            # Сортировка по времени (новые первыми)
            unique_news.sort(key=lambda x: x.get("published_at", 0), reverse=True)

            logger.info(f"📊 Итого уникальных новостей: {len(unique_news)}")
            return unique_news

        except Exception as e:
            logger.error(f"❌ Ошибка получения новостей: {e}")
            return []

    async def get_aggregated_news(
        self, symbol: str = None, limit: int = 50
    ) -> List[Dict]:
        """
        Получить агрегированные новости из всех источников
        С кэшированием и правильной обработкой параметров
        """
        all_news = []

        try:
            # Преобразуем symbol в список для fetch_cryptopanic_news
            symbols = [symbol] if symbol else ["BTC"]

            # Получаем новости параллельно
            results = await asyncio.gather(
                self.fetch_cryptopanic_news(
                    symbols, 24
                ),  # symbols: List, max_age_hours: int
                self.fetch_cryptocompare_news(symbol),  # symbol: str (опционально)
                return_exceptions=True,
            )

            # Проверяем каждый результат
            source_names = ["CryptoPanic", "CryptoCompare"]

            for idx, result in enumerate(results):
                source_name = (
                    source_names[idx] if idx < len(source_names) else f"Source {idx}"
                )

                if isinstance(result, Exception):
                    logger.warning(
                        f"⚠️ Ошибка при получении новостей из {source_name}: {result}"
                    )
                    continue

                if result is None:
                    logger.warning(f"⚠️ {source_name} вернул None")
                    continue

                if not isinstance(result, list):
                    logger.warning(
                        f"⚠️ {source_name}: ожидался список, получен {type(result)}"
                    )
                    continue

                all_news.extend(result)

            # Дедупликация по заголовку и времени
            unique_news = []
            seen = set()

            for news_item in all_news:
                if news_item is None or not isinstance(news_item, dict):
                    continue

                key = (
                    news_item.get("title", "").lower().strip(),
                    news_item.get("published_at", 0),
                )

                if key not in seen and key[0]:
                    seen.add(key)
                    unique_news.append(news_item)

            # Сортировка по времени (новые первыми)
            unique_news.sort(key=lambda x: x.get("published_at", 0), reverse=True)

            logger.info(f"📊 Итого уникальных новостей: {len(unique_news)}")
            return unique_news[:limit]

        except Exception as e:
            logger.error(f"❌ Ошибка агрегации новостей: {e}")
            return []

    async def fetch_cryptopanic_news(
        self, symbols: List[str], max_age_hours: int
    ) -> List[Dict]:
        """
        Получение новостей из CryptoPanic API
        ✅ С кэшированием (15 минут TTL)
        ✅ С правильной обработкой HTTP 429
        ✅ С минимальным интервалом между запросами (15 минут)
        """
        try:
            # 1. Проверка API ключа
            if not self.cryptopanic_key:
                logger.warning("⚠️ CryptoPanic API ключ не найден")
                return []

            # 2. Создание cache key
            cache_key = f"cryptopanic_{'_'.join(sorted(symbols))}"
            current_time = current_epoch_ms()

            # 3. ✅ ПРОВЕРКА КЭША (NEW!)
            if cache_key in self.cryptopanic_cache:
                cached_entry = self.cryptopanic_cache[cache_key]
                cache_age = (current_time - cached_entry["timestamp"]) / 1000
                ttl = cached_entry.get("ttl", 900)  # 15 минут по умолчанию

                if cache_age < ttl:
                    logger.debug(
                        f"📦 CryptoPanic cache HIT: {cache_key} "
                        f"(age: {cache_age:.0f}s/{ttl}s)"
                    )
                    return cached_entry["data"]
                else:
                    logger.debug(
                        f"⏰ CryptoPanic cache EXPIRED: {cache_age:.0f}s > {ttl}s"
                    )

            # 4. ✅ ПРОВЕРКА RETRY_AFTER (NEW!)
            if self.cryptopanic_retry_after > 0:
                if current_time < self.cryptopanic_retry_after:
                    wait_time = (self.cryptopanic_retry_after - current_time) / 1000
                    logger.warning(
                        f"⚠️ CryptoPanic: retry_after active, "
                        f"waiting {wait_time:.0f}s ({wait_time/60:.1f} min)"
                    )
                    # Возвращаем кэшированные данные если есть
                    if cache_key in self.cryptopanic_cache:
                        logger.info("📦 Returning cached data due to retry_after")
                        return self.cryptopanic_cache[cache_key]["data"]
                    return []
                else:
                    # Таймер истек, сбрасываем
                    self.cryptopanic_retry_after = 0

            # 5. ✅ ПРОВЕРКА МИНИМАЛЬНОГО ИНТЕРВАЛА (NEW!)
            min_interval = 900  # 15 минут = 900 секунд
            if self.last_cryptopanic_request > 0:
                time_since_last = (current_time - self.last_cryptopanic_request) / 1000
                if time_since_last < min_interval:
                    wait_time = min_interval - time_since_last
                    logger.debug(
                        f"⏳ CryptoPanic rate limit: "
                        f"waiting {wait_time:.0f}s ({wait_time/60:.1f} min) before next request"
                    )
                    # Возвращаем кэшированные данные если есть
                    if cache_key in self.cryptopanic_cache:
                        logger.debug("📦 Returning cached data due to rate limit")
                        return self.cryptopanic_cache[cache_key]["data"]
                    return []

            # 6. Rate limiter (существующий)
            await self.rate_limiter.acquire(priority="normal")
            session = await self.get_session()

            # 7. Формируем параметры запроса
            currencies = ",".join(symbols).upper()
            url = (
                API_ENDPOINTS["cryptopanic"]["base_url"]
                + API_ENDPOINTS["cryptopanic"]["posts"]
            )

            params = {
                "auth_token": self.cryptopanic_key,
                "currencies": currencies,
                "filter": "important",
                "public": "true",
                "limit": 50,
            }

            logger.debug(f"📡 CryptoPanic request: {currencies}")

            # 8. Выполнение запроса
            async with session.get(url, params=params) as response:
                # Обновляем время последнего запроса
                self.last_cryptopanic_request = current_epoch_ms()

                if response.status == 200:
                    data = await response.json()

                    if "results" in data:
                        news_items = []
                        cutoff_time = current_epoch_ms() - (max_age_hours * 3600000)

                        for item in data["results"]:
                            try:
                                # Парсинг времени публикации
                                published_at = item.get("published_at", "")
                                timestamp = datetime_to_epoch_ms(published_at)

                                if timestamp < cutoff_time:
                                    continue

                                # Формирование объекта новости
                                news_item = {
                                    "id": f"cp_{item.get('id', '')}",
                                    "title": item.get("title", "").strip(),
                                    "content": item.get("title", "").strip(),
                                    "published_at": published_at,
                                    "timestamp": timestamp,
                                    "url": item.get("url", ""),
                                    "source": "cryptopanic",
                                    "kind": item.get("kind", "news"),
                                    "domain": item.get("domain", ""),
                                    "votes": item.get("votes", {}),
                                }

                                if validate_news_data(news_item):
                                    news_items.append(news_item)

                            except Exception as e:
                                logger.warning(
                                    f"⚠️ Ошибка обработки CryptoPanic новости: {e}"
                                )
                                continue

                                # ✅ СОХРАНЕНИЕ В КЭШ RAM
                        self.cryptopanic_cache[cache_key] = {
                            "data": news_items,
                            "timestamp": current_epoch_ms(),
                            "ttl": 900,
                        }

                        # ✅ СОХРАНЕНИЕ КЭША НА ДИСК (НОВЫЙ КОД)
                        try:
                            cache_data = {
                                "cryptopanic_cache": self.cryptopanic_cache,
                                "saved_at": current_epoch_ms(),
                            }
                            with open(
                                self.cryptopanic_cache_file, "w", encoding="utf-8"
                            ) as f:
                                json.dump(cache_data, f, ensure_ascii=False, indent=2)
                            logger.debug(f"💾 CryptoPanic cache saved to disk")
                        except Exception as e:
                            logger.error(f"❌ Failed to save CryptoPanic cache: {e}")

                        logger.info(
                            f"📰 CryptoPanic: {len(news_items)} новостей (cached)"
                        )
                        return news_items

                    else:
                        logger.warning("⚠️ CryptoPanic: нет 'results' в ответе")
                        return []

                elif response.status == 429:
                    # ✅ ПРАВИЛЬНАЯ ОБРАБОТКА HTTP 429 (NEW!)
                    retry_after_header = response.headers.get("Retry-After")

                    if retry_after_header:
                        try:
                            retry_seconds = int(retry_after_header)
                            self.cryptopanic_retry_after = current_epoch_ms() + (
                                retry_seconds * 1000
                            )
                            logger.error(
                                f"❌ CryptoPanic HTTP 429: "
                                f"Retry after {retry_seconds}s ({retry_seconds/60:.1f} min)"
                            )
                        except ValueError:
                            # Retry-After может быть датой
                            logger.error(
                                "❌ CryptoPanic HTTP 429: invalid Retry-After header"
                            )
                            self.cryptopanic_retry_after = current_epoch_ms() + (
                                900 * 1000
                            )  # 15 минут
                    else:
                        # Нет заголовка - ждём 15 минут
                        self.cryptopanic_retry_after = current_epoch_ms() + (900 * 1000)
                        logger.error(
                            "❌ CryptoPanic HTTP 429: "
                            "no Retry-After header, waiting 15 min"
                        )

                    # Возвращаем кэшированные данные если есть
                    if cache_key in self.cryptopanic_cache:
                        logger.info("📦 Returning cached data due to rate limit (429)")
                        return self.cryptopanic_cache[cache_key]["data"]

                    return []

                else:
                    logger.error(f"❌ CryptoPanic HTTP ошибка: {response.status}")

                    # Возвращаем кэшированные данные если есть
                    if cache_key in self.cryptopanic_cache:
                        logger.debug("📦 Returning cached data due to HTTP error")
                        return self.cryptopanic_cache[cache_key]["data"]

                    return []

        except asyncio.TimeoutError:
            logger.error("❌ CryptoPanic API timeout")

            # Возвращаем кэшированные данные если есть
            cache_key = f"cryptopanic_{'_'.join(sorted(symbols))}"
            if cache_key in self.cryptopanic_cache:
                logger.debug("📦 Returning cached data due to timeout")
                return self.cryptopanic_cache[cache_key]["data"]

            return []

        except Exception as e:
            logger.error(f"❌ CryptoPanic API ошибка: {e}")
            return []

    async def fetch_cryptocompare_news(self, symbol: str = None) -> List[Dict]:
        """
        Получить новости из CryptoCompare с правильной обработкой None
        ✅ С кэшированием (15 минут TTL)
        """
        try:
            if not self.cryptocompare_key:
                logger.warning("⚠️ CryptoCompare API ключ не найден")
                return []

            # 1. Создание cache key
            cache_key = f"cryptocompare_{symbol or 'all'}"
            current_time = current_epoch_ms()

            # 2. ✅ ПРОВЕРКА КЭША (NEW!)
            if cache_key in self.cryptocompare_cache:
                cached_entry = self.cryptocompare_cache[cache_key]
                cache_age = (current_time - cached_entry["timestamp"]) / 1000
                ttl = cached_entry.get("ttl", 900)

                if cache_age < ttl:
                    logger.debug(
                        f"📦 CryptoCompare cache HIT: {cache_key} "
                        f"(age: {cache_age:.0f}s/{ttl}s)"
                    )
                    return cached_entry["data"]

            session = await self.get_session()

            endpoint = "https://min-api.cryptocompare.com/data/v2/news/"
            params = {"api_key": self.cryptocompare_key, "lang": "EN"}

            # Добавляем фильтр по категориям вместо символа
            if symbol and symbol.upper() in ["BTC", "BTCUSDT"]:
                params["categories"] = "BTC"
            elif symbol and symbol.upper() in ["ETH", "ETHUSDT"]:
                params["categories"] = "ETH"

            async with session.get(endpoint, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()

                    # КРИТИЧНО: Проверяем что data и data['Data'] не None
                    if data is None or not isinstance(data, dict):
                        logger.warning(
                            "⚠️ CryptoCompare вернул None или невалидный объект"
                        )
                        return []

                    news_list = data.get("Data", None)

                    # КРИТИЧНО: Проверяем news_list перед итерацией
                    if news_list is None or not isinstance(news_list, list):
                        logger.warning(
                            f"⚠️ CryptoCompare: 'Data' = {type(news_list)}, ожидался список"
                        )
                        return []

                    # Безопасная итерация
                    processed_news = []
                    for item in news_list:
                        if item is None or not isinstance(item, dict):
                            continue

                        processed_news.append(
                            {
                                "id": item.get("id", ""),
                                "title": item.get("title", "No title"),
                                "body": item.get("body", "")[:500],
                                "published_at": item.get("published_on", 0),
                                "source": "CryptoCompare",
                                "url": item.get("url", ""),
                                "categories": item.get("categories", "").split("|"),
                                "tags": item.get("tags", "").split("|"),
                            }
                        )

                        # ✅ СОХРАНЕНИЕ В КЭШ RAM
                    self.cryptocompare_cache[cache_key] = {
                        "data": processed_news,
                        "timestamp": current_epoch_ms(),
                        "ttl": 900,
                    }

                    # ✅ СОХРАНЕНИЕ КЭША НА ДИСК (НОВЫЙ КОД)
                    try:
                        cache_data = {
                            "cryptocompare_cache": self.cryptocompare_cache,
                            "saved_at": current_epoch_ms(),
                        }
                        with open(
                            self.cryptocompare_cache_file, "w", encoding="utf-8"
                        ) as f:
                            json.dump(cache_data, f, ensure_ascii=False, indent=2)
                        logger.debug(f"💾 CryptoCompare cache saved to disk")
                    except Exception as e:
                        logger.error(f"❌ Failed to save CryptoCompare cache: {e}")

                    logger.info(
                        f"📰 CryptoCompare: {len(processed_news)} новостей (cached)"
                    )
                    return processed_news

                elif response.status == 429:
                    logger.warning("⚠️ CryptoCompare rate limit exceeded")

                    # Возвращаем кэш если есть
                    if cache_key in self.cryptocompare_cache:
                        return self.cryptocompare_cache[cache_key]["data"]

                    return []
                else:
                    logger.warning(f"⚠️ CryptoCompare API status: {response.status}")
                    return []

        except asyncio.TimeoutError:
            logger.error("❌ CryptoCompare API timeout")

            # Возвращаем кэш если есть
            if cache_key in self.cryptocompare_cache:
                return self.cryptocompare_cache[cache_key]["data"]

            return []
        except Exception as e:
            logger.error(f"❌ CryptoCompare API ошибка: {e}")
            return []

    async def get_news_by_symbol(self, symbol: str, limit: int = 10) -> List[Dict]:
        """
        Получить новости для конкретного символа с умной фильтрацией

        Args:
            symbol: Символ (BTC, ETH, BTCUSDT, etc)
            limit: Максимум новостей (по умолчанию 10)

        Returns:
            Список отфильтрованных новостей для символа
        """
        try:
            # Нормализуем символ (убираем USDT/USD)
            clean_symbol = symbol.replace("USDT", "").replace("USD", "").upper()

            # Словарь ключевых слов для фильтрации
            symbol_keywords = {
                "BTC": ["bitcoin", "btc", "btcusd", "btcusdt", "xbt"],
                "ETH": ["ethereum", "eth", "ether", "vitalik", "ethusdt", "ethbtc"],
                "BNB": ["binance", "bnb", "cz", "bnbusdt", "bnbbtc"],
                "SOL": ["solana", "sol", "solusdt", "anatoly"],
                "XRP": ["ripple", "xrp", "xrpusdt", "xrpbtc"],
                "ADA": ["cardano", "ada", "adausdt", "charles hoskinson"],
                "DOGE": ["dogecoin", "doge", "dogeusdt", "elon"],
                "MATIC": ["polygon", "matic", "maticusdt"],
                "DOT": ["polkadot", "dot", "dotusdt", "gavin"],
                "AVAX": ["avalanche", "avax", "avaxusdt"],
                "LINK": ["chainlink", "link", "linkusdt", "sergey"],
                "UNI": ["uniswap", "uni", "uniusdt"],
                "ATOM": ["cosmos", "atom", "atomusdt"],
                "LTC": ["litecoin", "ltc", "ltcusdt"],
                "BCH": ["bitcoin cash", "bch", "bchusdt"],
                "APT": ["aptos", "apt", "aptusdt"],
                "ARB": ["arbitrum", "arb", "arbusdt"],
                "OP": ["optimism", "op", "opusdt"],
                "ALT": [
                    "altcoin",
                    "alt",
                    "crypto",
                    "cryptocurrency",
                    "defi",
                    "nft",
                    "web3",
                    "blockchain",
                ],
            }

            # Получаем ключевые слова для символа
            keywords = symbol_keywords.get(clean_symbol, [clean_symbol.lower()])

            logger.debug(
                f"🔍 Фильтрация новостей по {clean_symbol} (keywords: {keywords[:3]}...)"
            )

            # Получаем все новости (больше чем limit для лучшей фильтрации)
            all_news = await self.get_aggregated_news(symbol=clean_symbol, limit=100)

            if not all_news:
                logger.warning(f"⚠️ Нет новостей для фильтрации по {clean_symbol}")
                return []

            # Фильтруем новости
            filtered_news = []

            for news in all_news:
                if not isinstance(news, dict):
                    continue

                # Получаем текстовые поля
                title = news.get("title", "").lower()
                body = news.get("body", news.get("content", "")).lower()
                categories = " ".join(news.get("categories", [])).lower()
                tags = " ".join(news.get("tags", [])).lower()

                # Объединяем все текстовые поля
                text = f"{title} {body} {categories} {tags}"

                # Проверяем наличие хотя бы одного ключевого слова
                matched_keywords = [kw for kw in keywords if kw in text]

                if matched_keywords:
                    # Добавляем metadata
                    news["matched_symbol"] = clean_symbol
                    news["matched_keywords"] = matched_keywords
                    news["relevance_score"] = len(matched_keywords) / len(keywords)

                    filtered_news.append(news)

                # Прекращаем если набрали достаточно
                if len(filtered_news) >= limit * 2:
                    break

            # Сортируем по релевантности и времени
            filtered_news.sort(
                key=lambda x: (x.get("relevance_score", 0), x.get("published_at", 0)),
                reverse=True,
            )

            # Возвращаем топ N
            result = filtered_news[:limit]

            logger.info(
                f"📰 Отфильтровано {len(result)}/{len(all_news)} "
                f"новостей для {clean_symbol}"
            )

            return result

        except Exception as e:
            logger.error(
                f"❌ Ошибка получения новостей для {symbol}: {e}", exc_info=True
            )
            return []

    async def fetch_news_by_category(
        self, category: str = "ALL", limit: int = 50
    ) -> List[Dict]:
        """
        Получить новости по категории

        Args:
            category: 'BTC', 'ETH', 'ALT', 'ALL'
            limit: Количество новостей
        """
        try:
            categories_map = {
                "BTC": ["bitcoin", "btc", "satoshi"],
                "ETH": ["ethereum", "eth", "vitalik", "erc20"],
                "ALT": ["altcoin", "defi", "nft", "doge", "ada", "sol", "bnb"],
            }

            if category == "ALL":
                return await self.get_aggregated_news(limit=limit)

            all_news = await self.get_aggregated_news(limit=limit * 2)

            if category not in categories_map:
                return all_news

            keywords = categories_map[category]
            filtered = []

            for news in all_news:
                title = news.get("title", "").lower()
                body = news.get("body", "").lower()

                if any(kw in title or kw in body for kw in keywords):
                    filtered.append(news)
                    if len(filtered) >= limit:
                        break

            logger.info(f"📰 Категория {category}: {len(filtered)} новостей")
            return filtered

        except Exception as e:
            logger.error(f"❌ Ошибка фильтрации новостей: {e}")
            return []

    async def close(self):
        """Закрытие коннектора"""
        try:
            if self.session and not self.session.closed:
                await self.session.close()
                logger.info("🌐 News connector HTTP сессия закрыта")

        except Exception as e:
            logger.error(f"❌ Ошибка закрытия news connector: {e}")


# Экспорт
__all__ = ["UnifiedNewsConnector", "SmartRateLimiter"]
