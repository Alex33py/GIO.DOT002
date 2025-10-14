# -*- coding: utf-8 -*-
"""
Расширенный коннектор для Bybit API
Обеспечивает подключение к WebSocket и REST API
ИСПРАВЛЕННАЯ ВЕРСИЯ с корректным закрытием WebSocket
"""
import asyncio
import websockets
import aiohttp
import json
import time
import hmac
import hashlib
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque

from config.settings import BYBIT_API_KEY, BYBIT_SECRET_KEY, logger
from config.constants import API_ENDPOINTS, Colors
from core.exceptions import APIConnectionError
from utils.helpers import current_epoch_ms
from utils.rate_limiter import get_rate_limiter, ExponentialBackoff
from utils.cache_manager import get_cache_manager


class EnhancedBybitConnector:
    """Расширенный коннектор для Bybit с поддержкой WebSocket и REST API"""

    def __init__(self):
        """Инициализация коннектора"""
        self.api_key = BYBIT_API_KEY
        self.secret_key = BYBIT_SECRET_KEY
        self.base_url = API_ENDPOINTS["bybit"]["base_url"]

        # HTTP клиент
        self.session = None

        # ИСПРАВЛЕНО: Используем единое имя переменной
        self.websocket_connections = {}
        self.websocket_subscriptions = {}

        self.orderbook_cache = {}
        self.trades_cache = deque(maxlen=1000)
        self.klines_cache = {}
        self.ticker_cache = {}

        # 🚀 БАТЧИНГ: Добавляем кеш для батчинга
        self.candle_cache = {}
        self.cache_ttl = 300  # 5 мин
        self.batch_stats = {
            "total_batches": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "total_time_saved": 0.0,
        }

        # Состояние соединений
        self.connection_health = {
            "status": "disconnected",
            "last_ping": 0,
            "ping_count": 0,
            "error_count": 0,
            "reconnect_attempts": 0,
        }

        # Настройки
        self.ping_interval = 30
        self.reconnect_delay = 5
        self.max_reconnect_attempts = 10

        self.rate_limiter = get_rate_limiter()
        logger.info("✅ Rate Limiter интегрирован в EnhancedBybitConnector")

        self.cache = get_cache_manager()
        logger.info("✅ Cache Manager интегрирован в EnhancedBybitConnector")

        logger.info("✅ EnhancedBybitConnector инициализирован")

    async def initialize(self):
        """Инициализация коннектора"""
        try:
            # Создаём HTTP сессию
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self.session = aiohttp.ClientSession(timeout=timeout)

            # Тестируем подключение
            await self._test_connection()

            self.connection_health["status"] = "connected"
            logger.info("🚀 Bybit коннектор инициализирован успешно")

        except Exception as e:
            self.connection_health["status"] = "error"
            self.connection_health["error_count"] += 1
            logger.error(f"❌ Ошибка инициализации Bybit коннектора: {e}")
            raise APIConnectionError(
                f"Не удалось инициализировать Bybit коннектор: {e}"
            )

    async def _test_connection(self):
        """Тестирование подключения к API"""
        try:
            url = f"{self.base_url}/v5/market/tickers"
            params = {"category": "linear", "symbol": "BTCUSDT"}

            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    raise APIConnectionError(
                        f"API недоступен, статус: {response.status}"
                    )

                data = await response.json()
                if data.get("retCode") != 0:
                    raise APIConnectionError(
                        f"API ошибка: {data.get('retMsg', 'Unknown error')}"
                    )

            logger.info("✅ Подключение к Bybit API успешно")

        except aiohttp.ClientError as e:
            raise APIConnectionError(f"Ошибка HTTP клиента: {e}")

    def _generate_signature(self, params: str, timestamp: str) -> str:
        """Генерация подписи для авторизованных запросов"""
        try:
            message = timestamp + self.api_key + "5000" + params
            return hmac.new(
                self.secret_key.encode("utf-8"), message.encode("utf-8"), hashlib.sha256
            ).hexdigest()
        except Exception as e:
            logger.error(f"Ошибка генерации подписи: {e}")
            return ""

    # ... (все методы получения данных остаются без изменений)
    # _get_orderbook, _get_ticker, _get_recent_trades, _get_klines, _get_funding_rate
    # get_comprehensive_market_data - они работают корректно

    async def get_comprehensive_market_data(self, symbol: str) -> Dict[str, Any]:
        """Получение комплексных рыночных данных"""
        try:
            market_data = {}

            tasks = [
                self._get_orderbook(symbol),
                self._get_ticker(symbol),
                self._get_recent_trades(symbol),
                self._get_klines(symbol, "1", 100),
                self._get_funding_rate(symbol),
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)
            orderbook, ticker, trades, klines, funding = results

            if not isinstance(orderbook, Exception) and orderbook:
                market_data["orderbook"] = orderbook

            if not isinstance(ticker, Exception) and ticker:
                market_data["ticker"] = ticker

            if not isinstance(trades, Exception) and trades:
                market_data["trades"] = trades

            if not isinstance(klines, Exception) and klines:
                market_data["klines"] = klines

            if not isinstance(funding, Exception) and funding:
                market_data["funding_rate"] = funding

            market_data["timestamp"] = current_epoch_ms()
            market_data["symbol"] = symbol
            market_data["source"] = "bybit"

            return market_data

        except Exception as e:
            logger.error(f"Ошибка получения рыночных данных: {e}")
            self.connection_health["error_count"] += 1
            return {}

    async def _get_orderbook(self, symbol: str, limit: int = 50) -> Optional[Dict]:
        """Получение стакана заявок (с Rate Limiting и Cache)"""
        try:
            cache_key = f"{symbol}_{limit}"
            cached_orderbook = await self.cache.get(cache_key, namespace="orderbook")
            if cached_orderbook is not None:
                logger.debug(f"💾 Orderbook {symbol} из кэша")
                return cached_orderbook

            await self.rate_limiter.acquire("bybit_orderbook")
            url = f"{self.base_url}/v5/market/orderbook"
            params = {"category": "linear", "symbol": symbol, "limit": limit}

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("retCode") == 0:
                        result = data.get("result", {})

                        orderbook = {
                            "symbol": result.get("s", symbol),
                            "timestamp": int(result.get("ts", current_epoch_ms())),
                            "bids": [],
                            "asks": [],
                            "mid_price": 0.0,
                            "spread_bps": 0.0,
                        }

                        bids = result.get("b", [])
                        asks = result.get("a", [])

                        for bid in bids:
                            if len(bid) >= 2:
                                orderbook["bids"].append(
                                    {"price": float(bid[0]), "size": float(bid[1])}
                                )

                        for ask in asks:
                            if len(ask) >= 2:
                                orderbook["asks"].append(
                                    {"price": float(ask[0]), "size": float(ask[1])}
                                )

                        if orderbook["bids"] and orderbook["asks"]:
                            best_bid = orderbook["bids"][0]["price"]
                            best_ask = orderbook["asks"][0]["price"]
                            orderbook["mid_price"] = (best_bid + best_ask) / 2
                            orderbook["spread_bps"] = (
                                (best_ask - best_bid) / orderbook["mid_price"]
                            ) * 10000

                            # ✅ СОХРАНЯЕМ В КЭШ (TTL: 3 секунды)
                        await self.cache.set(
                            cache_key, orderbook, ttl=3.0, namespace="orderbook"
                        )

                        self.orderbook_cache[symbol] = orderbook
                        return orderbook

        except Exception as e:
            logger.error(f"Ошибка получения orderbook для {symbol}: {e}")
            return None

    async def _get_ticker(self, symbol: str) -> Optional[Dict]:
        """Получение данных тикера (с Rate Limiting и Cache)"""
        try:
            # ✅ ПРОВЕРЯЕМ КЭШ
            cached_ticker = await self.cache.get(symbol, namespace="ticker")
            if cached_ticker is not None:
                logger.debug(f"💾 Ticker {symbol} из кэша")
                return cached_ticker

            # ✅ RATE LIMITING
            await self.rate_limiter.acquire("bybit_ticker")

            url = f"{self.base_url}/v5/market/tickers"
            params = {"category": "linear", "symbol": symbol}

            # Retry logic
            backoff = ExponentialBackoff(base_delay=1.0, max_delay=10.0)
            max_retries = 3

            for attempt in range(max_retries):
                try:
                    async with self.session.get(url, params=params) as response:
                        # Rate limit check
                        if response.status == 429:
                            logger.warning(
                                f"⚠️ Rate Limit (429) для ticker {symbol}, "
                                f"retry {attempt+1}/{max_retries}"
                            )
                            await backoff.sleep()
                            continue

                        # Успешный ответ
                        if response.status == 200:
                            data = await response.json()
                            if data.get("retCode") == 0 and data.get("result"):
                                result_list = data["result"].get("list", [])
                                if result_list:
                                    ticker_data = result_list[0]

                                    # Форматируем данные тикера
                                    formatted_ticker = {
                                        "symbol": ticker_data.get("symbol"),
                                        "lastPrice": ticker_data.get("lastPrice"),
                                        "price24hPcnt": ticker_data.get("price24hPcnt"),
                                        "volume24h": ticker_data.get("volume24h"),
                                        "highPrice24h": ticker_data.get("highPrice24h"),
                                        "lowPrice24h": ticker_data.get("lowPrice24h"),
                                        "turnover24h": ticker_data.get("turnover24h"),
                                        "openInterest": ticker_data.get("openInterest"),
                                        "fundingRate": ticker_data.get("fundingRate"),
                                    }

                                    # ✅ СОХРАНЯЕМ В КЭШ (TTL: 5 секунд)
                                    await self.cache.set(
                                        symbol,
                                        formatted_ticker,
                                        ttl=5.0,
                                        namespace="ticker",
                                    )

                                    logger.debug(
                                        f"✅ Ticker для {symbol}: "
                                        f"${formatted_ticker.get('lastPrice')} (cached)"
                                    )

                                    return formatted_ticker

                        # Ошибка HTTP - прерываем retry
                        logger.warning(f"⚠️ HTTP {response.status} для ticker {symbol}")
                        break

                except aiohttp.ClientError as e:
                    logger.warning(
                        f"⚠️ HTTP ошибка для ticker {symbol}, "
                        f"retry {attempt+1}/{max_retries}: {e}"
                    )
                    if attempt < max_retries - 1:
                        await backoff.sleep()
                    else:
                        logger.error(f"❌ Все попытки исчерпаны для ticker {symbol}")

                except Exception as e:
                    logger.error(
                        f"❌ Неожиданная ошибка в retry loop для {symbol}: {e}"
                    )
                    break

            # Если дошли сюда - все попытки неудачны
            return None

        except Exception as e:
            logger.error(f"❌ Критическая ошибка получения ticker для {symbol}: {e}")
            return None

    async def _get_klines(
        self, symbol: str, interval: str, limit: int = 200
    ) -> Optional[Dict]:
        """
        Получение свечных данных с ПОЛНОЙ ВАЛИДАЦИЕЙ

        Args:
            symbol: Торговая пара (BTCUSDT)
            interval: Интервал (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M)
            limit: Количество свечей (макс 200)

        Returns:
            Dict с валидированными свечами или None при ошибке
        """
        try:
            url = f"{self.base_url}/v5/market/kline"
            params = {
                "category": "linear",
                "symbol": symbol,
                "interval": interval,
                "limit": limit,
            }

            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.error(f"❌ HTTP ошибка {response.status} для {symbol}")
                    return None

                data = await response.json()

                if data.get("retCode") != 0:
                    logger.error(
                        f"❌ API ошибка для {symbol}: {data.get('retMsg', 'Unknown')}"
                    )
                    return None

                if not data.get("result"):
                    logger.warning(f"⚠️ Нет результата для {symbol}")
                    return None

                klines_list = data["result"].get("list", [])

                # === ВАЛИДАЦИЯ: Проверка что данные есть ===
                if not klines_list or len(klines_list) == 0:
                    logger.warning(f"⚠️ Нет данных свечей для {symbol}")
                    return None

                # === ИНИЦИАЛИЗАЦИЯ ===
                candles = []
                invalid_count = 0

                # === ОБРАБОТКА КАЖДОЙ СВЕЧИ С ВАЛИДАЦИЕЙ ===
                for kline in klines_list:
                    try:
                        # Проверка минимальной длины массива
                        if len(kline) < 6:
                            logger.warning(
                                f"⚠️ Неполная свеча для {symbol}: {len(kline)} полей"
                            )
                            invalid_count += 1
                            continue

                        # === ПАРСИНГ И ВАЛИДАЦИЯ ПОЛЕЙ ===
                        timestamp = int(kline[0])
                        open_price = float(kline[1])
                        high_price = float(kline[2])
                        low_price = float(kline[3])
                        close_price = float(kline[4])
                        volume = float(kline[5])

                        # Проверка на NaN, None, отрицательные/нулевые значения
                        if any(
                            [
                                timestamp is None or timestamp <= 0,
                                open_price is None or open_price <= 0,
                                high_price is None or high_price <= 0,
                                low_price is None or low_price <= 0,
                                close_price is None or close_price <= 0,
                                volume is None or volume < 0,
                            ]
                        ):
                            logger.debug(
                                f"⚠️ Невалидные значения в свече для {symbol}: "
                                f"T={timestamp} O={open_price} H={high_price} "
                                f"L={low_price} C={close_price} V={volume}"
                            )
                            invalid_count += 1
                            continue

                        # === ПРОВЕРКА КОРРЕКТНОСТИ OHLC ===
                        # High должен быть максимальным, Low - минимальным
                        if not (
                            low_price <= open_price <= high_price
                            and low_price <= close_price <= high_price
                        ):
                            logger.warning(
                                f"⚠️ Некорректная OHLC свеча для {symbol}: "
                                f"L={low_price} O={open_price} "
                                f"H={high_price} C={close_price}"
                            )
                            invalid_count += 1
                            continue

                        # === ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: разумные значения ===
                        # Проверяем что цены в разумных пределах (не экстремальные)
                        price_spread = (high_price - low_price) / low_price
                        if price_spread > 0.5:  # Спред больше 50% - подозрительно
                            logger.warning(
                                f"⚠️ Подозрительный спред {price_spread:.1%} для {symbol}"
                            )
                            # Не отбрасываем, но логируем

                        # === ДОБАВЛЯЕМ ВАЛИДНУЮ СВЕЧУ ===
                        candles.append(
                            {
                                "timestamp": timestamp,
                                "open": open_price,
                                "high": high_price,
                                "low": low_price,
                                "close": close_price,
                                "volume": volume,
                            }
                        )

                    except (ValueError, TypeError, IndexError) as e:
                        logger.warning(f"⚠️ Ошибка парсинга свечи для {symbol}: {e}")
                        invalid_count += 1
                        continue
                    except Exception as e:
                        logger.error(
                            f"❌ Неожиданная ошибка парсинга свечи для {symbol}: {e}"
                        )
                        invalid_count += 1
                        continue

                # === ФИНАЛЬНАЯ ВАЛИДАЦИЯ: достаточно ли валидных свечей ===
                if len(candles) < limit * 0.5:  # Минимум 50% от запрошенных
                    logger.error(
                        f"❌ Слишком много невалидных свечей для {symbol}: "
                        f"валидных={len(candles)}, невалидных={invalid_count}, "
                        f"запрошено={limit}"
                    )
                    return None

                # Логируем если были отфильтрованы свечи
                if invalid_count > 0:
                    logger.info(
                        f"ℹ️ Отфильтровано {invalid_count} невалидных свечей "
                        f"для {symbol} (осталось {len(candles)})"
                    )

                # === СОРТИРОВКА ПО TIMESTAMP (от новых к старым) ===
                candles.sort(key=lambda x: x["timestamp"], reverse=True)

                # === ФОРМИРУЕМ РЕЗУЛЬТАТ ===
                klines = {
                    "symbol": symbol,
                    "interval": interval,
                    "candles": candles,
                    "timestamp": current_epoch_ms(),
                    "valid_count": len(candles),
                    "invalid_count": invalid_count,
                    "total_count": len(klines_list),
                }

                # Кэшируем
                cache_key = f"{symbol}_{interval}"
                self.klines_cache[cache_key] = klines

                return klines

        except aiohttp.ClientError as e:
            logger.error(f"❌ HTTP ошибка get_klines для {symbol}: {e}")
            import traceback

            logger.debug(traceback.format_exc())
            return None
        except Exception as e:
            logger.error(f"❌ Критическая ошибка get_klines для {symbol}: {e}")
            import traceback

            logger.error(traceback.format_exc())
            return None

    async def get_klines(
        self, symbol: str, interval: str = "60", limit: int = 100
    ) -> List[Dict]:
        """
        Публичный метод для получения свечей (klines)

        Args:
            symbol: Торговая пара (BTCUSDT)
            interval: Интервал (1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M)
            limit: Количество свечей (макс 200)

        Returns:
            List[Dict] со свечами
        """
        try:
            result = await self._get_klines(symbol, interval, limit)

            if result and "candles" in result:
                return result["candles"]

            return []

        except Exception as e:
            logger.error(f"❌ Ошибка get_klines для {symbol}: {e}")
            import traceback

            logger.debug(traceback.format_exc())
            return []

    async def get_ticker(self, symbol: str) -> Optional[Dict]:
        """
        Публичный метод для получения тикера

        Args:
            symbol: Торговая пара (BTCUSDT)

        Returns:
            Dict с данными тикера
        """
        return await self._get_ticker(symbol)

    async def get_trades(self, symbol: str, limit: int = 1000) -> Optional[List[Dict]]:
        """
        Публичный метод для получения последних сделок

        Args:
            symbol: Торговая пара (BTCUSDT)
            limit: Количество сделок (макс 1000)

        Returns:
            List[Dict] со сделками или None
        """
        try:
            result = await self._get_recent_trades(symbol, limit)

            if result and "trades" in result:
                return result["trades"]

            return None

        except Exception as e:
            logger.error(f"❌ Ошибка get_trades для {symbol}: {e}")
            return None

    async def get_orderbook(self, symbol: str, limit: int = 50) -> Optional[Dict]:
        """
        Получить L2 orderbook (bids/asks) для symbol

        Args:
            symbol: Торговая пара (например, "BTCUSDT")
            limit: Количество уровней (по умолчанию 50)

        Returns:
            {
                "bids": [[price, size], ...],
                "asks": [[price, size], ...],
                "timestamp": 1697040000000
            }
        """
        try:
            # Используем внутренний метод _get_orderbook
            orderbook_data = await self._get_orderbook(symbol, limit)

            if not orderbook_data:
                logger.warning(f"⚠️ Пустой orderbook для {symbol}")
                return None

            # Преобразуем формат из внутреннего в простой
            bids = []
            asks = []

            # Извлекаем bids
            for bid in orderbook_data.get("bids", []):
                if isinstance(bid, dict):
                    bids.append([bid["price"], bid["size"]])
                elif isinstance(bid, list) and len(bid) >= 2:
                    bids.append([float(bid[0]), float(bid[1])])

            # Извлекаем asks
            for ask in orderbook_data.get("asks", []):
                if isinstance(ask, dict):
                    asks.append([ask["price"], ask["size"]])
                elif isinstance(ask, list) and len(ask) >= 2:
                    asks.append([float(ask[0]), float(ask[1])])

            if not bids or not asks:
                logger.warning(f"⚠️ Orderbook пуст для {symbol}")
                return None

            result = {
                "bids": bids,
                "asks": asks,
                "timestamp": orderbook_data.get("timestamp", current_epoch_ms()),
            }

            logger.debug(f"✅ Orderbook {symbol}: {len(bids)} bids, {len(asks)} asks")

            return result

        except Exception as e:
            logger.error(f"❌ get_orderbook error для {symbol}: {e}")
            return None

    async def _get_recent_trades(self, symbol: str, limit: int = 100) -> Optional[Dict]:
        """Получение последних сделок"""
        try:
            url = f"{self.base_url}/v5/market/recent-trade"
            params = {"category": "linear", "symbol": symbol, "limit": limit}

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("retCode") == 0 and data.get("result"):
                        trades_list = data["result"].get("list", [])

                        trades = {
                            "symbol": symbol,
                            "trades": [],
                            "timestamp": current_epoch_ms(),
                        }

                        for trade in trades_list:
                            trades["trades"].append(
                                {
                                    "id": trade.get("execId", ""),
                                    "price": float(trade.get("price", 0)),
                                    "size": float(trade.get("size", 0)),
                                    "side": trade.get("side", "").lower(),
                                    "timestamp": int(
                                        trade.get("time", current_epoch_ms())
                                    ),
                                    "is_block_trade": trade.get("isBlockTrade", False),
                                }
                            )

                        trades["trades"].sort(
                            key=lambda x: x["timestamp"], reverse=True
                        )

                        return trades

        except Exception as e:
            logger.error(f"Ошибка получения trades для {symbol}: {e}")
            return None

    async def _get_funding_rate(self, symbol: str) -> Optional[Dict]:
        """Получение данных по funding rate"""
        try:
            url = f"{self.base_url}/v5/market/funding/history"
            params = {"category": "linear", "symbol": symbol, "limit": 10}

            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("retCode") == 0 and data.get("result"):
                        funding_list = data["result"].get("list", [])

                        if funding_list:
                            latest_funding = funding_list[0]

                            funding_data = {
                                "symbol": latest_funding.get("symbol", symbol),
                                "funding_rate": float(
                                    latest_funding.get("fundingRate", 0)
                                ),
                                "funding_timestamp": int(
                                    latest_funding.get("fundingRateTimestamp", 0)
                                ),
                                "timestamp": current_epoch_ms(),
                            }

                            return funding_data

        except Exception as e:
            logger.error(f"Ошибка получения funding rate для {symbol}: {e}")
            return None

    def get_connection_health(self) -> Dict[str, Any]:
        """Получение состояния здоровья соединений"""
        try:
            current_time = current_epoch_ms()

            if self.connection_health["last_ping"] > 0:
                time_since_last_ping = (
                    current_time - self.connection_health["last_ping"]
                )
                if time_since_last_ping > 60000:
                    self.connection_health["status"] = "stale"

            error_rate = self.connection_health["error_count"] / max(
                1, self.connection_health["ping_count"]
            )
            if error_rate > 0.1:
                self.connection_health["status"] = "unhealthy"

            return {
                "status": self.connection_health["status"],
                "last_ping": self.connection_health["last_ping"],
                "error_count": self.connection_health["error_count"],
                "error_rate": round(error_rate, 3),
                "reconnect_attempts": self.connection_health["reconnect_attempts"],
                "cache_status": {
                    "orderbook_symbols": len(self.orderbook_cache),
                    "trades_count": len(self.trades_cache),
                    "klines_symbols": len(self.klines_cache),
                    "tickers_count": len(self.ticker_cache),
                },
            }

        except Exception as e:
            logger.error(f"Ошибка проверки здоровья соединения: {e}")
            return {"status": "error", "error": str(e)}

    async def get_long_short_ratio(self, symbol: str) -> Optional[Dict]:
        """
        Получить Long/Short Ratio для символа

        Args:
            symbol: Торговая пара (например, "BTCUSDT")

        Returns:
            Dict с данными о соотношении лонгов/шортов:
            {
                "symbol": "BTCUSDT",
                "buy_ratio": 0.6542,      # 65.42% лонгов
                "sell_ratio": 0.3458,     # 34.58% шортов
                "ratio": 1.89,            # 1.89:1 (лонги/шорты)
                "timestamp": "1697040000000"
            }

        API Endpoint: /v5/market/account-ratio
        Docs: https://bybit-exchange.github.io/docs/v5/market/account-ratio
        """
        try:
            url = f"{self.base_url}/v5/market/account-ratio"
            params = {
                "category": "linear",
                "symbol": symbol,
                "period": "5min",  # 5min, 15min, 30min, 1h, 4h, 1d
            }

            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(
                        f"⚠️ HTTP {response.status} для Long/Short Ratio {symbol}"
                    )
                    return None

                data = await response.json()

                if data.get("retCode") != 0:
                    logger.warning(
                        f"⚠️ API ошибка Long/Short Ratio {symbol}: "
                        f"{data.get('retMsg', 'Unknown')}"
                    )
                    return None

                result = data.get("result", {})
                data_list = result.get("list", [])

                if not data_list:
                    logger.warning(f"⚠️ Нет данных Long/Short Ratio для {symbol}")
                    return None

                # Берём самые свежие данные
                latest = data_list[0]

                buy_ratio = float(latest.get("buyRatio", 0))
                sell_ratio = float(latest.get("sellRatio", 0))

                # Рассчитываем соотношение longs/shorts
                if sell_ratio > 0:
                    ratio = buy_ratio / sell_ratio
                else:
                    ratio = buy_ratio  # Если шортов 0, то ratio = buy_ratio

                ls_data = {
                    "symbol": symbol,
                    "buy_ratio": buy_ratio,
                    "sell_ratio": sell_ratio,
                    "ratio": round(ratio, 2),
                    "timestamp": latest.get("timestamp"),
                }

                logger.debug(
                    f"📊 Long/Short Ratio {symbol}: "
                    f"{buy_ratio:.1%} / {sell_ratio:.1%} = {ratio:.2f}"
                )

                return ls_data

        except aiohttp.ClientError as e:
            logger.error(f"❌ HTTP ошибка Long/Short Ratio {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения Long/Short Ratio {symbol}: {e}")
            return None

    async def get_open_interest(self, symbol: str) -> Optional[Dict]:
        """
        Получить Open Interest для символа

        Args:
            symbol: Торговая пара (например, "BTCUSDT")

        Returns:
            Dict с данными об открытом интересе
        """
        try:
            url = f"{self.base_url}/v5/market/open-interest"
            params = {
                "category": "linear",
                "symbol": symbol,
                "intervalTime": "5min",  # 5min, 15min, 30min, 1h, 4h, 1d
            }

            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    logger.warning(
                        f"⚠️ HTTP {response.status} для Open Interest {symbol}"
                    )
                    return None

                data = await response.json()

                if data.get("retCode") != 0:
                    logger.warning(
                        f"⚠️ API ошибка Open Interest {symbol}: "
                        f"{data.get('retMsg', 'Unknown')}"
                    )
                    return None

                result = data.get("result", {})
                data_list = result.get("list", [])

                if not data_list:
                    logger.warning(f"⚠️ Нет данных Open Interest для {symbol}")
                    return None

                # Берём самые свежие данные
                latest = data_list[0]

                oi_data = {
                    "symbol": symbol,
                    "open_interest": float(latest.get("openInterest", 0)),
                    "timestamp": latest.get("timestamp"),
                }

                logger.debug(
                    f"📊 Open Interest {symbol}: " f"{oi_data['open_interest']:,.0f}"
                )

                return oi_data

        except aiohttp.ClientError as e:
            logger.error(f"❌ HTTP ошибка Open Interest {symbol}: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Ошибка получения Open Interest {symbol}: {e}")
            return None

    async def start_websocket_stream(self, symbol: str, streams: List[str]) -> bool:
        """Запуск WebSocket потока для указанного символа"""
        try:
            ws_url = API_ENDPOINTS["bybit"]["websocket"]

            subscriptions = []
            for stream in streams:
                if stream == "orderbook":
                    subscriptions.append(f"orderbook.50.{symbol}")
                elif stream == "trades":
                    subscriptions.append(f"publicTrade.{symbol}")
                elif stream == "klines":
                    subscriptions.append(f"kline.1.{symbol}")

            websocket = await websockets.connect(
                ws_url,
                ping_interval=self.ping_interval,
                ping_timeout=10,
                close_timeout=10,
            )

            subscribe_message = {"op": "subscribe", "args": subscriptions}

            await websocket.send(json.dumps(subscribe_message))

            self.websocket_connections[symbol] = websocket
            self.websocket_subscriptions[symbol] = subscriptions

            asyncio.create_task(self._websocket_handler(symbol, websocket))

            logger.info(f"🔌 WebSocket поток запущен для {symbol}: {streams}")
            return True

        except Exception as e:
            logger.error(f"Ошибка запуска WebSocket потока для {symbol}: {e}")
            return False

    async def _websocket_handler(self, symbol: str, websocket):
        """Обработчик WebSocket сообщений"""
        try:
            async for message in websocket:
                try:
                    data = json.loads(message)

                    self.connection_health["last_ping"] = current_epoch_ms()
                    self.connection_health["ping_count"] += 1

                    if "topic" in data:
                        await self._process_websocket_data(symbol, data)

                except json.JSONDecodeError as e:
                    logger.error(f"Ошибка парсинга WebSocket сообщения: {e}")
                except Exception as e:
                    logger.error(f"Ошибка обработки WebSocket сообщения: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.warning(f"WebSocket соединение закрыто для {symbol}")
            await self._reconnect_websocket(symbol)
        except Exception as e:
            logger.error(f"Критическая ошибка WebSocket для {symbol}: {e}")
            self.connection_health["error_count"] += 1

    async def _process_websocket_data(self, symbol: str, data: Dict):
        """Обработка данных от WebSocket"""
        try:
            topic = data.get("topic", "")

            if "orderbook" in topic:
                await self._process_orderbook_update(symbol, data)
            elif "publicTrade" in topic:
                await self._process_trades_update(symbol, data)
            elif "kline" in topic:
                await self._process_klines_update(symbol, data)

        except Exception as e:
            logger.error(f"Ошибка обработки WebSocket данных: {e}")

    async def _process_orderbook_update(self, symbol: str, data: Dict):
        """Обработка обновления стакана заявок"""
        try:
            if "data" in data:
                orderbook_data = data["data"]

                if symbol in self.orderbook_cache:
                    orderbook = self.orderbook_cache[symbol]

                    if "b" in orderbook_data:
                        orderbook["bids"] = [
                            {"price": float(bid[0]), "size": float(bid[1])}
                            for bid in orderbook_data["b"]
                        ]

                    if "a" in orderbook_data:
                        orderbook["asks"] = [
                            {"price": float(ask[0]), "size": float(ask[1])}
                            for ask in orderbook_data["a"]
                        ]

                    if orderbook["bids"] and orderbook["asks"]:
                        best_bid = orderbook["bids"][0]["price"]
                        best_ask = orderbook["asks"][0]["price"]
                        orderbook["mid_price"] = (best_bid + best_ask) / 2
                        orderbook["spread_bps"] = (
                            (best_ask - best_bid) / orderbook["mid_price"]
                        ) * 10000

                    orderbook["timestamp"] = current_epoch_ms()

        except Exception as e:
            logger.error(f"Ошибка обработки orderbook update: {e}")

    async def _process_trades_update(self, symbol: str, data: Dict):
        """Обработка обновления сделок"""
        try:
            if "data" in data:
                for trade_data in data["data"]:
                    trade = {
                        "id": trade_data.get("i", ""),
                        "price": float(trade_data.get("p", 0)),
                        "size": float(trade_data.get("v", 0)),
                        "side": trade_data.get("S", "").lower(),
                        "timestamp": int(trade_data.get("T", current_epoch_ms())),
                        "symbol": symbol,
                        "exchange": "bybit",
                    }

                    self.trades_cache.append(trade)

        except Exception as e:
            logger.error(f"Ошибка обработки trades update: {e}")

    async def _process_klines_update(self, symbol: str, data: Dict):
        """Обработка обновления свечей"""
        try:
            if "data" in data:
                for kline_data in data["data"]:
                    kline = {
                        "timestamp": int(kline_data.get("start", current_epoch_ms())),
                        "open": float(kline_data.get("open", 0)),
                        "high": float(kline_data.get("high", 0)),
                        "low": float(kline_data.get("low", 0)),
                        "close": float(kline_data.get("close", 0)),
                        "volume": float(kline_data.get("volume", 0)),
                        "confirm": kline_data.get("confirm", False),
                    }

                    cache_key = f"{symbol}_1"
                    if cache_key in self.klines_cache:
                        klines = self.klines_cache[cache_key]

                        if kline["confirm"]:
                            updated = False
                            for i, existing_kline in enumerate(klines["candles"]):
                                if existing_kline["timestamp"] == kline["timestamp"]:
                                    klines["candles"][i] = kline
                                    updated = True
                                    break

                            if not updated:
                                klines["candles"].insert(0, kline)
                                if len(klines["candles"]) > 1000:
                                    klines["candles"] = klines["candles"][:1000]

        except Exception as e:
            logger.error(f"Ошибка обработки klines update: {e}")

    async def _reconnect_websocket(self, symbol: str):
        """Переподключение WebSocket"""
        try:
            if (
                self.connection_health["reconnect_attempts"]
                >= self.max_reconnect_attempts
            ):
                logger.error(
                    f"Достигнуто максимальное количество попыток переподключения для {symbol}"
                )
                return

            self.connection_health["reconnect_attempts"] += 1
            logger.info(
                f"🔄 Переподключение WebSocket для {symbol} (попытка {self.connection_health['reconnect_attempts']})"
            )

            await asyncio.sleep(self.reconnect_delay)

            subscriptions = self.websocket_subscriptions.get(symbol, [])
            if subscriptions:
                streams = []
                for sub in subscriptions:
                    if "orderbook" in sub:
                        streams.append("orderbook")
                    elif "publicTrade" in sub:
                        streams.append("trades")
                    elif "kline" in sub:
                        streams.append("klines")

                success = await self.start_websocket_stream(symbol, streams)
                if success:
                    self.connection_health["reconnect_attempts"] = 0
                    logger.info(f"✅ WebSocket успешно переподключен для {symbol}")

        except Exception as e:
            logger.error(f"Ошибка переподключения WebSocket: {e}")

    # БАТЧИНГ: Новые методы

    async def get_klines_batch(
        self, symbol: str, timeframes: list, limits: list = None, use_cache: bool = True
    ) -> dict:
        """
        🚀 БАТЧИНГ: Получение нескольких таймфреймов параллельно

        Args:
            symbol: Торговая пара (BTCUSDT)
            timeframes: Список таймфреймов ['60', '240', 'D']
            limits: Список лимитов [100, 50, 30]
            use_cache: Использовать кеш

        Returns:
            {
                '60': [candles_1h],
                '240': [candles_4h],
                'D': [candles_1d]
            }
        """
        if limits is None:
            limits = [100] * len(timeframes)

        self.batch_stats["total_batches"] += 1
        batch_start = time.time()

        batch_result = {}
        tasks_to_fetch = []
        cache_keys_to_fetch = []
        timeframes_to_fetch = []

        current_time = time.time()

        # Проверяем кеш для каждого таймфрейма
        for tf, limit in zip(timeframes, limits):
            cache_key = f"{symbol}_{tf}_{limit}"

            if use_cache and cache_key in self.candle_cache:
                cached_data, cached_time = self.candle_cache[cache_key]

                # Кеш валидный?
                if current_time - cached_time < self.cache_ttl:
                    logger.debug(f"💾 Cache HIT: {cache_key}")
                    self.batch_stats["cache_hits"] += 1
                    batch_result[tf] = cached_data
                    continue

            # Cache MISS - добавляем в очередь загрузки
            logger.debug(f"🔄 Cache MISS: {cache_key}")
            self.batch_stats["cache_misses"] += 1
            task = self.get_klines(symbol, tf, limit)
            tasks_to_fetch.append(task)
            cache_keys_to_fetch.append(cache_key)
            timeframes_to_fetch.append(tf)

        # Загружаем только те таймфреймы, которых нет в кеше
        if tasks_to_fetch:
            logger.info(
                f"📊 Загружаем {len(tasks_to_fetch)} таймфреймов для {symbol}..."
            )

            results = await asyncio.gather(*tasks_to_fetch, return_exceptions=True)

            # Сохраняем результаты в кеш
            for cache_key, tf, result in zip(
                cache_keys_to_fetch, timeframes_to_fetch, results
            ):
                if isinstance(result, Exception):
                    logger.error(f"❌ Ошибка загрузки {tf}: {result}")
                    batch_result[tf] = []
                else:
                    self.candle_cache[cache_key] = (result, current_time)
                    batch_result[tf] = result
                    logger.debug(f"✅ {tf}: {len(result)} свечей загружено")

        batch_time = time.time() - batch_start

        # Считаем сэкономленное время
        if len(batch_result) > 1:
            sequential_time = len(batch_result) * 0.15
            time_saved = sequential_time - batch_time
            self.batch_stats["total_time_saved"] += time_saved

            logger.info(
                f"⚡ Batch {symbol}: {len(batch_result)} таймфреймов за {batch_time:.3f}s "
                f"(сэкономлено {time_saved:.3f}s)"
            )

        return batch_result

    def get_batch_stats(self) -> dict:
        """Получить статистику батчинга"""
        return {
            **self.batch_stats,
            "cache_hit_rate": (
                self.batch_stats["cache_hits"]
                / (self.batch_stats["cache_hits"] + self.batch_stats["cache_misses"])
                if (self.batch_stats["cache_hits"] + self.batch_stats["cache_misses"])
                > 0
                else 0.0
            ),
        }

    def clear_cache(self):
        """Очистить кеш свечей"""
        self.candle_cache.clear()
        logger.info("🗑️ Кеш свечей очищен")

    async def close(self):
        """
        Закрытие всех соединений
        ИСПРАВЛЕНО: Корректная обработка закрытия WebSocket без проверки .closed
        """
        try:
            logger.info("🔄 Закрытие Bybit коннектора...")

            # ИСПРАВЛЕНО: Закрываем WebSocket соединения безопасно
            symbols_to_close = list(
                self.websocket_connections.keys()
            )  # Копия для безопасной итерации

            for symbol in symbols_to_close:
                websocket = self.websocket_connections.get(symbol)

                if websocket is None:
                    continue

                try:
                    # ИСПРАВЛЕНО: Просто пытаемся закрыть без проверки .closed
                    # Библиотека websockets корректно обработает если уже закрыто
                    await websocket.close(code=1000, reason="Normal shutdown")
                    logger.debug(f"🔌 WebSocket закрыт для {symbol}")

                except websockets.exceptions.ConnectionClosed:
                    # Соединение уже закрыто - это нормально
                    logger.debug(f"ℹ️ WebSocket для {symbol} уже был закрыт")

                except AttributeError as e:
                    # Если объект не имеет метода close (не должно происходить)
                    logger.debug(f"⚠️ WebSocket для {symbol} не имеет метода close: {e}")

                except Exception as e:
                    # Любые другие ошибки логируем как warning, но не падаем
                    logger.warning(f"⚠️ Ошибка при закрытии WebSocket для {symbol}: {e}")

                finally:
                    # В любом случае удаляем из словаря
                    if symbol in self.websocket_connections:
                        del self.websocket_connections[symbol]
                    if symbol in self.websocket_subscriptions:
                        del self.websocket_subscriptions[symbol]

            # Закрываем HTTP сессию
            if self.session is not None:
                try:
                    if not self.session.closed:
                        await self.session.close()
                        logger.info("🌐 HTTP сессия закрыта")
                    else:
                        logger.debug("ℹ️ HTTP сессия уже была закрыта")
                except Exception as e:
                    logger.warning(f"⚠️ Ошибка при закрытии HTTP сессии: {e}")

            self.connection_health["status"] = "disconnected"
            logger.info("✅ Bybit коннектор закрыт")

        except Exception as e:
            logger.error(f"❌ Критическая ошибка закрытия коннектора: {e}")

    def get_cache_stats(self) -> Dict:
        """
        Получить статистику кэша

        Returns:
            Dict со статистикой кэша
        """
        return self.cache.get_stats()

    def get_detailed_cache_stats(self) -> Dict:
        """
        Получить детальную статистику кэша

        Returns:
            Dict с подробной статистикой кэша
        """
        return self.cache.get_detailed_stats()

        # Не бросаем исключение, чтобы shutdown мог продолжиться

    def get_cache_statistics(self) -> Dict:
        """
        Получить статистику кэша

        Returns:
            Dict со статистикой кэша
        """
        if hasattr(self, "cache") and self.cache:
            return self.cache.get_statistics()
        return {"hit_rate": 0.0, "total_items": 0, "total_size_mb": 0.0}

    def get_rate_limiter_stats(self) -> Dict:
        """
        Получить статистику использования API (Rate Limiter)

        Returns:
            Dict со статистикой для всех endpoints
        """
        return self.rate_limiter.get_all_stats()

    def get_rate_limiter_stats(self) -> Dict:
        """
        Получить статистику использования API (Rate Limiter)

        Returns:
            Dict со статистикой для всех endpoints
        """
        return self.rate_limiter.get_all_stats()
