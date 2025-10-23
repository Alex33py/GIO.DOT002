
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Market Overview с интеграцией корреляций
Объединяет /overview + /correlation в один dashboard
"""
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import numpy as np
import os
from ai.gemini_interpreter import GeminiInterpreter


class EnhancedOverview:
    """Расширенный обзор рынка с корреляциями и insights"""

    def __init__(self, bot):
        from config.settings import logger

        self.logger = logger
        self.bot = bot

        # CRITICAL FIX: Инициализация symbols
        self.symbols = getattr(bot, "pairs", [])
        gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini = GeminiInterpreter(gemini_key) if gemini_key else None

        if self.gemini:
            self.logger.info("✅ EnhancedOverview с Gemini 2.0 Flash")
        else:
            self.logger.warning("⚠️ EnhancedOverview без AI (no GEMINI_API_KEY)")
        if not self.symbols:
            self.symbols = [
                "BTCUSDT",
                "ETHUSDT",
                "SOLUSDT",
                "XRPUSDT",
                "ADAUSDT",
                "DOGEUSDT",
                "AVAXUSDT",
                "DOTUSDT",
            ]

    async def generate_full_overview(self) -> str:
        """Генерирует полный обзор рынка с корреляциями"""
        try:
            # 1. Global Market Sentiment
            global_sentiment = await self._get_global_sentiment()

            # 2. Assets Snapshot (топ-8)
            assets_data = await self._get_assets_snapshot()

            # 3. Correlation Matrix (топ-4)
            correlation_data = await self._get_correlation_matrix()

            # 4. Correlation Insights
            insights = self._generate_correlation_insights(correlation_data)

            # ✅ 5. AI Market Analysis (Gemini 2.0)
            ai_analysis = await self._get_ai_analysis(
                global_sentiment, assets_data, correlation_data
            )

            # Форматирование
            return self._format_overview(
                global_sentiment, assets_data, correlation_data, insights, ai_analysis
            )

        except Exception as e:
            self.logger.error(f"Error generating enhanced overview: {e}", exc_info=True)
            return f"❌ Ошибка генерации overview: {str(e)}"

    async def _get_global_sentiment(self) -> Dict:
        """Получить глобальные метрики рынка"""
        try:
            # Подсчет downtrend активов
            downtrend_count = 0
            for symbol in self.symbols:
                mtf = {}
                if hasattr(self.bot, "mtf_cache"):
                    mtf = self.bot.mtf_cache.get(symbol, {})

                if mtf.get("1d", {}).get("trend") == "DOWN":
                    downtrend_count += 1

            # Total volume из tracked активов
            total_volume = 0
            btc_price = 0
            eth_price = 0

            for symbol in self.symbols[:2]:  # BTC, ETH
                try:
                    ticker = await self.bot.bybit_connector.get_ticker(symbol)
                    if ticker:
                        volume = float(ticker.get("turnover24h", 0))
                        total_volume += volume

                        if symbol == "BTCUSDT":
                            btc_price = float(ticker.get("lastPrice", 0))
                        elif symbol == "ETHUSDT":
                            eth_price = float(ticker.get("lastPrice", 0))
                except:
                    pass

            # Market cap (примерная оценка)
            btc_market_cap = btc_price * 19_500_000  # BTC supply
            eth_market_cap = eth_price * 120_000_000  # ETH supply
            estimated_market_cap = (
                btc_market_cap + eth_market_cap
            ) * 2  # x2 для остальных

            # BTC dominance (примерная)
            btc_dominance = (
                (btc_market_cap / estimated_market_cap * 100)
                if estimated_market_cap > 0
                else 50
            )
            eth_dominance = (
                (eth_market_cap / estimated_market_cap * 100)
                if estimated_market_cap > 0
                else 18
            )

            return {
                "market_cap": estimated_market_cap,
                "total_volume": total_volume,
                "btc_dominance": btc_dominance,
                "eth_dominance": eth_dominance,
                "downtrend_count": downtrend_count,
                "total_assets": len(self.symbols),
                "market_cap_change": 0,  # TODO: Calculate from historical data
            }
        except Exception as e:
            self.logger.error(f"Error getting global sentiment: {e}")
            return {}

    async def _get_assets_snapshot(self) -> List[Dict]:
        """Получить snapshot всех активов"""
        tasks = []
        for symbol in self.symbols:
            tasks.append(self._get_asset_data(symbol))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, dict) and r]

    async def _get_asset_data(self, symbol: str) -> Dict:
        """Получить данные для одного актива"""
        try:
            # Цена
            ticker = await self.bot.bybit_connector.get_ticker(symbol)
            if not ticker:
                return {}

            price = float(ticker.get("lastPrice", 0))
            price_change = float(ticker.get("price24hPcnt", 0)) * 100

            # CVD - используем метод get_cvd из OrderbookAnalyzer с fallback
            cvd = 0
            try:
                if hasattr(self.bot, "orderbook_analyzer"):
                    cvd_data = await self.bot.orderbook_analyzer.get_cvd(symbol)
                    cvd = cvd_data.get("cvd_pct", 0)
                    self.logger.debug(f"✅ CVD для {symbol}: {cvd}%")

                    # ✅ Fallback: если CVD = 0, пробуем получить напрямую из Order Book
                    if cvd == 0:
                        try:
                            ob = await self.bot.bybit_connector.get_orderbook(
                                symbol, limit=50
                            )
                            if ob and "bids" in ob and "asks" in ob:
                                bids_vol = sum([float(b[1]) for b in ob["bids"][:20]])
                                asks_vol = sum([float(a[1]) for a in ob["asks"][:20]])
                                total_vol = bids_vol + asks_vol

                                if total_vol > 0:
                                    cvd = ((bids_vol - asks_vol) / total_vol) * 100
                                    self.logger.debug(
                                        f"✅ Fallback CVD для {symbol}: {cvd}%"
                                    )
                        except Exception as fb_error:
                            self.logger.debug(
                                f"Fallback CVD error for {symbol}: {fb_error}"
                            )

            except Exception as cvd_error:
                self.logger.debug(f"CVD error for {symbol}: {cvd_error}")
                cvd = 0

            # Market Regime
            regime = "RANGE"
            if hasattr(self.bot, "market_structure"):
                regime_data = self.bot.market_structure.get(symbol, {})
                regime = regime_data.get("regime", "RANGE")

            return {
                "symbol": symbol,
                "price": price,
                "price_change": price_change,
                "cvd": cvd,
                "regime": regime,
            }
        except Exception as e:
            self.logger.error(
                f"Error getting asset data for {symbol}: {e}", exc_info=True
            )
            return {}

    async def _get_correlation_matrix(self) -> Dict:
        """Получить матрицу корреляций"""
        try:
            # Используем существующий CorrelationAnalyzer
            if hasattr(self.bot, "correlation_handler") and hasattr(
                self.bot.correlation_handler, "correlation_analyzer"
            ):
                correlations = await self.bot.correlation_handler.correlation_analyzer.calculate_correlations(
                    self.symbols[:4]
                )
                return correlations

            # Fallback: простая корреляция
            return await self._calculate_simple_correlations()
        except Exception as e:
            self.logger.error(f"Error calculating correlations: {e}")
            return {}

    async def _calculate_simple_correlations(self) -> Dict:
        """Простая корреляция на основе изменений цен"""
        top_symbols = self.symbols[:4]  # BTC, ETH, SOL, XRP

        price_changes = {}
        for symbol in top_symbols:
            try:
                ticker = await self.bot.bybit_connector.get_ticker(
                    symbol
                )  # ✅ ВИПРАВЛЕНО
                price_changes[symbol] = float(ticker.get("price24hPcnt", 0))
            except:
                price_changes[symbol] = 0

        # Упрощенная корреляция
        correlations = {}
        for s1 in top_symbols:
            correlations[s1] = {}
            for s2 in top_symbols:
                if s1 == s2:
                    correlations[s1][s2] = 1.0
                else:
                    # Корреляция на основе знака изменения
                    sign1 = 1 if price_changes[s1] > 0 else -1
                    sign2 = 1 if price_changes[s2] > 0 else -1
                    base_corr = 0.7 if sign1 == sign2 else 0.3
                    correlations[s1][s2] = base_corr

        return correlations

    def _generate_correlation_insights(self, corr_data: Dict) -> List[Dict]:
        """Генерировать insights по корреляциям"""
        insights = []

        if not corr_data:
            return insights

        # Анализ сильных корреляций
        processed_pairs = set()

        for s1, corrs in corr_data.items():
            for s2, corr_val in corrs.items():
                pair_key = tuple(sorted([s1, s2]))

                if s1 != s2 and pair_key not in processed_pairs:
                    processed_pairs.add(pair_key)

                    if corr_val > 0.8:
                        insights.append(
                            {
                                "pair": f"{s1.replace('USDT', '')}-{s2.replace('USDT', '')}",
                                "correlation": corr_val,
                                "strength": "Strong positive",
                                "emoji": "🔥",
                                "interpretation": "Движутся синхронно (↓ confidence сигналов)",
                            }
                        )
                    elif 0.6 <= corr_val <= 0.8:
                        insights.append(
                            {
                                "pair": f"{s1.replace('USDT', '')}-{s2.replace('USDT', '')}",
                                "correlation": corr_val,
                                "strength": "Moderate",
                                "emoji": "🟡",
                                "interpretation": "Умеренная связь",
                            }
                        )

        return sorted(insights, key=lambda x: x["correlation"], reverse=True)[:3]

    def _format_overview(
        self,
        global_sentiment: Dict,
        assets: List[Dict],
        correlations: Dict,
        insights: List[Dict],
        ai_analysis: str = "",
    ) -> str:
        """Форматирование с краткими подсказками"""

        lines = ["📊 <b>MARKET OVERVIEW</b>", "━━━━━━━━━━━━━━━━━━━━━━", ""]

        # 1. Global Market Sentiment
        lines.append("🌍 <b>GLOBAL MARKET SENTIMENT</b>")
        if global_sentiment:
            market_cap = global_sentiment.get("market_cap", 0) / 1e12
            volume = global_sentiment.get("total_volume", 0) / 1e9
            btc_dom = global_sentiment.get("btc_dominance", 0)
            eth_dom = global_sentiment.get("eth_dominance", 0)
            down_count = global_sentiment.get("downtrend_count", 0)
            total = global_sentiment.get("total_assets", 8)

            trend_emoji = "🔴" if down_count > total / 2 else "🟢"
            trend_text = "Downtrend" if down_count > total / 2 else "Uptrend"

            lines.append(
                f"├─ Market Cap: ${market_cap:.2f}T <i>(капитализация рынка)</i>"
            )
            lines.append(f"├─ Total Volume: ${volume:.1f}B 24h <i>(объём торгов)</i>")
            lines.append(
                f"├─ BTC Dominance: {btc_dom:.1f}% | ETH: {eth_dom:.1f}% <i>(доля в рынке)</i>"
            )
            lines.append(
                f"└─ Trend Breadth: {down_count}/{total} assets {trend_emoji} {trend_text} <i>(активы в даунтренде)</i>"
            )

        lines.extend(["", "━━━━━━━━━━━━━━━━━━━━━━", ""])

        # 2. Assets Snapshot (✅ ИСПРАВЛЕНО: экранирование < и >)
        lines.append("📈 <b>TOP 8 ASSETS SNAPSHOT</b>")
        lines.append(
            "<i>CVD = дисбаланс покупок/продаж (🟢 &gt;+2% покупатели, 🔴 &lt;-2% продавцы)</i>"
        )
        lines.append("")

        for asset in assets:
            symbol = asset.get("symbol", "N/A").replace("USDT", "")
            price = asset.get("price", 0)
            change = asset.get("price_change", 0)
            cvd = asset.get("cvd", 0)
            regime = asset.get("regime", "RANGE")

            # Форматирование цены
            if price >= 1000:
                price_str = f"${price:,.0f}"
            elif price >= 1:
                price_str = f"${price:,.2f}"
            else:
                price_str = f"${price:.4f}"

            # Эмодзи
            arrow = "↗️" if change > 0 else "↘️" if change < 0 else "→"
            cvd_emoji = "🟢" if cvd > 2 else "🔴" if cvd < -2 else "⚪"

            line = f"<code>{symbol:8s}</code> {price_str:>10s} ({change:+.1f}%) {arrow}  │ {regime:5s} │ CVD: {cvd:+.1f}% {cvd_emoji}"
            lines.append(line)

        lines.extend(["", "━━━━━━━━━━━━━━━━━━━━━━", ""])

        # 3. Correlation Matrix (✅ ИСПРАВЛЕНО: экранирование)
        if correlations:
            lines.append("🔗 <b>CORRELATION MATRIX</b>")
            lines.append(
                "<i>(0.8+ сильная связь, 0.5-0.8 умеренная, &lt;0.5 слабая)</i>"
            )
            lines.append("")

            top_4 = list(correlations.keys())[:4]

            # Header
            header = "       " + "  ".join([s.replace("USDT", "")[:3] for s in top_4])
            lines.append(f"<code>{header}</code>")

            # Rows
            for s1 in top_4:
                row_values = [f"{correlations[s1].get(s2, 0):.2f}" for s2 in top_4]
                row = (
                    f"<code>{s1.replace('USDT', '')[:3]}   "
                    + "  ".join(row_values)
                    + "</code>"
                )
                lines.append(row)

            lines.extend(["", ""])

        # 4. Insights
        if insights:
            lines.append("💡 <b>INSIGHTS:</b>")
            for insight in insights:
                lines.append(
                    f"├─ {insight['pair']}: {insight['correlation']:.2f} {insight['emoji']} {insight['strength']}"
                )
                lines.append(f"│  └─ {insight['interpretation']}")

            lines.extend(["", "━━━━━━━━━━━━━━━━━━━━━━", ""])

        # 5. AI Analysis
        if ai_analysis:
            lines.append(" <b>  AI INTERPRETATION  </b>")
            lines.append("")
            lines.append(ai_analysis)
            lines.extend(["", "━━━━━━━━━━━━━━━━━━━━━━", ""])

        # Timestamp + Подсказки
        now = datetime.now().strftime("%H:%M:%S EEST")
        lines.append(f"⏱️ Updated: {now}")
        lines.append("")
        lines.append("<i>💡 RANGE = боковик, TREND = направленное движение</i>")

        return "\n".join(lines)

    async def _get_ai_analysis(
        self, global_sentiment: Dict, assets: List[Dict], correlations: Dict
    ) -> str:
        """Получить AI-анализ от Gemini 2.0 с отладкой"""

        # ✅ Проверка 1: Gemini инициализирован?
        if not self.gemini:
            self.logger.warning("⚠️ Gemini не инициализирован (нет API key)")
            return "⚠️ <i>AI-анализ недоступен (Gemini API не настроен)</i>"

        try:
            # Подсчёт медвежьих активов
            bearish_count = sum(1 for a in assets if a.get("price_change", 0) < -2)
            bullish_count = sum(1 for a in assets if a.get("price_change", 0) > 2)

            # Средний CVD
            avg_cvd = (
                sum(a.get("cvd", 0) for a in assets) / len(assets) if assets else 0
            )

            self.logger.info(
                f"📊 AI Analysis: bearish={bearish_count}, bullish={bullish_count}, avg_cvd={avg_cvd:.1f}%"
            )

            # Данные для Gemini
            prompt_data = {
                "symbol": "MARKET_OVERVIEW",
                "cvd": avg_cvd,
                "funding_rate": 0,
                "open_interest": global_sentiment.get("total_volume", 0),
                "ls_ratio": bullish_count / max(bearish_count, 1),
                "orderbook_pressure": avg_cvd,
                "whale_activity": [],
            }

            # ✅ Проверка 2: Запрос к Gemini
            self.logger.info("🤖 Запрос к Gemini API...")
            ai_text = await self.gemini.interpret_metrics(prompt_data)

            # ✅ Проверка 3: Получен ответ?
            if ai_text and len(ai_text.strip()) > 0:
                self.logger.info(
                    f"✅ Gemini analysis получен (длина: {len(ai_text)} символов)"
                )
                return ai_text
            else:
                self.logger.warning("⚠️ Gemini вернул пустой ответ")
                return self._generate_fallback_analysis(
                    avg_cvd, bearish_count, bullish_count
                )

        except Exception as e:
            self.logger.error(f"❌ Gemini analysis error: {e}", exc_info=True)
            return self._generate_fallback_analysis(
                sum(a.get("cvd", 0) for a in assets) / len(assets) if assets else 0,
                sum(1 for a in assets if a.get("price_change", 0) < -2),
                sum(1 for a in assets if a.get("price_change", 0) > 2),
            )

    def _generate_fallback_analysis(
        self, avg_cvd: float, bearish_count: int, bullish_count: int
    ) -> str:
        """Fallback-анализ при недоступности Gemini"""

        if avg_cvd < -10:
            sentiment = "📉 Сильное медвежье давление"
            advice = "Рассмотрите шорт-позиции или ждите подтверждения разворота"
        elif avg_cvd > 10:
            sentiment = "📈 Сильное бычье давление"
            advice = "Лонг-позиции предпочтительнее, но следите за перегревом"
        else:
            sentiment = "⚖️ Рынок в балансе"
            advice = "Торговля внутри диапазона, ожидайте прорыва"

        return f"""<b>🤖 ЛОКАЛЬНЫЙ АНАЛИЗ</b>

{sentiment}
├─ Средний CVD: {avg_cvd:+.1f}%
├─ Медвежьих активов: {bearish_count}
└─ Бычьих активов: {bullish_count}

💡 Рекомендация: {advice}

<i>⚠️ AI-анализ от Gemini временно недоступен</i>"""
