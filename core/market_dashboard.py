#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Market Dashboard - главный дашборд рынка (альтернатива Coinglass)
Показывает всю информацию о символе в одном экране
"""

from typing import Dict, Optional
from datetime import datetime
import requests
import pandas as pd
from config.settings import logger
from telegram_bot.dashboard_helpers import DashboardFormatter
from ai.gemini_interpreter import GeminiInterpreter



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

        # ✅ Инициализация Gemini 2.0 Flash
        import os
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini = GeminiInterpreter(gemini_key) if gemini_key else None

        if self.gemini:
            logger.info("✅ MarketDashboard инициализирован с Gemini 2.0 Flash")
        else:
            logger.warning("⚠️ MarketDashboard инициализирован без AI (no GEMINI_API_KEY)")

    async def generate_dashboard(self, symbol: str) -> str:
        """
        Генерация полного Market Dashboard
        """
        logger.info(f"📊 Генерация dashboard для {symbol}...")

        # 1. Price & 24h Change
        ticker = await self._get_ticker(symbol)

        # 2. Market Regime
        regime = await self._get_market_regime(symbol, ticker)

        # 3. Strategy Pattern (MM Scenario)
        mm_scenario = await self._get_mm_scenario(symbol, ticker)

        # 4. Wyckoff Phase
        wyckoff_phase = await self._get_wyckoff_phase(symbol)

        # 5. ✅ MATCHED SCENARIOS
        matched_scenarios = await self._get_matched_scenarios(symbol)

        # 6. ✅ Volume Analysis (ИСПРАВЛЕНО: добавлен ticker)
        volume_analysis = await self._get_volume_analysis(symbol, ticker)

        # 7. Sentiment & Pressure
        sentiment_pressure = await self._get_sentiment_pressure(symbol)

        # 8. Multi-Timeframe Trends
        mtf_trends = await self._get_mtf_trends(symbol)

        # 9. ✅ Key Levels (ИСПРАВЛЕНО: добавлен volume_analysis)
        key_levels = await self._get_key_levels(symbol, volume_analysis)

        # 10. Whale Activity
        whale_activity = await self._get_whale_activity(symbol)

        # 11. ✅ Liquidation Levels (ДОБАВЛЕНО!)
        liquidation_levels = await self._get_liquidation_levels(symbol, ticker)

        # 12. ✅ Format Dashboard (ИСПРАВЛЕНО: все параметры переданы)
        dashboard_text = await self._format_dashboard(
            symbol=symbol,
            ticker=ticker,
            regime=regime,
            mm_scenario=mm_scenario,
            wyckoff_phase=wyckoff_phase,
            matched_scenarios=matched_scenarios,
            volume_data=volume_analysis,  # ← ПРАВИЛЬНОЕ ИМЯ!
            sentiment_data=sentiment_pressure,  # ← ПРАВИЛЬНОЕ ИМЯ!
            mtf_trends=mtf_trends,
            levels=key_levels,  # ← ПРАВИЛЬНОЕ ИМЯ!
            whale_activity=whale_activity,
            liquidation_levels=liquidation_levels,  # ← ДОБАВЛЕНО!
        )

        logger.info(f"✅ Dashboard для {symbol} сгенерирован")
        return dashboard_text

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

                regime_result = self.bot.market_regime_detector.detect_regime(
                    market_data
                )
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

    def _generate_top3_scenarios(
        self,
        ticker: Dict,
        mtf_trends: Dict,
        volume_data: Dict = None,
        sentiment_data: Dict = None,
    ) -> list:
        """Генерирует ТОП-3 сценария на основе рыночных условий"""
        change_24h = ticker["change_24h"]
        price = ticker["price"]

        # Получаем MTF тренды
        trend_1h = mtf_trends.get("1h", "NEUTRAL")
        trend_4h = mtf_trends.get("4h", "NEUTRAL")
        trend_1d = mtf_trends.get("1d", "NEUTRAL")

        # Получаем дополнительные данные
        cvd = volume_data.get("cvd", 0) if volume_data else 0
        ls_ratio = (
            sentiment_data.get("long_short_ratio", 1.0) if sentiment_data else 1.0
        )

        scenarios = []

        # Определяем основные сценарии на основе price action и MTF
        if change_24h > 3 and trend_4h in ["UP", "BULLISH"]:
            # Сценарий 1: Strong Uptrend
            conf = 70 + min(10, int(abs(change_24h)))
            if cvd > 10:
                conf += 5
            if ls_ratio > 1.5:
                conf += 5
            scenarios.append(
                {"name": "🚀 Strong Uptrend", "probability": min(conf, 85)}
            )

            # Сценарий 2: Overbought Risk
            scenarios.append({"name": "⚠️ Overbought Risk", "probability": 15})

            # Сценарий 3: Continuation
            scenarios.append({"name": "📈 Bullish Continuation", "probability": 10})

        elif change_24h < -3 and trend_4h in ["DOWN", "BEARISH"]:
            # Сценарий 1: Strong Downtrend
            conf = 70 + min(10, int(abs(change_24h)))
            if cvd < -10:
                conf += 5
            if ls_ratio < 0.7:
                conf += 5
            scenarios.append(
                {"name": "📉 Strong Downtrend", "probability": min(conf, 85)}
            )

            # Сценарий 2: Oversold Bounce
            scenarios.append({"name": "🔄 Oversold Bounce", "probability": 15})

            # Сценарий 3: Continuation
            scenarios.append({"name": "🔴 Bearish Continuation", "probability": 10})

        elif abs(change_24h) < 2:
            # Сценарий 1: Range Trading
            conf = 60
            if trend_1h == "NEUTRAL" and trend_4h == "NEUTRAL":
                conf += 15
            scenarios.append({"name": "↔️ Range Trading", "probability": conf})

            # Сценарий 2: Накопление
            if cvd > 5 and ls_ratio > 1.2:
                scenarios.append({"name": "📊 Accumulation Phase", "probability": 25})
            else:
                scenarios.append({"name": "⏸️ Consolidation", "probability": 20})

            # Сценарий 3: Breakout preparation
            scenarios.append({"name": "⚡ Breakout Incoming", "probability": 15})

        else:
            # Смешанные сигналы
            # Сценарий 1: Correction Phase
            conf = 60
            if trend_4h != trend_1h:
                conf += 10
            scenarios.append({"name": "🔄 Correction Phase", "probability": conf})

            # Сценарий 2: MTF Divergence
            scenarios.append({"name": "🔀 MTF Divergence", "probability": 25})

            # Сценарий 3: Neutral Consolidation
            scenarios.append({"name": "⚪ Neutral Drift", "probability": 15})

        # Нормализация вероятностей до 100%
        total_prob = sum(s["probability"] for s in scenarios)
        if total_prob != 100:
            factor = 100 / total_prob
            for s in scenarios:
                s["probability"] = int(s["probability"] * factor)

        return scenarios[:3]  # Возвращаем только ТОП-3

    async def _get_wyckoff_phase(self, symbol: str) -> str:
        try:
            if hasattr(self.bot, "wyckoff_detector"):
                phase = self.bot.wyckoff_detector.get_phase(symbol)
                return phase or "Unknown"
            return "Unknown"
        except Exception as e:
            logger.error(f"❌ Ошибка _get_wyckoff_phase: {e}")
            return "Unknown"

    async def _get_matched_scenarios(self, symbol: str) -> list:
        """Получить подходящие сценарии ММ для текущей ситуации"""
        try:
            # Получаем необходимые данные
            ticker = await self._get_ticker(symbol)
            if not ticker:
                return [{"name": "⚪ No Data", "probability": 100}]

            # Получаем MTF тренды
            mtf_data = await self._get_mtf_trends(symbol)

            # Получаем volume данные
            volume_data = await self._get_volume_analysis(symbol, ticker)

            # Получаем sentiment данные
            sentiment_data = await self._get_sentiment_pressure(symbol)

            # Генерируем ТОП-3 сценария
            scenarios = self._generate_top3_scenarios(
                ticker, mtf_data, volume_data, sentiment_data
            )

            logger.info(f"✅ Generated {len(scenarios)} scenarios for {symbol}")
            return scenarios

        except Exception as e:
            logger.error(f"❌ Error getting scenarios: {e}")
            return [{"name": "⚠️ Analysis Error", "probability": 100}]

    async def _collect_market_data(self, symbol: str) -> Dict:
        """Собирает все рыночные данные для scenario matching"""
        try:
            # Получаем ticker
            ticker = await self._get_ticker(symbol)

            # Получаем volume analysis
            volume_data = await self._get_volume_analysis(symbol, ticker)

            # Получаем sentiment
            sentiment_data = await self._get_sentiment_pressure(symbol)

            # Получаем MTF тренды
            mtf_trends = await self._get_mtf_trends(symbol)

            # Формируем market_data для scenario matcher
            market_data = {
                "symbol": symbol,
                "price": ticker["price"],
                "volume": ticker["volume_24h"],
                "change_24h": ticker["change_24h"],
                "cvd": volume_data.get("cvd", 0),
                "funding_rate": sentiment_data.get("funding_rate", 0),
                "open_interest": sentiment_data.get("open_interest", 0),
                "ls_ratio": sentiment_data.get("long_short_ratio", 1.0),
                "mtf_trends": mtf_trends,
            }

            return market_data

        except Exception as e:
            logger.error(f"_collect_market_data: {e}", exc_info=True)
            return {}

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

                # Метод 2: Fallback на Bybit orderbook если L2 = 0
                if cvd_value == 0.0:
                    try:
                        ob = await self.bot.bybit_connector.get_orderbook(
                            symbol, limit=50
                        )

                        if ob and "bids" in ob and "asks" in ob:
                            # Суммируем топ-20 уровней
                            bids_volume = sum([float(b[1]) for b in ob["bids"][:20]])
                            asks_volume = sum([float(a[1]) for a in ob["asks"][:20]])

                            total_volume = bids_volume + asks_volume
                            if total_volume > 0:
                                cvd_value = (
                                    (bids_volume - asks_volume) / total_volume
                                ) * 100
                                logger.debug(
                                    f"✅ CVD {symbol} (Bybit OB): {cvd_value:+.2f}%"
                                )
                            else:
                                logger.warning(f"⚠️ CVD {symbol}: total_volume = 0")
                        else:
                            logger.warning(
                                f"⚠️ CVD {symbol}: Order Book данные недоступны"
                            )

                    except Exception as e:
                        logger.debug(f"⚠️ Bybit orderbook fallback failed: {e}")

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
                    vp = await self.bot.get_volume_profile(symbol)
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

    # ✅ PUBLIC API для unified_dashboard
    async def get_volume_analysis(self, symbol: str) -> Dict:
        """
        PUBLIC метод для получения CVD данных
        Используется unified_dashboard
        """
        try:
            ticker = await self._get_ticker(symbol)
            return await self._get_volume_analysis(symbol, ticker)
        except Exception as e:
            logger.error(f"Ошибка get_volume_analysis: {e}")
            return {
                "volume_24h": 0,
                "cvd": 0,
                "cvd_label": "⚪ Neutral",
                "volume_profile": {"poc": 0, "vah": 0, "val": 0},
            }

    async def get_sentiment_pressure(self, symbol: str) -> Dict:
        """
        PUBLIC метод для получения sentiment данных
        Используется unified_dashboard
        """
        try:
            return await self._get_sentiment_pressure(symbol)
        except Exception as e:
            logger.error(f"Ошибка get_sentiment_pressure: {e}")
            return {
                "funding_rate": 0,
                "funding_label": "⚪ Neutral",
                "open_interest": 0,
                "long_short_ratio": 0,
                "ls_label": "⚪ Neutral",
                "news_sentiment": "neutral",
                "news_label": "⚪ Neutral",
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

            # Open Interest с Delta расчётом
            open_interest = 0
            oi_label = ""
            oi_delta_pct = 0.0
            oi_trend_emoji = ""

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

                            # OI DELTA РАСЧЁТ
                            try:
                                if not hasattr(self, "oi_cache"):
                                    self.oi_cache = {}
                                    logger.info("✅ OI cache инициализирован")

                                cache_key = f"oi_{symbol}"
                                current_time = datetime.now()

                                if cache_key in self.oi_cache:
                                    prev_oi = self.oi_cache[cache_key]["value"]
                                    prev_time = self.oi_cache[cache_key]["time"]
                                    time_diff_seconds = (
                                        current_time - prev_time
                                    ).total_seconds()

                                    if time_diff_seconds > 3000:
                                        if prev_oi > 0:
                                            oi_delta_pct = (
                                                (open_interest - prev_oi) / prev_oi
                                            ) * 100

                                            if oi_delta_pct > 5:
                                                oi_trend_emoji = "📈"
                                                oi_label = "🔥 Rising"
                                            elif oi_delta_pct > 2:
                                                oi_trend_emoji = "⬆️"
                                                oi_label = "🟢 Growing"
                                            elif oi_delta_pct < -5:
                                                oi_trend_emoji = "📉"
                                                oi_label = "❄️ Falling"
                                            elif oi_delta_pct < -2:
                                                oi_trend_emoji = "⬇️"
                                                oi_label = "🔴 Declining"
                                            else:
                                                oi_trend_emoji = "➡️"
                                                oi_label = "⚪ Stable"

                                            logger.info(
                                                f"📊 OI Delta {symbol}: {oi_delta_pct:+.2f}% "
                                                f"({prev_oi:,.0f} → {open_interest:,.0f})"
                                            )
                                    else:
                                        minutes_left = int(
                                            (3000 - time_diff_seconds) / 60
                                        )
                                        logger.debug(
                                            f"⏳ OI Delta {symbol}: ждём {minutes_left} мин"
                                        )
                                else:
                                    logger.info(f"🔄 OI {symbol}: первая запись в кэш")

                                self.oi_cache[cache_key] = {
                                    "value": open_interest,
                                    "time": current_time,
                                }

                            except Exception as delta_e:
                                logger.error(
                                    f"❌ OI Delta calculation failed: {delta_e}"
                                )

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
                if ls_ratio_data and isinstance(ls_ratio_data, dict):
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

            # ✅ ДОБАВИТЬ FALLBACK БЛОК
            if long_short_ratio == 0.0:
                try:
                    logger.info(
                        f"🔄 Fallback: расчёт L/S Ratio из Order Book для {symbol}"
                    )
                    ob = await self.bot.bybit_connector.get_orderbook(symbol, limit=50)
                    if ob and "bids" in ob and "asks" in ob:
                        bids_volume = sum([float(b[1]) for b in ob["bids"][:20]])
                        asks_volume = sum([float(a[1]) for a in ob["asks"][:20]])

                        if asks_volume > 0:  # ✅ ИСПРАВЛЕНО
                            long_short_ratio = (
                                bids_volume / asks_volume
                            )  # ✅ ИСПРАВЛЕНО

                            # Классификация на основе OB imbalance
                            if long_short_ratio > 1.5:
                                ls_label = "🟢 Bullish (OB)"
                            elif long_short_ratio < 0.7:
                                ls_label = "🔴 Bearish (OB)"
                            else:
                                ls_label = "⚪ Neutral (OB)"

                            logger.info(
                                f"✅ L/S Ratio (fallback): {long_short_ratio:.2f}"
                            )
                        else:
                            logger.warning(f"⚠️ Order Book: asks_volume = 0")
                    else:
                        logger.warning(f"⚠️ Order Book данные недоступны")

                except Exception as fb_e:
                    logger.error(f"❌ L/S Ratio fallback failed: {fb_e}")

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
                "oi_delta_pct": oi_delta_pct,
                "oi_trend_emoji": oi_trend_emoji,
                "oi_label": oi_label,
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
        try:
            # ✅ ПРАВИЛЬНО: Используем WhaleActivityTracker!
            if hasattr(self.bot, "whale_tracker"):
                whale_data = self.bot.whale_tracker.get_whale_activity(
                    symbol=symbol, timeframe_seconds=300  # 5 минут
                )

                # Форматируем данные для dashboard
                count = whale_data.get("trades", 0)
                buy_volume = whale_data.get("buy_volume", 0.0)
                sell_volume = whale_data.get("sell_volume", 0.0)
                net_volume = whale_data.get("net", 0.0)
                dominant_side = whale_data.get("dominant_side", "neutral")

                # Классификация
                if dominant_side == "bullish":
                    label = (
                        "🐋 Strong BUY" if net_volume > buy_volume * 0.5 else "🐋 BUY"
                    )
                elif dominant_side == "bearish":
                    label = (
                        "🦈 Strong SELL"
                        if abs(net_volume) > sell_volume * 0.5
                        else "🦈 SELL"
                    )
                else:
                    label = "⚪ Neutral"

                logger.debug(
                    f"✅ Whale activity {symbol}: {count} trades, net=${net_volume:,.0f}"
                )

                return {
                    "count": count,
                    "buy_volume": buy_volume,
                    "sell_volume": sell_volume,
                    "net_volume": net_volume,
                    "largest_trade": 0.0,  # Не используется в dashboard
                    "label": label,
                }

            # Fallback
            logger.warning(f"⚠️ whale_tracker не найден")
            return {
                "count": 0,
                "buy_volume": 0.0,
                "sell_volume": 0.0,
                "net_volume": 0.0,
                "largest_trade": 0.0,
                "label": "⚪ Neutral",
            }

        except Exception as e:
            logger.error(f"❌ Ошибка whale activity: {e}", exc_info=True)
            return {
                "count": 0,
                "buy_volume": 0.0,
                "sell_volume": 0.0,
                "net_volume": 0.0,
                "largest_trade": 0.0,
                "label": "⚪ Neutral",
            }

    async def _get_liquidation_levels(self, symbol: str, ticker: Dict) -> Dict:
        """Получить зоны ликвидации с расчётом из Order Book"""
        try:
            current_price = ticker["price"]

            # Получаем ATR для расчёта уровней
            atr = ticker.get("atr", current_price * 0.02)  # Fallback 2% от цены

            # Расчёт уровней ликвидации
            # Long liquidation: цена - (ATR * 5) ≈ -5% от текущей цены при leverage 10x
            # Short liquidation: цена + (ATR * 5) ≈ +5% от текущей цены при leverage 10x
            long_liq_level = current_price - (atr * 5)
            short_liq_level = current_price + (atr * 5)

            # Расчёт объёмов из Order Book
            long_liq_volume = 0.0
            short_liq_volume = 0.0

            try:
                ob = await self.bot.bybit_connector.get_orderbook(symbol, limit=100)

                if ob and "bids" in ob and "asks" in ob:
                    # Рассчитываем общий объём Order Book около текущей цены
                    # Long liquidations = объём bids (поддержка)
                    # Short liquidations = объём asks (сопротивление)

                    for bid in ob["bids"][:50]:
                        price = float(bid[0])
                        size = float(bid[1])
                        long_liq_volume += size * price

                    for ask in ob["asks"][:50]:
                        price = float(ask[0])
                        size = float(ask[1])
                        short_liq_volume += size * price

                    # Применяем коэффициент риска ликвидации (30% объёма)
                    # и умножаем на средний leverage (10x)
                    long_liq_volume = long_liq_volume * 0.3 * 10
                    short_liq_volume = short_liq_volume * 0.3 * 10

                    logger.debug(
                        f"✅ Liquidation zones {symbol}: "
                        f"Long ${long_liq_volume:,.0f} @ ${long_liq_level:,.0f}, "
                        f"Short ${short_liq_volume:,.0f} @ ${short_liq_level:,.0f}"
                    )
                else:
                    logger.warning(
                        f"⚠️ Order Book недоступен для расчёта ликвидаций {symbol}"
                    )

            except Exception as e:
                logger.debug(f"⚠️ Order Book fallback для ликвидаций failed: {e}")

            # Определение уровня риска
            total_liq = long_liq_volume + short_liq_volume

            if total_liq > 100_000_000:  # >$100M
                risk_level = "🔴 High"
            elif total_liq > 50_000_000:  # >$50M
                risk_level = "🟡 Medium"
            else:
                risk_level = "⚪ Low"

            return {
                "long_liq_level": long_liq_level,
                "short_liq_level": short_liq_level,
                "long_liq_volume": long_liq_volume,
                "short_liq_volume": short_liq_volume,
                "risk_level": risk_level,
            }

        except Exception as e:
            logger.error(f"❌ Liquidation levels error: {e}")
            return {
                "long_liq_level": 0,
                "short_liq_level": 0,
                "long_liq_volume": 0,
                "short_liq_volume": 0,
                "risk_level": "⚪ Low",
            }

    async def _get_mtf_trends(self, symbol: str) -> Dict:
        """Получить multi-timeframe тренды с контекстными метками"""
        try:
            trends = {}

            for tf, interval in [("1h", "60"), ("4h", "240"), ("1d", "D")]:
                try:
                    # Получаем свечи
                    klines = await self.bot.bybit_connector.get_klines(
                        symbol, interval, 100
                    )

                    if not klines or len(klines) < 20:
                        trends[tf] = "⚪ NEUTRAL"
                        continue

                    # get_klines возвращает List[Dict], конвертируем в pandas
                    import pandas as pd

                    df = pd.DataFrame(klines)

                    close = df["close"].values
                    high = df["high"].values
                    low = df["low"].values

                    # ═══════════════════════════════════════════════════
                    # 1. БАЗОВЫЙ ТРЕНД (EMA 20)
                    # ═══════════════════════════════════════════════════
                    ema20 = pd.Series(close).ewm(span=20, adjust=False).mean().iloc[-1]
                    current_price = close[-1]

                    if current_price > ema20 * 1.005:  # +0.5% выше EMA
                        base_trend = "🟢 UP"
                    elif current_price < ema20 * 0.995:  # -0.5% ниже EMA
                        base_trend = "🔴 DOWN"
                    else:
                        base_trend = "⚪ NEUTRAL"

                    # ═══════════════════════════════════════════════════
                    # 2. RSI КОНТЕКСТ
                    # ═══════════════════════════════════════════════════
                    context_labels = []

                    try:
                        delta = pd.Series(close).diff()
                        gain = delta.where(delta > 0, 0).rolling(window=14).mean()
                        loss = -delta.where(delta < 0, 0).rolling(window=14).mean()

                        # Избегаем деления на ноль
                        rs = gain / loss.replace(0, 0.0001)
                        rsi = 100 - (100 / (1 + rs))
                        current_rsi = rsi.iloc[-1]

                        if not pd.isna(current_rsi):
                            if current_rsi < 30:
                                context_labels.append("oversold")
                                context_labels.append(f"RSI {current_rsi:.0f}")
                            elif current_rsi > 70:
                                context_labels.append("overbought")
                                context_labels.append(f"RSI {current_rsi:.0f}")
                            elif current_rsi < 40 and base_trend == "🔴 DOWN":
                                context_labels.append(f"RSI {current_rsi:.0f}")
                            elif current_rsi > 60 and base_trend == "🟢 UP":
                                context_labels.append(f"RSI {current_rsi:.0f}")

                    except Exception as rsi_e:
                        logger.debug(f"⚠️ RSI calculation error for {tf}: {rsi_e}")

                    # ═══════════════════════════════════════════════════
                    # 3. MACD MOMENTUM
                    # ═══════════════════════════════════════════════════
                    try:
                        ema12 = pd.Series(close).ewm(span=12, adjust=False).mean()
                        ema26 = pd.Series(close).ewm(span=26, adjust=False).mean()
                        macd = ema12 - ema26
                        macd_signal = macd.ewm(span=9, adjust=False).mean()
                        macd_hist = macd - macd_signal

                        # Проверяем ослабление momentum
                        if len(macd_hist) >= 3:
                            current_hist = abs(macd_hist.iloc[-1])
                            prev_hist = abs(macd_hist.iloc[-2])
                            prev_prev_hist = abs(macd_hist.iloc[-3])

                            # Momentum weakening если 2 последних бара меньше предыдущих
                            if current_hist < prev_hist < prev_prev_hist:
                                context_labels.append("momentum weakening")

                    except Exception as macd_e:
                        logger.debug(f"⚠️ MACD calculation error for {tf}: {macd_e}")

                    # ═══════════════════════════════════════════════════
                    # 4. SUPPORT/RESISTANCE TESTING
                    # ═══════════════════════════════════════════════════
                    try:
                        recent_high = max(high[-20:])
                        recent_low = min(low[-20:])

                        # Проверяем близость к экстремумам (в пределах 1%)
                        distance_to_high = (
                            abs(current_price - recent_high) / current_price
                        )
                        distance_to_low = (
                            abs(current_price - recent_low) / current_price
                        )

                        if distance_to_high < 0.01:
                            context_labels.append("testing resistance")
                        elif distance_to_low < 0.01:
                            context_labels.append("testing support")

                    except Exception as sr_e:
                        logger.debug(f"⚠️ S/R testing error for {tf}: {sr_e}")

                    # ═══════════════════════════════════════════════════
                    # 5. ФИНАЛЬНОЕ ФОРМАТИРОВАНИЕ
                    # ═══════════════════════════════════════════════════
                    if context_labels:
                        # Ограничиваем до 2 самых важных меток
                        final_context = ", ".join(context_labels[:2])
                        trends[tf] = f"{base_trend} ({final_context})"
                    else:
                        trends[tf] = base_trend

                    logger.debug(f"✅ MTF {tf}: {trends[tf]}")

                except Exception as tf_e:
                    logger.error(f"❌ MTF error for {tf}: {tf_e}")
                    trends[tf] = "⚪ NEUTRAL"

            return trends

        except Exception as e:
            logger.error(f"❌ _get_mtf_trends critical error: {e}", exc_info=True)
            return {"1h": "⚪ NEUTRAL", "4h": "⚪ NEUTRAL", "1d": "⚪ NEUTRAL"}

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
                    "pivot": poc,
                }

            # Fallback
            return {
                "resistance": [0, 0],
                "support": [0, 0],
                "invalidation": 0,
                "pivot": 0,
            }
        except Exception as e:
            logger.error(f"❌ Ошибка _get_key_levels: {e}")
            return {
                "resistance": [0, 0],
                "support": [0, 0],
                "invalidation": 0,
                "pivot": 0,
            }

    async def _format_dashboard(
        self,
        symbol: str,
        ticker: Dict,
        regime: Dict,
        mm_scenario: Dict,
        volume_data: Dict,
        sentiment_data: Dict,
        mtf_trends: Dict,
        levels: Dict,
        whale_activity: Dict,
        liquidation_levels: Dict,
        matched_scenarios: Optional[list] = None,
        wyckoff_phase: Optional[str] = None,
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
🎯 **Strategy Pattern:** {mm_scenario['scenario_name']} (Conf: {mm_scenario['confidence']:.0%})

"""
        if wyckoff_phase:
            text += f"\n📊 **Wyckoff Phase:** {wyckoff_phase}"

        if matched_scenarios:
            text += "\n\n🧠 **MARKET SCENARIOS**"
            for i, sc in enumerate(matched_scenarios, start=1):
                name = sc.get("name", "Unknown")
                prob = sc.get("probability", 0)
                text += f"\n├─ {i}️⃣ {name} → {prob:.0f}%"
            logger.info(f"✅ Отображено {len(matched_scenarios)}сценариев в дашборде")

        text += f"""

📊 **VOLUME ANALYSIS**
├─ 24h Vol: {f.format_volume(volume_data['volume_24h'])}
├─ CVD: {f.format_percentage(volume_data['cvd'])} {volume_data['cvd_label']}
└─ VP: POC {f.format_price(volume_data['volume_profile']['poc'], 0)} | VAH {f.format_price(volume_data['volume_profile']['vah'], 0)} | VAL {f.format_price(volume_data['volume_profile']['val'], 0)}

🔥 **SENTIMENT & PRESSURE**
├─ Funding: {f.format_percentage(sentiment_data['funding_rate'], 3)} {sentiment_data['funding_label']}
├─ OI: {f.format_volume(sentiment_data['open_interest'])} ({sentiment_data['oi_delta_pct']:+.1f}% за 1ч) {sentiment_data['oi_trend_emoji']}
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
├─ Pivot: {f.format_price(levels['pivot'], 0)}
├─ Resistance: {', '.join([f.format_price(r, 0) for r in levels['resistance'][:3]])}
└─ Support: {', '.join([f.format_price(s, 0) for s in levels['support'][:3]])}


⏱️ Updated: {f.format_timestamp()}"""

        # 🤖 AI INTERPRETATION (Gemini 2.0)
        if self.gemini:
            try:
                gemini_metrics = {
                    "symbol": symbol,
                    "cvd": volume_data.get("cvd", 0),
                    "funding_rate": sentiment_data.get("funding_rate", 0),
                    "open_interest": sentiment_data.get("open_interest", 0),
                    "ls_ratio": sentiment_data.get("long_short_ratio", 1.0),
                    "orderbook_pressure": 0,  # Можно добавить если есть
                    "whale_activity": [{"volume": whale_activity.get("net_volume", 0)}]
                }

                ai_interpretation = await self.gemini.interpret_metrics(gemini_metrics)

                if ai_interpretation:
                    text += f"\n\n AI INTERPRETATION \n{ai_interpretation}"

            except Exception as e:
                logger.error(f"❌ Gemini interpretation failed: {e}")

        text += f"\n\n⏱️ Updated: {f.format_timestamp()}"
        return text.strip()

    async def _calculate_support_resistance(self, symbol: str, ticker: Dict) -> Dict:
        """Рассчитать Support/Resistance уровни на основе исторических данных"""
        try:
            # Получаем исторические свечи из БД
            import sqlite3

            conn = sqlite3.connect("data/gio_crypto_bot.db")
            cursor = conn.cursor()

            # Загружаем последние 1000 свечей (5m timeframe)
            cursor.execute(
                """
                SELECT high, low, close
                FROM market_data
                WHERE symbol = ?
                ORDER BY timestamp DESC
                LIMIT 1000
            """,
                (symbol,),
            )

            candles = cursor.fetchall()
            conn.close()

            if len(candles) < 100:
                logger.warning(f"⚠️ Недостаточно данных для S/R: {len(candles)} свечей")
                return {"support": [], "resistance": [], "pivot": 0}

            # Метод 1: Классические Pivot Points
            recent = candles[:20]  # Последние 20 свечей
            high = max([c[0] for c in recent])
            low = min([c[1] for c in recent])
            close = recent[0][2]

            pivot = (high + low + close) / 3
            r1 = (2 * pivot) - low
            r2 = pivot + (high - low)
            s1 = (2 * pivot) - high
            s2 = pivot - (high - low)

            # Метод 2: Fractal-based S/R (находим локальные max/min)
            highs = [c[0] for c in candles]
            lows = [c[1] for c in candles]

            resistance_levels = []
            support_levels = []

            # Находим фрактальные максимумы (resistance)
            for i in range(2, len(highs) - 2):
                if (
                    highs[i] > highs[i - 1]
                    and highs[i] > highs[i - 2]
                    and highs[i] > highs[i + 1]
                    and highs[i] > highs[i + 2]
                ):
                    resistance_levels.append(highs[i])

            # Находим фрактальные минимумы (support)
            for i in range(2, len(lows) - 2):
                if (
                    lows[i] < lows[i - 1]
                    and lows[i] < lows[i - 2]
                    and lows[i] < lows[i + 1]
                    and lows[i] < lows[i + 2]
                ):
                    support_levels.append(lows[i])

            # Кластеризуем уровни (убираем близкие)
            current_price = ticker["price"]
            tolerance = current_price * 0.01  # 1% зона

            def cluster_levels(levels):
                if not levels:
                    return []
                levels = sorted(set(levels))
                clustered = [levels[0]]
                for level in levels[1:]:
                    if abs(level - clustered[-1]) > tolerance:
                        clustered.append(level)
                return clustered[:5]  # Топ-5 уровней

            resistance_final = cluster_levels(
                [l for l in resistance_levels if l > current_price]
            )
            support_final = cluster_levels(
                [l for l in support_levels if l < current_price]
            )

            # Комбинируем с классическими pivot points
            all_resistance = sorted(set(resistance_final + [r1, r2]))[:3]
            all_support = sorted(set(support_final + [s1, s2]), reverse=True)[:3]

            logger.debug(
                f"✅ S/R для {symbol}: Support={all_support}, Resistance={all_resistance}"
            )

            return {
                "support": all_support,
                "resistance": all_resistance,
                "pivot": pivot,
            }

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта S/R: {e}", exc_info=True)
            return {"support": [], "resistance": [], "pivot": 0}


# Экспорт
__all__ = ["MarketDashboard"]
