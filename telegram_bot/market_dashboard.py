#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Market Dashboard - главный дашборд рынка (альтернатива Coinglass)
Показывает всю информацию о символе в одном экране
"""

from typing import Dict, Optional
from datetime import datetime
import requests  # ← НОВЫЙ ИМПОРТ для Funding Rate API
from config.settings import logger
from telegram_bot.dashboard_helpers import DashboardFormatter


class MarketDashboard:
    """
    Главный дашборд рынка

    Показывает в одном экране:
    - Цену и 24h изменение
    - Фазу рынка (Accumulation/Distribution/Markup)
    - Активный сценарий ММ с confidence
    - Volume Analysis (24h vol, spike, CVD, VP)
    - Sentiment & Pressure (Funding, OI, L/S Ratio, Orderbook)
    - Multi-Timeframe тренды (1h/4h/1d)
    - Key Levels (Support/Resistance)
    """

    def __init__(self, bot_instance):
        """
        Args:
            bot_instance: Экземпляр GIOCryptoBot для доступа к данным
        """
        self.bot = bot_instance
        self.formatter = DashboardFormatter()
        logger.info("✅ MarketDashboard инициализирован")

    async def generate_dashboard(self, symbol: str) -> str:
        """
        Генерирует полный дашборд для символа

        Args:
            symbol: Торговая пара (например, "BTCUSDT")

        Returns:
            Форматированный текст дашборда для Telegram
        """
        try:
            logger.info(f"📊 Генерация dashboard для {symbol}...")

            # ========== 1. СБОР ВСЕХ ДАННЫХ ==========

            # 1.1. Ticker (цена, объём, 24h change)
            ticker = await self._get_ticker(symbol)
            if not ticker or ticker["price"] == 0:
                return f"❌ Не удалось получить данные для {symbol}"

            # 1.2. Market Regime (фаза рынка)
            regime = await self._get_market_regime(symbol, ticker)

            # 1.3. MM Scenario (сценарий маркетмейкеров)
            scenario = await self._get_mm_scenario(symbol, ticker)

            # 1.4. Volume Analysis
            volume_data = await self._get_volume_analysis(symbol, ticker)

            # 1.5. Sentiment & Pressure
            sentiment_data = await self._get_sentiment_pressure(symbol)

            # 1.6. Multi-Timeframe Trends
            mtf_trends = await self._get_mtf_trends(symbol)

            # 1.7. Key Levels
            levels = await self._get_key_levels(symbol, volume_data)

            # 1.8. Whale Activity (5 минут)
            whale_activity = await self._get_whale_activity(symbol)

            # 1.9. Liquidation Levels
            liquidation_levels = await self._get_liquidation_levels(symbol, ticker)

            # ========== 2. ФОРМАТИРОВАНИЕ ДАШБОРДА ==========

            dashboard_text = self._format_dashboard(
                symbol=symbol,
                ticker=ticker,
                regime=regime,
                scenario=scenario,
                volume_data=volume_data,
                sentiment_data=sentiment_data,
                mtf_trends=mtf_trends,
                levels=levels,
                whale_activity=whale_activity,
                liquidation_levels=liquidation_levels,
            )

            logger.info(f"✅ Dashboard для {symbol} сгенерирован")
            return dashboard_text

        except Exception as e:
            logger.error(
                f"❌ Ошибка генерации dashboard для {symbol}: {e}", exc_info=True
            )
            return f"❌ Ошибка генерации dashboard: {e}"

    async def _get_ticker(self, symbol: str) -> Dict:
        """Получение базовых данных тикера"""
        try:
            ticker_raw = await self.bot.bybit_connector.get_ticker(symbol)

            if not ticker_raw:
                logger.warning(f"⚠️ Ticker data unavailable for {symbol}")
                return {
                    "price": 0.0,
                    "change_24h": 0.0,
                    "high_24h": 0.0,
                    "low_24h": 0.0,
                    "volume_24h": 0.0,
                }

            # Извлекаем цену из различных форматов ответа Bybit
            price = float(
                ticker_raw.get("lastPrice")
                or ticker_raw.get("last_price")
                or ticker_raw.get("last")
                or 0
            )

            # Процентное изменение за 24ч
            change_str = (
                ticker_raw.get("price24hPcnt")
                or ticker_raw.get("price_24h_pcnt")
                or "0"
            )
            change_24h = float(change_str) * 100 if change_str else 0.0

            # High/Low/Volume
            high_24h = float(
                ticker_raw.get("highPrice24h")
                or ticker_raw.get("high_24h")
                or ticker_raw.get("high")
                or 0
            )
            low_24h = float(
                ticker_raw.get("lowPrice24h")
                or ticker_raw.get("low_24h")
                or ticker_raw.get("low")
                or 0
            )
            volume_24h = float(
                ticker_raw.get("volume24h")
                or ticker_raw.get("volume_24h")
                or ticker_raw.get("volume")
                or 0
            )

            logger.debug(
                f"✅ Ticker {symbol}: Price=${price:,.2f}, Change={change_24h:+.2f}%"
            )

            return {
                "price": price,
                "change_24h": change_24h,
                "high_24h": high_24h,
                "low_24h": low_24h,
                "volume_24h": volume_24h,
            }

        except Exception as e:
            logger.error(f"❌ Ошибка получения ticker {symbol}: {e}")
            return {
                "price": 0.0,
                "change_24h": 0.0,
                "high_24h": 0.0,
                "low_24h": 0.0,
                "volume_24h": 0.0,
            }

    async def _get_market_regime(self, symbol: str, ticker: Dict) -> Dict:
        """Получить Market Regime (рыночный режим) - КРИТЕРИЙ 2"""
        try:
            # Используем MarketRegimeDetector
            if hasattr(self.bot, "market_regime_detector"):
                # Подготавливаем market_data
                market_data = {
                    "symbol": symbol,
                    "price": ticker["price"],
                    "volume": ticker["volume_24h"],
                    "high_24h": ticker["high_24h"],
                    "low_24h": ticker["low_24h"],
                }

                regime_result = self.bot.market_regime_detector.detect_regime(market_data)
                return {
                    "regime": regime_result.get("regime", "NEUTRAL"),  # ← UPPERCASE
                    "confidence": regime_result.get("confidence", 0.5),
                    "description": regime_result.get("description", ""),
                }

            # Fallback
            return {
                "regime": "RANGING",
                "confidence": 0.5,
                "description": "Боковое движение в определённом диапазоне",
            }
        except Exception as e:
            logger.error(f"❌ Ошибка _get_market_regime: {e}", exc_info=True)
            return {
                "regime": "NEUTRAL",
                "confidence": 0.5,
                "description": "Смешанные сигналы",
            }


    async def _get_mm_scenario(self, symbol: str, ticker: Dict) -> Dict:
        """Получить сценарий ММ с умным fallback"""
        try:
            # Получаем MTF тренды для более точного matching
            mtf_trends = await self._get_mtf_trends(symbol)

            # Используем EnhancedScenarioMatcher
            if hasattr(self.bot, "enhanced_scenario_matcher"):
                # Подготавливаем данные для match_scenario
                market_data = {
                    "symbol": symbol,
                    "price": ticker["price"],
                    "volume": ticker["volume_24h"],
                    "change_24h": ticker["change_24h"],
                }

                scenario = self.bot.enhanced_scenario_matcher.match_scenario(
                    symbol=symbol,
                    market_data=market_data,
                    indicators={},
                    mtf_trends=mtf_trends,
                    volume_profile={},
                    news_sentiment={},
                    veto_checks={},
                )

                if (
                    scenario and scenario.get("score", 0) > 30
                ):  # Понижаем порог с 50% до 30%
                    return {
                        "scenario_id": scenario.get("scenario_id", "unknown"),
                        "scenario_name": scenario.get("scenario_name", "Unknown"),
                        "confidence": scenario.get("score", 0) / 100,
                        "description": scenario.get("description", ""),
                    }

            # УМНЫЙ FALLBACK: Генерируем базовый сценарий на основе MTF
            return self._generate_fallback_scenario(ticker, mtf_trends)

        except Exception as e:
            logger.error(f"❌ Ошибка _get_mm_scenario: {e}")
            return {
                "scenario_id": "error",
                "scenario_name": "Market Analysis",
                "confidence": 0.5,
                "description": "Basic market analysis",
            }

    def _generate_fallback_scenario(self, ticker: Dict, mtf_trends: Dict) -> Dict:
        """Генерирует базовый сценарий на основе цены и MTF"""
        change_24h = ticker["change_24h"]

        # Определяем тренд
        trend_1h = mtf_trends.get("1h", "NEUTRAL")
        trend_4h = mtf_trends.get("4h", "NEUTRAL")
        trend_1d = mtf_trends.get("1d", "NEUTRAL")

        # Логика fallback сценария
        if abs(change_24h) < 1:
            # Рынок в боковике
            scenario_name = "Range Trading"
            scenario_id = "range_consolidation"
            confidence = 0.65
        elif change_24h > 3:
            # Сильный рост
            if trend_1h == "UP" and trend_4h == "UP":
                scenario_name = "Strong Uptrend"
                scenario_id = "uptrend_momentum"
                confidence = 0.75
            else:
                scenario_name = "Recovery Rally"
                scenario_id = "bullish_recovery"
                confidence = 0.60
        elif change_24h < -3:
            # Сильное падение
            if trend_1h == "DOWN" and trend_4h == "DOWN":
                scenario_name = "Strong Downtrend"
                scenario_id = "downtrend_momentum"
                confidence = 0.75
            else:
                scenario_name = "Correction Phase"
                scenario_id = "bearish_correction"
                confidence = 0.60
        else:
            # Слабое движение
            scenario_name = "Consolidation"
            scenario_id = "neutral_consolidation"
            confidence = 0.55

        return {
            "scenario_id": scenario_id,
            "scenario_name": scenario_name,
            "confidence": confidence,
            "description": f"Market showing {scenario_name.lower()} pattern",
        }

    async def _get_volume_analysis(self, symbol: str, ticker: Dict) -> Dict:
        """Получить анализ объёмов"""
        try:
            volume_24h = ticker["volume_24h"]

            # CVD - комбинированный подход (L2 imbalance + Binance orderbook)
            cvd_value = 0.0
            cvd_label = "⚪ Neutral"

            try:
                # Метод 1: L2 imbalance из market_data
                if hasattr(self.bot, "market_data") and symbol in self.bot.market_data:
                    l2_data = self.bot.market_data[symbol].get("l2_imbalance", {})
                    if l2_data:
                        cvd_value = l2_data.get("imbalance_percent", 0.0)

                # Метод 2: Если L2 = 0, используем Binance orderbook
                if cvd_value == 0.0 and hasattr(self.bot, "binance_connector"):
                    try:
                        ob = await self.bot.binance_connector.get_orderbook(
                            symbol, limit=100
                        )
                        if ob and "bids" in ob and "asks" in ob:
                            bids_volume = sum([float(b[1]) for b in ob["bids"][:50]])
                            asks_volume = sum([float(a[1]) for a in ob["asks"][:50]])

                            total_volume = bids_volume + asks_volume
                            if total_volume > 0:
                                cvd_value = (
                                    (bids_volume - asks_volume) / total_volume
                                ) * 100
                                logger.debug(
                                    f"✅ CVD {symbol} (Binance OB): {cvd_value:+.2f}%"
                                )
                    except Exception as e:
                        logger.debug(f"⚠️ Binance orderbook недоступен: {e}")

                # Классификация CVD
                if cvd_value > 10:
                    cvd_label = "🔥 Extreme BUY"
                elif cvd_value > 5:
                    cvd_label = "🟢 Strong BUY"
                elif cvd_value > 1:
                    cvd_label = "🟢 BUY"
                elif cvd_value < -10:
                    cvd_label = "❄️ Extreme SELL"
                elif cvd_value < -5:
                    cvd_label = "🔴 Strong SELL"
                elif cvd_value < -1:
                    cvd_label = "🔴 SELL"
                else:
                    cvd_label = "⚪ Neutral"

            except Exception as e:
                logger.error(f"❌ Ошибка CVD для {symbol}: {e}")

            # Volume Profile
            vp_poc = 0
            vp_vah = 0
            vp_val = 0

            try:
                if hasattr(self.bot, "get_volume_profile"):
                    vp = self.bot.get_volume_profile(symbol)
                    if vp:
                        vp_poc = vp.get("poc", 0)
                        vp_vah = vp.get("vah", 0)
                        vp_val = vp.get("val", 0)
            except Exception as e:
                logger.debug(f"⚠️ Volume Profile недоступен: {e}")

            # Fallback для VP - используем текущую цену
            if vp_poc == 0:
                current_price = ticker["price"]
                vp_poc = current_price
                vp_vah = current_price * 1.02
                vp_val = current_price * 0.98

            return {
                "volume_24h": volume_24h,
                "cvd": cvd_value,
                "cvd_label": cvd_label,
                "volume_profile": {"poc": vp_poc, "vah": vp_vah, "val": vp_val},
            }
        except Exception as e:
            logger.error(f"❌ Ошибка _get_volume_analysis: {e}")
            return {
                "volume_24h": 0,
                "cvd": 0,
                "cvd_label": "⚪ Neutral",
                "volume_profile": {"poc": 0, "vah": 0, "val": 0},
            }

    async def _get_sentiment_pressure(self, symbol: str) -> Dict:
        """Получить sentiment и давление рынка"""
        try:
            # Funding Rate - используем публичный REST API
            funding_rate = 0.0
            funding_label = "⚪ Neutral"

            try:
                response = requests.get(
                    f"https://api.bybit.com/v5/market/funding/history",
                    params={"category": "linear", "symbol": symbol, "limit": 1},
                    timeout=3,
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("retCode") == 0:
                        result = data.get("result", {}).get("list", [])
                        if result:
                            funding_rate = float(result[0].get("fundingRate", 0)) * 100

                            if funding_rate > 0.03:
                                funding_label = "🔥 Very Bullish"
                            elif funding_rate > 0.01:
                                funding_label = "🟢 Bullish"
                            elif funding_rate < -0.03:
                                funding_label = "❄️ Very Bearish"
                            elif funding_rate < -0.01:
                                funding_label = "🔴 Bearish"
                            else:
                                funding_label = "⚪ Neutral"
            except Exception as e:
                logger.debug(f"⚠️ Funding недоступен: {e}")

            # Open Interest - используем REST API напрямую
            open_interest = 0.0
            try:
                response = requests.get(
                    "https://api.bybit.com/v5/market/open-interest",
                    params={
                        "category": "linear",
                        "symbol": symbol,
                        "intervalTime": "5min",
                        "limit": 1,
                    },
                    timeout=3,
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("retCode") == 0:
                        result = data.get("result", {}).get("list", [])
                        if result:
                            open_interest = float(result[0].get("openInterest", 0))
                            logger.debug(f"✅ OI {symbol}: ${open_interest:,.0f}")
            except Exception as e:
                logger.debug(f"⚠️ OI недоступен: {e}")

            # Long/Short Ratio
            long_short_ratio = 0.0
            ls_label = "⚪ Neutral"

            try:
                ls_ratio_data = await self.bot.bybit_connector.get_long_short_ratio(
                    symbol
                )
                if ls_ratio_data:
                    long_short_ratio = ls_ratio_data.get("ratio", 0.0)

                    if long_short_ratio > 3:
                        ls_label = "🔥 Very Bullish"
                    elif long_short_ratio > 1.5:
                        ls_label = "🟢 Bullish"
                    elif long_short_ratio < 0.5:
                        ls_label = "❄️ Very Bearish"
                    elif long_short_ratio < 0.8:
                        ls_label = "🔴 Bearish"
                    else:
                        ls_label = "⚪ Neutral"
            except Exception as e:
                logger.debug(f"⚠️ Long/Short Ratio недоступен: {e}")

            # News Sentiment
            news_sentiment = "neutral"
            news_label = "⚪ Neutral"

            if hasattr(self.bot, "enhanced_sentiment"):
                try:
                    news_data = self.bot.enhanced_sentiment.get_symbol_sentiment(symbol)
                    if news_data:
                        news_sentiment = news_data.get("sentiment", "neutral")
                        if news_sentiment.lower() == "positive":
                            news_label = "🟢 Bullish"
                        elif news_sentiment.lower() == "negative":
                            news_label = "🔴 Bearish"
                except Exception as e:
                    logger.debug(f"⚠️ News sentiment недоступен: {e}")

            return {
                "funding_rate": funding_rate,
                "funding_label": funding_label,
                "open_interest": open_interest,
                "long_short_ratio": long_short_ratio,
                "ls_label": ls_label,
                "news_sentiment": news_sentiment,
                "news_label": news_label,
            }
        except Exception as e:
            logger.error(f"❌ Ошибка _get_sentiment_pressure: {e}")
            return {
                "funding_rate": 0,
                "funding_label": "⚪ Neutral",
                "open_interest": 0,
                "long_short_ratio": 0,
                "ls_label": "⚪ Neutral",
                "news_sentiment": "neutral",
                "news_label": "⚪ Neutral",
            }

    async def _get_whale_activity(self, symbol: str) -> Dict:
        """Получить активность крупных игроков за последние 5 минут"""
        import time

        try:
            whale_trades = {
                "count": 0,
                "buy_volume": 0.0,
                "sell_volume": 0.0,
                "net_volume": 0.0,
                "largest_trade": 0.0,
                "label": "⚪ Neutral",
            }

            # Получаем large trades из bot
            if hasattr(self.bot, "large_trades_cache"):
                current_time = time.time()
                recent_trades = []

                # Фильтруем trades за последние 5 минут
                for trade in self.bot.large_trades_cache.get(symbol, []):
                    if current_time - trade.get("timestamp", 0) < 300:  # 5 минут
                        recent_trades.append(trade)

                # Подсчитываем статистику
                for trade in recent_trades:
                    volume = trade.get("volume", 0)
                    side = trade.get("side", "buy")

                    whale_trades["count"] += 1

                    if side == "buy":
                        whale_trades["buy_volume"] += volume
                    else:
                        whale_trades["sell_volume"] += volume

                    if volume > whale_trades["largest_trade"]:
                        whale_trades["largest_trade"] = volume

                # Рассчитываем net volume
                whale_trades["net_volume"] = (
                    whale_trades["buy_volume"] - whale_trades["sell_volume"]
                )
                total_volume = whale_trades["buy_volume"] + whale_trades["sell_volume"]

                # Классификация
                if total_volume > 0:
                    net_percent = (whale_trades["net_volume"] / total_volume) * 100

                    if net_percent > 50:
                        whale_trades["label"] = "🐋 Strong BUY"
                    elif net_percent > 20:
                        whale_trades["label"] = "🐋 BUY"
                    elif net_percent < -50:
                        whale_trades["label"] = "🦈 Strong SELL"
                    elif net_percent < -20:
                        whale_trades["label"] = "🦈 SELL"
                    else:
                        whale_trades["label"] = "⚪ Balanced"

                logger.debug(
                    f"✅ Whale activity {symbol}: {whale_trades['count']} trades, net={whale_trades['net_volume']:,.2f}"
                )

            return whale_trades

        except Exception as e:
            logger.error(f"❌ Ошибка whale activity: {e}")
            return {
                "count": 0,
                "buy_volume": 0.0,
                "sell_volume": 0.0,
                "net_volume": 0.0,
                "largest_trade": 0.0,
                "label": "⚪ Neutral",
            }

    async def _get_liquidation_levels(self, symbol: str, ticker: Dict) -> Dict:
        """Получить уровни ликвидаций"""
        try:
            current_price = ticker["price"]

            liquidation_data = {
                "long_liq_level": current_price * 0.95,  # -5% от текущей цены
                "short_liq_level": current_price * 1.05,  # +5% от текущей цены
                "long_liq_volume": 0.0,
                "short_liq_volume": 0.0,
                "risk_level": "⚪ Low",
            }

            # Получаем данные ликвидаций через REST API
            try:
                response = requests.get(
                    "https://fapi.binance.com/futures/data/openInterestHist",
                    params={
                        "symbol": symbol.replace("USDT", ""),
                        "period": "5m",
                        "limit": 1,
                    },
                    timeout=3,
                )

                if response.status_code == 200:
                    data = response.json()
                    if data:
                        # Оцениваем риск ликвидаций на основе OI
                        oi_value = float(data[0].get("sumOpenInterest", 0))

                        # Примерная оценка объёмов ликвидаций
                        liquidation_data["long_liq_volume"] = (
                            oi_value * 0.3
                        )  # 30% длинных позиций
                        liquidation_data["short_liq_volume"] = (
                            oi_value * 0.2
                        )  # 20% коротких позиций

                        # Оценка риска
                        total_liq = (
                            liquidation_data["long_liq_volume"]
                            + liquidation_data["short_liq_volume"]
                        )

                        if total_liq > 100000000:  # > $100M
                            liquidation_data["risk_level"] = "🔴 High"
                        elif total_liq > 50000000:  # > $50M
                            liquidation_data["risk_level"] = "🟡 Medium"
                        else:
                            liquidation_data["risk_level"] = "⚪ Low"

                        logger.debug(
                            f"✅ Liquidation levels {symbol}: Long ${liquidation_data['long_liq_level']:,.0f}, Short ${liquidation_data['short_liq_level']:,.0f}"
                        )

            except Exception as e:
                logger.debug(f"⚠️ Liquidation data недоступна: {e}")

            return liquidation_data

        except Exception as e:
            logger.error(f"❌ Ошибка liquidation levels: {e}")
            return {
                "long_liq_level": 0,
                "short_liq_level": 0,
                "long_liq_volume": 0,
                "short_liq_volume": 0,
                "risk_level": "⚪ Low",
            }

    async def _get_mtf_trends(self, symbol: str) -> Dict:
        """Получить Multi-Timeframe тренды"""
        try:
            if hasattr(self.bot, "multi_tf_filter"):
                # Получаем тренды из MTF Filter
                mtf_data = await self.bot.multi_tf_filter._get_mtf_data(
                    symbol, ["1h", "4h", "1d"]
                )

                if mtf_data:
                    return {
                        "1h": mtf_data.get("1h", {}).get("trend", "NEUTRAL"),
                        "4h": mtf_data.get("4h", {}).get("trend", "NEUTRAL"),
                        "1d": mtf_data.get("1d", {}).get("trend", "NEUTRAL"),
                    }

            # Fallback
            return {"1h": "NEUTRAL", "4h": "NEUTRAL", "1d": "NEUTRAL"}
        except Exception as e:
            logger.error(f"❌ Ошибка _get_mtf_trends: {e}")
            return {"1h": "NEUTRAL", "4h": "NEUTRAL", "1d": "NEUTRAL"}

    async def _get_key_levels(self, symbol: str, volume_data: Dict) -> Dict:
        """Получить ключевые уровни поддержки/сопротивления"""
        try:
            vp = volume_data.get("volume_profile", {})
            poc = vp.get("poc", 0)
            vah = vp.get("vah", 0)
            val = vp.get("val", 0)

            # Используем VP для расчёта уровней
            if poc > 0:
                return {
                    "resistance": [vah, vah * 1.02],
                    "support": [val, val * 0.98],
                    "invalidation": val * 0.95,
                }

            # Fallback
            return {"resistance": [0, 0], "support": [0, 0], "invalidation": 0}
        except Exception as e:
            logger.error(f"❌ Ошибка _get_key_levels: {e}")
            return {"resistance": [0, 0], "support": [0, 0], "invalidation": 0}

    def _format_dashboard(
        self,
        symbol: str,
        ticker: Dict,
        regime: Dict,
        scenario: Dict,
        volume_data: Dict,
        sentiment_data: Dict,
        mtf_trends: Dict,
        levels: Dict,
        whale_activity: Dict,
        liquidation_levels: Dict,
    ) -> str:
        """Форматирует дашборд в текст для Telegram"""

        # Извлекаем данные
        price = ticker["price"]
        price_change_24h = ticker["change_24h"]

        # Форматируем
        f = self.formatter

        text = f"""📊 **{symbol} MARKET INTELLIGENCE**

💰 **Price:** {f.format_price(price)} ({f.format_percentage(price_change_24h)})
📈 **Market Regime:** {f.get_regime_emoji(regime['regime'])} {regime['regime']} (Conf: {regime['confidence']:.0%})
🎯 **Strategy Pattern:** {scenario['scenario_name']} (Conf: {scenario['confidence']:.0%})


📊 **VOLUME ANALYSIS**
├─ 24h Vol: {f.format_volume(volume_data['volume_24h'])}
├─ CVD: {f.format_percentage(volume_data['cvd'])} {volume_data['cvd_label']}
└─ VP: POC {f.format_price(volume_data['volume_profile']['poc'], 0)} | VAH {f.format_price(volume_data['volume_profile']['vah'], 0)} | VAL {f.format_price(volume_data['volume_profile']['val'], 0)}

🔥 **SENTIMENT & PRESSURE**
├─ Funding: {f.format_percentage(sentiment_data['funding_rate'], 3)} {sentiment_data['funding_label']}
├─ OI: {f.format_volume(sentiment_data['open_interest'])}
├─ L/S Ratio: {sentiment_data['long_short_ratio']:.2f} {sentiment_data['ls_label']}
└─ News: {sentiment_data['news_label']}

🐋 **WHALE ACTIVITY (5min)**
├─ Trades: {whale_activity['count']}
├─ Buy Vol: {f.format_volume(whale_activity['buy_volume'])}
├─ Sell Vol: {f.format_volume(whale_activity['sell_volume'])}
└─ Net: {f.format_volume(whale_activity['net_volume'])} {whale_activity['label']}

⚠️ **LIQUIDATION ZONES**
├─ Long Liq: {f.format_price(liquidation_levels['long_liq_level'], 0)} ({f.format_volume(liquidation_levels['long_liq_volume'])})
├─ Short Liq: {f.format_price(liquidation_levels['short_liq_level'], 0)} ({f.format_volume(liquidation_levels['short_liq_volume'])})
└─ Risk: {liquidation_levels['risk_level']}


🎯 **MULTI-TIMEFRAME**
├─ 1H: {f.get_trend_emoji(mtf_trends['1h'])} {mtf_trends['1h']}
├─ 4H: {f.get_trend_emoji(mtf_trends['4h'])} {mtf_trends['4h']}
└─ 1D: {f.get_trend_emoji(mtf_trends['1d'])} {mtf_trends['1d']}

📌 **KEY LEVELS**
├─ Resistance: {f.format_price(levels['resistance'][0], 0)}, {f.format_price(levels['resistance'][1], 0)}
└─ Support: {f.format_price(levels['support'][0], 0)}, {f.format_price(levels['support'][1], 0)}

⏱️ Updated: {f.format_timestamp()}"""

        return text.strip()


# Экспорт
__all__ = ["MarketDashboard"]
