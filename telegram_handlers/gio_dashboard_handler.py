#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIO Market Intelligence Dashboard Handler
Unified dashboard - замена Coinglass/ExoCharts
"""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Optional
from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from config.settings import logger


class GIODashboardHandler:
    """Единый информативный дашборд для GIO Bot"""

    def __init__(self, bot_instance):
        self.bot = bot_instance
        from analytics.market_phase_detector import MarketPhaseDetector

        self.phase_detector = MarketPhaseDetector()
        logger.info("✅ GIODashboardHandler инициализирован")

    async def cmd_gio(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        /gio [SYMBOL] - GIO Market Intelligence Dashboard
        Показывает ВСЁ в одном сообщении
        """
        try:
            # Определяем символ
            symbol = "BTCUSDT"
            if context.args:
                symbol = context.args[0].upper()
                if not symbol.endswith("USDT"):
                    symbol = f"{symbol}USDT"

            user = update.effective_user.username or "Unknown"
            logger.info(f"📊 /gio {symbol} от @{user}")

            # Loading сообщение
            loading = await update.message.reply_text(
                f"🔍 Загружаю GIO Intelligence для {symbol}..."
            )

            # Собираем данные
            dashboard = await self.build_dashboard(symbol)

            # Отправляем дашборд
            await loading.delete()
            await update.message.reply_text(
                dashboard, parse_mode=None  # Без Markdown для стабильности
            )

        except Exception as e:
            logger.error(f"❌ /gio error: {e}", exc_info=True)
            await update.message.reply_text(f"⚠️ Ошибка: {str(e)}")

    async def build_dashboard(self, symbol: str) -> str:
        """Построение unified dashboard"""
        try:
            lines = []
            lines.append(f"🎯 GIO MARKET INTELLIGENCE — {symbol}")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("")

            # === 1. PRICE ACTION ===
            try:
                ticker = await self.bot.bybit_connector.get_ticker(symbol)
                if ticker:
                    price = float(ticker.get("lastPrice", 0))
                    change = float(ticker.get("price24hPcnt", 0)) * 100

                    emoji = "🟢" if change >= 0 else "🔴"

                    lines.append("💰 PRICE ACTION")
                    lines.append(
                        f"├─ Current: ${price:,.2f} ({emoji}{change:+.2f}% 24h)"
                    )

                    # Получаем режим рынка
                    try:
                        regime = (
                            await self.bot.market_structure_analyzer.get_market_regime(
                                symbol
                            )
                        )
                        if regime:
                            regime_name = regime.get("regime", "Unknown")
                            regime_conf = regime.get("confidence", 0)
                            regime_emoji = self.get_regime_emoji(regime_name)
                            lines.append(
                                f"└─ Trend: {regime_emoji} {regime_name.upper()} ({regime_conf:.0f}% conf)"
                            )
                        else:
                            lines.append("└─ Trend: ... (анализируется)")
                    except:
                        lines.append("└─ Trend: ... (анализируется)")

                    lines.append("")
            except Exception as e:
                logger.error(f"Price error: {e}")
                lines.append("💰 PRICE ACTION")
                lines.append("└─ ⚠️ Данные недоступны")
                lines.append("")

            # === 2. MARKET PHASE ===
            lines.append("🎯 MARKET PHASE")
            try:
                ticker = await self.bot.bybit_connector.get_ticker(symbol)
                vp_data = await self.get_volume_profile_data(symbol)

                if ticker and vp_data:
                    price = float(ticker.get("lastPrice", 0))
                    price_change = float(ticker.get("price24hPcnt", 0)) * 100

                    # Получаем OB imbalance
                    ob_imbalance = 0
                    try:
                        if hasattr(self.bot, "orderbook_ws") and self.bot.orderbook_ws:
                            if hasattr(self.bot.orderbook_ws, "_orderbook"):
                                snapshot = self.bot.orderbook_ws._orderbook
                                bids = snapshot.get("bids", [])
                                asks = snapshot.get("asks", [])
                                if bids and asks:
                                    bid_vol = sum(float(b[1]) for b in bids[:50])
                                    ask_vol = sum(float(a[1]) for a in asks[:50])
                                    total = bid_vol + ask_vol
                                    if total > 0:
                                        ob_imbalance = (
                                            (bid_vol - ask_vol) / total
                                        ) * 100
                    except:
                        pass

                    # Получаем CVD
                    cvd = 0
                    try:
                        if hasattr(self.bot, "orderbook_analyzer"):
                            cvd_data = await self.bot.orderbook_analyzer.get_cvd(symbol)
                            cvd = cvd_data.get("cvd_pct", 0) if cvd_data else 0
                    except:
                        pass

                    # Определяем фазу
                    phase_info = await self.phase_detector.detect_phase(
                        symbol=symbol,
                        price=price,
                        volume_profile=vp_data,
                        ob_imbalance=ob_imbalance,
                        cvd=cvd,
                        price_change_24h=price_change,
                    )

                    phase = phase_info.get("phase", "UNKNOWN")
                    emoji = phase_info.get("emoji", "❓")
                    confidence = phase_info.get("confidence", 0)
                    description = phase_info.get("description", "")

                    lines.append(
                        f"├─ Phase: {emoji} {phase} ({confidence}% confidence)"
                    )
                    lines.append(f"└─ {description}")
                else:
                    lines.append("└─ ⚠️ Данные недоступны")
            except Exception as e:
                logger.error(f"Phase detection error: {e}")
                lines.append("└─ ⚠️ Ошибка определения фазы")
            lines.append("")

            # ===  MARKET MAKER SCENARIO ===
            lines.append("📊 MARKET MAKER SCENARIO")
            try:
                if hasattr(self.bot, "scenario_matcher"):
                    # Собираем данные
                    ticker = await self.bot.bybit_connector.get_ticker(symbol)
                    vp_data = await self.get_volume_profile_data(symbol)

                    if ticker and vp_data:
                        price = float(ticker.get("lastPrice", 0))

                        # ✅ ПРАВИЛЬНЫЕ ДАННЫЕ для UnifiedScenarioMatcher
                        market_data = {
                            "price": price,
                            "close": price,
                            "volume": float(ticker.get("volume24h", 0)),
                            "poc": vp_data.get("poc", 0),
                            "vah": vp_data.get("vah", 0),
                            "val": vp_data.get("val", 0),
                        }

                        indicators = {
                            "rsi": 50,  # Заглушка
                            "rsi_1h": 50,
                            "macd_histogram": 0,
                            "atr": 0,
                        }

                        mtf_trends = {
                            "1H": {"trend": "neutral", "strength": 0},
                            "4H": {"trend": "neutral", "strength": 0},
                            "1D": {"trend": "neutral", "strength": 0},
                        }

                        news_sentiment = {
                            "sentiment": "neutral",
                            "score": 0,
                        }

                        veto_checks = {
                            "has_veto": False,
                            "veto_reasons": [],
                            "liquidity_ok": True,
                            "spread_ok": True,
                            "volatility_ok": True,
                        }

                        cvd_data = None  # Optional

                        # ✅ ПРАВИЛЬНЫЙ ВЫЗОВ match_scenario
                        scenario = self.bot.scenario_matcher.match_scenario(
                            symbol=symbol,
                            market_data=market_data,
                            indicators=indicators,
                            mtf_trends=mtf_trends,
                            volume_profile=vp_data,
                            news_sentiment=news_sentiment,
                            veto_checks=veto_checks,
                            cvd_data=cvd_data,
                        )

                        if scenario and scenario.get("score", 0) > 50:
                            name = scenario.get("scenario_name", "Unknown")
                            status = scenario.get("status", "observation")
                            conf = scenario.get("score", 0)

                            emoji = self.get_scenario_emoji(name)
                            lines.append(
                                f"├─ {emoji} {name.upper()} — {status} ({conf:.0f}% conf)"
                            )
                            lines.append(
                                f"├─ Direction: {scenario.get('direction', 'N/A').upper()}"
                            )
                            lines.append(
                                f"└─ Timeframe: {scenario.get('timeframe', '1H')}"
                            )
                        else:
                            lines.append("└─ ⚠️ Сценарий не определен (низкий score)")
                    else:
                        lines.append("└─ ⚠️ Недостаточно данных")
                else:
                    lines.append("└─ ⚠️ Scenario matcher не инициализирован")
            except Exception as e:
                logger.error(f"Scenario error: {e}", exc_info=True)
                lines.append(f"└─ ⚠️ Ошибка определения сценария")
            lines.append("")

            # === 3. INSTITUTIONAL METRICS ===
            lines.append("🔥 INSTITUTIONAL METRICS")
            try:
                # Funding rate - ИСПРАВЛЕНО: используем snake_case
                funding_rate = 0
                oi_value = 0
                ls_ratio = 0

                try:
                    # Пробуем разные варианты названий методов
                    if hasattr(self.bot, "get_funding_rate"):
                        funding = await self.bot.get_funding_rate(symbol)
                        funding_rate = funding.get("rate", 0) if funding else 0
                    elif hasattr(self.bot.bybit_connector, "get_funding_rate"):
                        funding = await self.bot.bybit_connector.get_funding_rate(
                            symbol
                        )
                        funding_rate = funding.get("rate", 0) if funding else 0
                except Exception as e:
                    logger.debug(f"Funding rate error: {e}")

                try:
                    # Open Interest
                    if hasattr(self.bot, "get_open_interest"):
                        oi = await self.bot.get_open_interest(symbol)
                        oi_value = oi.get("value", 0) if oi else 0
                    elif hasattr(self.bot.bybit_connector, "get_open_interest"):
                        oi = await self.bot.bybit_connector.get_open_interest(symbol)
                        oi_value = oi.get("value", 0) if oi else 0
                except Exception as e:
                    logger.debug(f"OI error: {e}")

                try:
                    # Long/Short Ratio
                    if hasattr(self.bot, "get_long_short_ratio"):
                        ratio = await self.bot.get_long_short_ratio(symbol)
                        ls_ratio = ratio.get("ratio", 0) if ratio else 0
                    elif hasattr(self.bot.bybit_connector, "get_long_short_ratio"):
                        ratio = await self.bot.bybit_connector.get_long_short_ratio(
                            symbol
                        )
                        ls_ratio = ratio.get("ratio", 0) if ratio else 0
                except Exception as e:
                    logger.debug(f"L/S Ratio error: {e}")

                long_pct = (ls_ratio / (1 + ls_ratio)) * 100 if ls_ratio else 50

                # CVD
                cvd = 0
                try:
                    if hasattr(self.bot, "orderbook_analyzer"):
                        cvd_data = await self.bot.orderbook_analyzer.get_cvd(symbol)
                        cvd = cvd_data.get("cvd_pct", 0) if cvd_data else 0
                except Exception as e:
                    logger.debug(f"CVD error: {e}")

                funding_emoji = self.get_funding_emoji(funding_rate)
                cvd_emoji = self.get_cvd_emoji(cvd)

                lines.append(f"├─ Funding: {funding_rate:+.4f}% {funding_emoji}")
                lines.append(f"├─ OI: ${oi_value/1e9:.2f}B")
                lines.append(
                    f"├─ L/S Ratio: {ls_ratio:.2f} ({long_pct:.0f}% LONG) {'🟢' if ls_ratio > 1 else '🔴'}"
                )
                lines.append(f"└─ CVD: {cvd:+.2f}% {cvd_emoji}")
            except Exception as e:
                logger.error(f"Metrics error: {e}")
                lines.append("└─ ⚠️ Данные недоступны")
            lines.append("")

            # === 4. MULTI-TIMEFRAME ===
            lines.append("📈 MULTI-TIMEFRAME ALIGNMENT")
            try:
                trends = {}

                if hasattr(self.bot, "multi_tf_filter"):
                    mtf = self.bot.multi_tf_filter

                    # ✅ ПРАВИЛЬНЫЙ СПОСОБ: Проверяем, есть ли кэшированные данные MTF
                    if hasattr(mtf, "_cache") and mtf._cache:
                        # Пытаемся получить из кэша
                        cache_key = f"mtf_{symbol}"
                        if cache_key in mtf._cache:
                            cached_data = mtf._cache[cache_key]
                            for tf in ["1h", "4h", "1d"]:
                                if tf in cached_data:
                                    trends[tf] = cached_data[tf]

                    # Если кэша нет, пробуем получить через connector напрямую
                    if not trends:
                        for tf in ["1h", "4h", "1d"]:
                            try:
                                # Пробуем через cached data в multi_tf_filter
                                if hasattr(mtf, "trends") and symbol in mtf.trends:
                                    symbol_trends = mtf.trends[symbol]
                                    if tf in symbol_trends:
                                        trends[tf] = symbol_trends[tf]
                                else:
                                    # Fallback: Показываем UNKNOWN
                                    trends[tf] = {"trend": "UNKNOWN", "strength": 0}
                            except Exception as e:
                                logger.debug(f"MTF {tf} cache error: {e}")
                                trends[tf] = {"trend": "UNKNOWN", "strength": 0}

                    # Выводим результаты
                    if trends and any(
                        t.get("trend") != "UNKNOWN" for t in trends.values()
                    ):
                        for tf in ["1h", "4h", "1d"]:
                            trend_data = trends.get(tf, {})
                            trend = trend_data.get("trend", "UNKNOWN")
                            strength = trend_data.get("strength", 0)
                            emoji = self.get_trend_emoji(trend)
                            lines.append(
                                f"├─ {tf.upper()}: {emoji} {trend} (strength {strength:.2f})"
                            )

                        # Agreement calculation
                        up_count = sum(
                            1 for t in trends.values() if t.get("trend") == "UP"
                        )
                        down_count = sum(
                            1 for t in trends.values() if t.get("trend") == "DOWN"
                        )
                        total = len(trends)

                        if up_count > down_count:
                            agreement = up_count / total
                            agreement_text = "Bullish"
                        elif down_count > up_count:
                            agreement = down_count / total
                            agreement_text = "Bearish"
                        else:
                            agreement = 0.33
                            agreement_text = "Mixed"

                        agreement_emoji = (
                            "🟢"
                            if agreement >= 0.67
                            else "⚠️" if agreement >= 0.34 else "🔴"
                        )
                        lines.append(
                            f"└─ Agreement: {agreement:.0%} {agreement_emoji} {agreement_text}"
                        )
                    else:
                        lines.append("└─ ⚠️ MTF данные в процессе загрузки...")
                else:
                    lines.append("└─ ⚠️ MTF не инициализирован")
            except Exception as e:
                logger.error(f"MTF error: {e}", exc_info=True)
                lines.append("└─ ⚠️ MTF ошибка")
            lines.append("")

            # === 5. VOLUME PROFILE ===
            lines.append("📊 VOLUME PROFILE")
            try:
                vp = await self.bot.get_volume_profile(symbol)
                if vp and vp.get("poc"):
                    poc = vp.get("poc", 0)
                    vah = vp.get("vah", 0)
                    val = vp.get("val", 0)

                    lines.append(f"├─ POC: ${poc:,.2f} (Point of Control)")
                    lines.append(f"├─ VAH: ${vah:,.2f} (Value Area High)")
                    lines.append(f"├─ VAL: ${val:,.2f} (Value Area Low)")

                    # Position
                    ticker = await self.bot.bybit_connector.get_ticker(symbol)
                    if ticker:
                        price = float(ticker.get("lastPrice", 0))
                        position = self.get_vp_position(price, poc, vah, val)
                        poc_diff = ((price - poc) / poc) * 100
                        lines.append(
                            f"└─ Position: {position} ({poc_diff:+.2f}% from POC)"
                        )
                else:
                    lines.append("└─ ⚠️ VP данные недоступны")
            except Exception as e:
                logger.error(f"VP error: {e}")
                lines.append("└─ ⚠️ VP ошибка")
            lines.append("")

            # === 6. ORDERBOOK PRESSURE ===
            lines.append("🐋 ORDERBOOK PRESSURE (Real-time)")
            try:
                # ✅ ИСПРАВЛЕНИЕ: Используем self.bot.orderbook_ws (не bybit_orderbook_ws)
                if hasattr(self.bot, "orderbook_ws") and self.bot.orderbook_ws:
                    # Проверяем наличие _orderbook атрибута
                    if (
                        hasattr(self.bot.orderbook_ws, "_orderbook")
                        and self.bot.orderbook_ws._orderbook
                    ):
                        snapshot = self.bot.orderbook_ws._orderbook

                        bids = snapshot.get("bids", [])
                        asks = snapshot.get("asks", [])

                        if bids and asks:
                            # Считаем top 50 levels
                            bid_vol = sum(float(b[1]) for b in bids[:50])
                            ask_vol = sum(float(a[1]) for a in asks[:50])
                            total = bid_vol + ask_vol

                            if total > 0:
                                bid_pct = (bid_vol / total) * 100
                                ask_pct = (ask_vol / total) * 100
                                imbalance = bid_pct - ask_pct

                                emoji = self.get_pressure_emoji(imbalance)

                                lines.append(
                                    f"├─ BID: {bid_pct:.1f}% {'🟢' if bid_pct > 50 else '🔴'}"
                                )
                                lines.append(f"├─ ASK: {ask_pct:.1f}%")
                                lines.append(f"└─ Imbalance: {imbalance:+.1f}% {emoji}")
                            else:
                                lines.append("└─ ⚠️ Нет объёма в orderbook")
                        else:
                            lines.append("└─ ⚠️ Пустой orderbook")
                    else:
                        lines.append("└─ ⚠️ Ожидание данных orderbook...")
                else:
                    lines.append("└─ ⚠️ Orderbook WS не подключен")
            except Exception as e:
                logger.error(f"L2 error: {e}")
                lines.append("└─ ⚠️ L2 ошибка")
            lines.append("")

            # === 7. KEY LEVELS ===
            lines.append("💎 KEY LEVELS")
            try:
                vp = await self.bot.get_volume_profile(symbol)
                if vp:
                    # Берем VAH/VAL как ключевые уровни
                    vah = vp.get("vah", 0)
                    val = vp.get("val", 0)

                    lines.append(f"├─ Resistance: ${vah:,.0f}")
                    lines.append(f"├─ Support: ${val:,.0f}")

                    ticker = await self.bot.bybit_connector.get_ticker(symbol)
                    if ticker:
                        price = float(ticker.get("lastPrice", 0))
                        if price > 0 and vah > 0:
                            breakout_pct = ((vah - price) / price) * 100
                            lines.append(
                                f"└─ Breakout Target: ${vah:,.0f} ({breakout_pct:+.1f}%)"
                            )
                else:
                    lines.append("└─ ⚠️ Уровни недоступны")
            except Exception as e:
                logger.error(f"Levels error: {e}")
                lines.append("└─ ⚠️ Уровни ошибка")
            lines.append("")

            # === FOOTER ===
            now = datetime.now().strftime("%H:%M:%S")
            next_update = (datetime.now() + timedelta(minutes=5)).strftime("%H:%M:%S")

            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append(f"⏱️ Updated: {now}")
            lines.append(f"🔄 Next update: {next_update} (manual)")
            lines.append("")

            # === 8. WHALE ACTIVITY ===
            lines.append("🐋 WHALE ACTIVITY (Last 15min)")
            try:
                if hasattr(self.bot, "whale_tracker"):
                    whale_info = self.bot.whale_tracker.format_whale_info(
                        symbol, minutes=15
                    )
                    lines.append(whale_info)
                else:
                    lines.append("└─ ⚠️ Whale tracker не инициализирован")
            except Exception as e:
                logger.error(f"Whale activity error: {e}")
                lines.append("└─ ⚠️ Whale data unavailable")
            lines.append("")

            # === GIO INTERPRETATION ===
            lines.append("💡 GIO Interpretation:")
            # Генерируем интерпретацию на основе реальных данных
            interpretation = await self.generate_interpretation(symbol)
            lines.append(interpretation)

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"❌ build_dashboard error: {e}", exc_info=True)
            return f"⚠️ Ошибка построения дашборда: {str(e)}"

    async def generate_interpretation(self, symbol: str) -> str:
        """Генерация интеллектуальной интерпретации"""
        try:
            parts = []

            # Получаем CVD
            cvd_data = (
                await self.bot.orderbook_analyzer.get_cvd(symbol)
                if hasattr(self.bot, "orderbook_analyzer")
                else {}
            )
            cvd = cvd_data.get("cvd_pct", 0)

            # Получаем L2 pressure
            try:
                snapshot = (
                    self.bot.bybit_orderbook_ws.get_orderbook_snapshot()
                    if hasattr(self.bot, "bybit_orderbook_ws")
                    else None
                )
                if snapshot:
                    bid_vol = sum(float(b[1]) for b in snapshot.get("bids", [])[:50])
                    ask_vol = sum(float(a[1]) for a in snapshot.get("asks", [])[:50])
                    total = bid_vol + ask_vol
                    imbalance = ((bid_vol - ask_vol) / total * 100) if total > 0 else 0
                else:
                    imbalance = 0
            except:
                imbalance = 0

            # Формируем интерпретацию
            if abs(cvd) > 50:
                side = "покупателей" if cvd > 0 else "продавцов"
                parts.append(f"Сильная активность {side} (CVD {cvd:+.0f}%).")

            if abs(imbalance) > 30:
                pressure_side = "покупателей" if imbalance > 0 else "продавцов"
                parts.append(
                    f"L2 orderbook показывает давление {pressure_side} ({imbalance:+.0f}%)."
                )

            if not parts:
                parts.append("Рынок в балансе, ожидаем развития ситуации.")

            return " ".join(parts)

        except Exception as e:
            logger.error(f"generate_interpretation error: {e}")
            return "Анализируйте ситуацию с осторожностью."

    def get_regime_emoji(self, regime: str) -> str:
        mapping = {"TRENDING": "📈", "RANGING": "↔️", "VOLATILE": "⚡", "BREAKOUT": "🚀"}
        return mapping.get(regime.upper(), "⚪")

    def get_scenario_emoji(self, scenario: str) -> str:
        mapping = {
            "ACCUMULATION": "🎯",
            "MARKUP": "📈",
            "DISTRIBUTION": "📉",
            "MARKDOWN": "🔴",
            "IMPULSE": "🚀",
            "MEANREVERSION": "↔️",
            "FLAT": "📊",
        }
        return mapping.get(scenario.upper(), "⚪")

    def get_funding_emoji(self, funding: float) -> str:
        if funding > 0.01:
            return "🔥"
        elif funding < -0.01:
            return "❄️"
        else:
            return "⚪"

    def get_cvd_emoji(self, cvd: float) -> str:
        if cvd > 50:
            return "🔥"
        elif cvd > 20:
            return "🟢"
        elif cvd < -50:
            return "❄️"
        elif cvd < -20:
            return "🔴"
        else:
            return "⚪"

    def get_trend_emoji(self, trend: str) -> str:
        mapping = {"UP": "🟢", "DOWN": "🔴", "NEUTRAL": "⚪", "UNKNOWN": "⚪"}
        return mapping.get(trend.upper(), "⚪")

    def get_pressure_emoji(self, imbalance: float) -> str:
        if imbalance > 50:
            return "🔥"
        elif imbalance > 20:
            return "🟢"
        elif imbalance < -50:
            return "❄️"
        elif imbalance < -20:
            return "🔴"
        else:
            return "⚪"

    def get_vp_position(self, price: float, poc: float, vah: float, val: float) -> str:
        if price > vah:
            return "Above VAH ⬆️"
        elif price < val:
            return "Below VAL ⬇️"
        elif price > poc:
            return "Above POC 🟢"
        else:
            return "Below POC 🔴"

    async def get_market_data(self, symbol: str) -> Dict:
        """Получение полных рыночных данных"""
        try:
            data = {}

            # Ticker
            ticker = await self.bot.bybit_connector.get_ticker(symbol)
            if ticker:
                data["price"] = float(ticker.get("lastPrice", 0))
                data["change_24h"] = float(ticker.get("price24hPcnt", 0)) * 100
                data["volume_24h"] = float(ticker.get("volume24h", 0))

            # Funding
            if hasattr(self.bot, "get_funding_rate"):
                funding = await self.bot.get_funding_rate(symbol)
                data["funding_rate"] = funding.get("rate", 0) if funding else 0

            # OI
            if hasattr(self.bot, "get_open_interest"):
                oi = await self.bot.get_open_interest(symbol)
                data["open_interest"] = oi.get("value", 0) if oi else 0

            # L/S Ratio
            if hasattr(self.bot, "get_long_short_ratio"):
                ratio = await self.bot.get_long_short_ratio(symbol)
                data["long_short_ratio"] = ratio.get("ratio", 0) if ratio else 0

            # CVD
            if hasattr(self.bot, "orderbook_analyzer"):
                cvd_data = await self.bot.orderbook_analyzer.get_cvd(symbol)
                data["cvd"] = cvd_data.get("cvd_pct", 0) if cvd_data else 0

            return data
        except Exception as e:
            logger.error(f"get_market_data error: {e}")
            return {}

    async def get_volume_profile_data(self, symbol: str) -> Dict:
        """Получение данных Volume Profile"""
        try:
            if hasattr(self.bot, "get_volume_profile"):
                return await self.bot.get_volume_profile(symbol)
            elif hasattr(self.bot, "volume_profile_calculator"):
                return await self.bot.volume_profile_calculator.get_latest_profile(
                    symbol
                )
            else:
                return {}
        except Exception as e:
            logger.error(f"get_volume_profile_data error: {e}")
            return {}

    async def get_mtf_trends(self, symbol: str) -> Dict:
        """Получение Multi-Timeframe трендов"""
        try:
            trends = {}

            if not hasattr(self.bot, "multitf_filter"):
                return trends

            mtf = self.bot.multitf_filter

            for tf in ["1h", "4h", "1d"]:
                try:
                    # Получаем klines
                    klines = await mtf.get_klines_from_connector(symbol, tf, 200)
                    if not klines:
                        trends[tf] = {"trend": "UNKNOWN", "strength": 0}
                        continue

                    # Анализируем
                    if hasattr(mtf, "mtf_analyzer"):
                        result = await mtf.mtf_analyzer.analyze(klines, tf)
                        trends[tf] = {
                            "trend": result.get("trend", "UNKNOWN"),
                            "strength": result.get("strength", 0),
                        }
                    else:
                        trends[tf] = {"trend": "UNKNOWN", "strength": 0}

                except Exception as e:
                    logger.error(f"MTF {tf} error: {e}")
                    trends[tf] = {"trend": "UNKNOWN", "strength": 0}

            return trends

        except Exception as e:
            logger.error(f"get_mtf_trends error: {e}")
            return {}

    async def get_orderbook_pressure(self, symbol: str) -> Dict:
        """Получение давления orderbook"""
        try:
            if (
                not hasattr(self.bot, "bybit_orderbook_ws")
                or not self.bot.bybit_orderbook_ws
            ):
                return {}

            # Проверяем, есть ли метод get_orderbook_snapshot
            if hasattr(self.bot.bybit_orderbook_ws, "get_orderbook_snapshot"):
                snapshot = self.bot.bybit_orderbook_ws.get_orderbook_snapshot()
            elif hasattr(self.bot.bybit_orderbook_ws, "orderbook"):
                snapshot = self.bot.bybit_orderbook_ws.orderbook
            else:
                return {}

            if not snapshot:
                return {}

            bids = snapshot.get("bids", [])
            asks = snapshot.get("asks", [])

            if not bids or not asks:
                return {}

            # Считаем top 50 levels
            bid_vol = sum(float(b[1]) for b in bids[:50])
            ask_vol = sum(float(a[1]) for a in asks[:50])
            total = bid_vol + ask_vol

            if total == 0:
                return {}

            bid_pct = (bid_vol / total) * 100
            ask_pct = (ask_vol / total) * 100
            imbalance = bid_pct - ask_pct

            return {
                "bid_pct": bid_pct,
                "ask_pct": ask_pct,
                "imbalance": imbalance,
                "bid_vol": bid_vol,
                "ask_vol": ask_vol,
            }

        except Exception as e:
            logger.error(f"get_orderbook_pressure error: {e}")
            return {}

    async def get_scenario(self, symbol: str) -> Optional[Dict]:
        """Получение текущего сценария MM"""
        try:
            if not hasattr(self.bot, "unified_scenario_matcher"):
                return None

            # Получаем market data
            market_data = await self.get_market_data(symbol)
            vp_data = await self.get_volume_profile_data(symbol)

            if not market_data or not market_data.get("price"):
                return None

            # Match scenario
            scenario = await self.bot.unified_scenario_matcher.match_scenario(
                symbol=symbol,
                price=market_data.get("price", 0),
                volume_profile=vp_data,
                market_data=market_data,
            )

            return scenario if scenario and scenario.get("score", 0) > 40 else None

        except Exception as e:
            logger.error(f"get_scenario error: {e}")
            return None
