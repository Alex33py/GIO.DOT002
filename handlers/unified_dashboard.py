#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unified Dashboard Handler для Telegram с LIVE AUTO-UPDATE
"""

import logging
import aiohttp
import sqlite3
import asyncio
import re
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from core.scenario_interpreter import ScenarioInterpreter, get_scenario_emoji
from core.mm_scenarios_generator import MMScenariosGenerator

logger = logging.getLogger(__name__)


def escape_markdown_v2(text: str) -> str:
    """Экранирует специальные символы для MarkdownV2"""
    escape_chars = r"_*[]()~`>#+-=|{}.!"
    return re.sub(f"([{re.escape(escape_chars)}])", r"\\\1", text)


class UnifiedDashboardHandler:
    """Handler для unified dashboard команды с live updates"""

    def __init__(self, bot):
        self.bot = bot
        self.interpreter = ScenarioInterpreter()
        self.generator = MMScenariosGenerator()
        self.live_tasks = {}  # {chat_id: task}

    async def handle_dashboard(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Обрабатывает команду /dashboard [live]"""
        try:
            # Проверяем аргументы команды
            args = context.args or []
            is_live = "live" in args

            if is_live:
                await self._start_live_dashboard(update, context)
            else:
                await self._send_single_dashboard(update, context)

        except Exception as e:
            logger.error(f"Dashboard error: {e}", exc_info=True)
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def _send_single_dashboard(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Отправить обычный dashboard (одноразовый)"""
        try:
            await update.message.reply_text("📊 Загрузка dashboard...")

            dashboard_text = await self._build_dashboard_text()

            # ✅ УБИРАЕМ parse_mode для безопасности
            await update.message.reply_text(dashboard_text)

        except Exception as e:
            logger.error(f"Single dashboard error: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def _start_live_dashboard(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Запустить LIVE dashboard с автообновлением"""
        chat_id = update.effective_chat.id

        # Остановить предыдущую live-сессию если есть
        if chat_id in self.live_tasks:
            self.live_tasks[chat_id].cancel()
            logger.info(f"🛑 Stopped previous live dashboard for chat {chat_id}")

        try:
            # Отправляем первое сообщение
            loading_msg = await update.message.reply_text(
                "📊 Загрузка GIO Dashboard Live..."
            )

            # Генерируем первый dashboard
            dashboard_text = await self._build_dashboard_text()

            # Добавляем индикатор автообновления
            end_time = datetime.now() + timedelta(minutes=60)
            end_time_str = end_time.strftime("%H:%M")
            dashboard_text += f"\n\n🔄 Автообновление: каждые 60 сек | Активно до {end_time_str}"  # ✅ БЕЗ ПОДЧЁРКИВАНИЙ!

            # Обновляем сообщение
            await loading_msg.edit_text(dashboard_text)

            # Запускаем фоновое автообновление
            task = asyncio.create_task(
                self._auto_update_loop(
                    chat_id=chat_id,
                    message_id=loading_msg.message_id,
                    end_time=end_time,
                    context=context,
                )
            )

            self.live_tasks[chat_id] = task

            logger.info(f"✅ Live dashboard started for chat {chat_id}")

        except Exception as e:
            logger.error(f"Start live dashboard error: {e}")
            await update.message.reply_text(f"❌ Ошибка: {e}")

    async def _auto_update_loop(
        self,
        chat_id: int,
        message_id: int,
        end_time: datetime,
        context: ContextTypes.DEFAULT_TYPE,
    ):
        """Фоновый цикл автообновления"""
        try:
            update_count = 0

            while datetime.now() < end_time:
                await asyncio.sleep(60)  # Ждём 60 секунд

                try:
                    update_count += 1
                    time_left = int((end_time - datetime.now()).total_seconds() / 60)

                    # Генерируем новый dashboard
                    dashboard_text = await self._build_dashboard_text()

                    # Добавляем индикатор
                    dashboard_text += f"\n\n🔄 Обновлено #{update_count} | Осталось ~{time_left} мин"  # ✅ БЕЗ ПОДЧЁРКИВАНИЙ!

                    # Обновляем сообщение
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=dashboard_text,
                    )

                    logger.info(
                        f"🔄 Dashboard updated #{update_count} for chat {chat_id}"
                    )

                except BadRequest as e:
                    if "message is not modified" in str(e).lower():
                        logger.debug("Dashboard unchanged, skipping update")
                        continue
                    else:
                        logger.error(f"Update error: {e}")
                        break

                except Exception as e:
                    logger.error(f"Update loop error: {e}")
                    break

        except asyncio.CancelledError:
            logger.info(f"🛑 Live dashboard cancelled for chat {chat_id}")

        except Exception as e:
            logger.error(f"Auto-update loop error: {e}")

        finally:
            # Удаляем задачу из словаря
            if chat_id in self.live_tasks:
                del self.live_tasks[chat_id]
            logger.info(f"🛑 Live dashboard stopped for chat {chat_id}")

    async def _build_dashboard_text(self) -> str:
        """Построить текст dashboard"""
        try:
            # === 1. Market Overview ===
            market_text = await self._get_market_overview()

            # === 2. MM Scenario ===
            scenario_text = await self._get_mm_scenario()

            # === 3. HOT Pairs ===
            hot_pairs_text = await self._get_hot_pairs()

            # === 4. News Summary === ✅ НОВОЕ!
            news_text = await self._get_news_summary()

            # === 5. Whale Activity === ✅ НОВОЕ!
            whale_text = await self._get_whale_activity_summary()

            # === 6. Active Signals ===
            signals_text = self._get_active_signals()

            # === 7. Signal Performance ===
            performance_text = self._get_signal_performance()

            # === Собираем полное сообщение ===
            full_message = f"""
{market_text}

{scenario_text}

{hot_pairs_text}

{news_text}

{whale_text}

{signals_text}

{performance_text}
"""
            return full_message.strip()

        except Exception as e:
            logger.error(f"Build dashboard error: {e}")
            return f"❌ Ошибка построения dashboard: {e}"


    async def _get_market_overview(self) -> str:
        """Получить Market Overview с реальными ценами"""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.binance.com/api/v3/ticker/24hr"
                params = {"symbols": '["BTCUSDT","ETHUSDT"]'}

                async with session.get(url, params=params) as resp:
                    data = await resp.json()

                    btc = next(d for d in data if d["symbol"] == "BTCUSDT")
                    eth = next(d for d in data if d["symbol"] == "ETHUSDT")

                    btc_price = float(btc["lastPrice"])
                    btc_change = float(btc["priceChangePercent"])
                    eth_price = float(eth["lastPrice"])
                    eth_change = float(eth["priceChangePercent"])

                    total_vol = (
                        float(btc["quoteVolume"]) + float(eth["quoteVolume"])
                    ) / 1e9

                    # Эмодзи для изменения цены
                    btc_emoji = "🟢" if btc_change >= 0 else "🔴"
                    eth_emoji = "🟢" if eth_change >= 0 else "🔴"

                    return f"""📊 Market Overview  #
    • BTC: ${btc_price:,.0f} ({btc_emoji}{btc_change:+.1f}%)
    • ETH: ${eth_price:,.0f} ({eth_emoji}{eth_change:+.1f}%)
    • Total Vol: ${total_vol:.1f}B"""

        except Exception as e:
            logger.error(f"Market Overview error: {e}")
            return "⚠️ Market Overview недоступен"

    async def _get_mm_scenario(self) -> str:
        """Получить MM сценарий С РЕАЛЬНЫМИ ДАННЫМИ"""
        try:
            # === ПОЛУЧАЕМ РЕАЛЬНЫЕ ДАННЫЕ ИЗ market_dashboard ===
            logger.info("📊 Fetching REAL market data from market_dashboard...")

            # Используем существующий market_dashboard из бота
            cvd_data = await self.bot.market_dashboard.get_volume_analysis("BTCUSDT")
            sentiment_data = await self.bot.market_dashboard.get_sentiment_pressure(
                "BTCUSDT"
            )

            # ✅ ИСПРАВЛЕНО: ИСПОЛЬЗУЕМ ПРАВИЛЬНЫЕ КЛЮЧИ!
            cvd = cvd_data.get("cvd", 0)
            funding = sentiment_data.get(
                "funding_rate", 0
            )  # ← ✅ ДЕСЯТИЧНАЯ ФОРМА (0.006755)
            ls_ratio = sentiment_data.get(
                "long_short_ratio", 1.0
            )  # ← ✅ БЫЛО "ls_ratio", ДОЛЖНО БЫТЬ "long_short_ratio"!

            logger.info(
                f"✅ REAL DATA FETCHED: CVD={cvd}, Funding={funding}, L/S={ls_ratio}"
            )

            # ✅ ТЕПЕРЬ ДАННЫЕ РЕАЛЬНЫЕ!
            market_data = {
                "cvd": cvd,
                "funding": funding,  # ← ✅ ДЕСЯТИЧНАЯ ФОРМА (0.006755)
                "ratio": ls_ratio,
                "liquidations": sentiment_data.get("liquidations", 5_000_000),
                "institutional": 12.5,
                "wyckoff_phase": "accumulation",
            }

            # Генерируем сценарий на основе РЕАЛЬНЫХ данных
            scenario_data = self.generator.generate_scenario(market_data)

            if not scenario_data:
                return "❌ Ошибка генерации сценария"

            # Интерпретация
            interpretation = self.interpreter.interpret(
                scenario_data["scenario"],
                scenario_data["phase"],
                scenario_data["metrics"],
            )

            emoji = get_scenario_emoji(scenario_data["scenario"])

            # ====================================================
            # ✅ ФОРМАТИРУЕМ MM SCENARIO С ПОДРОБНЫМИ ПОЯСНЕНИЯМИ
            # ====================================================

            # Словарь пояснений для сценариев MM
            mm_scenarios_info = {
                "accumulation": {
                    "emoji": "🟢",
                    "title": "Накопление",
                    "short_desc": "MM собирают позиции по низким ценам",
                    "action": "⏸️ Ожидай пробоя вверх или Spring-теста",
                },
                "distribution": {
                    "emoji": "🔴",
                    "title": "Распределение",
                    "short_desc": "MM распродают позиции по высоким ценам",
                    "action": "🚨 Готовься к развороту вниз",
                },
                "markup": {
                    "emoji": "🚀",
                    "title": "Разметка (Рост)",
                    "short_desc": "MM толкают цену вверх",
                    "action": "🚀 Держи лонги, следи за объёмами",
                },
                "markdown": {
                    "emoji": "📉",
                    "title": "Разметка (Падение)",
                    "short_desc": "MM давят цену вниз",
                    "action": "📉 Избегай лонгов, жди дна",
                },
            }

            # Словарь фаз Wyckoff
            wyckoff_phases_info = {
                "test": "Тестирование поддержки/сопротивления",
                "spring": "Встряска (Spring) — ложный пробой",
                "sos": "Признаки Силы (SOS)",
                "accumulation": "Фаза накопления",
                "distribution": "Фаза распределения",
            }

            # Получаем информацию о сценарии
            scenario_name = scenario_data["scenario"].lower()
            scenario_info = mm_scenarios_info.get(
                scenario_name, mm_scenarios_info["accumulation"]
            )
            phase_desc = wyckoff_phases_info.get(
                scenario_data["phase"].lower(), "Неопределённая фаза"
            )

            # Формируем сообщение С ПОЯСНЕНИЯМИ
            message = (
                f"{emoji} MM Scenario: {scenario_data['scenario'].title()} ({scenario_info['title']})\n\n"
                f"📌 Что это? {scenario_info['short_desc']}\n\n"
                f"📍 Фаза Wyckoff: {scenario_data['phase'].capitalize()}\n"
                f"└─ {phase_desc}\n\n"
                f"💬 Интерпретация:\n{interpretation}\n\n"
                f"🎯 Рекомендация: {scenario_info['action']}\n\n"
                f"📊 Metrics:\n"
                f"• CVD: {scenario_data['metrics']['cvd']}%\n"
                f"• Funding: {scenario_data['metrics']['funding']*100:.2f}%\n"
                f"• L/S Ratio: {scenario_data['metrics']['ratio']}\n"
            )

            # === ДОБАВЛЯЕМ AI INTERPRETATION ОТ GEMINI ===
            logger.info("🤖 Starting Gemini AI interpretation...")

            try:
                from ai.gemini_interpreter import GeminiInterpreter
                from config.settings import GEMINI_API_KEY

                gemini = GeminiInterpreter(api_key=GEMINI_API_KEY)

                # ✅ ИСПРАВЛЕНО: ПЕРЕДАЁМ ПРАВИЛЬНЫЕ КЛЮЧИ!
                dashboard_data = {
                    "scenario": scenario_data["scenario"],  # ← ✅ ДОБАВЛЕНО!
                    "symbol": "BTCUSDT",  # ← ✅ ДОБАВЛЕНО!
                    "cvd": scenario_data["metrics"]["cvd"],
                    "funding_rate": scenario_data["metrics"][
                        "funding"
                    ],  # ← ✅ ДЕСЯТИЧНАЯ ФОРМА (0.006755)
                    "ls_ratio": scenario_data["metrics"]["ratio"],
                    "open_interest": 0,  # ← ✅ ДОБАВЛЕНО!
                    "orderbook_pressure": 0,  # ← ✅ ДОБАВЛЕНО!
                    "whale_activity": [],  # ← ✅ ДОБАВЛЕНО!
                }

                # ✅ DEBUG: ПРОВЕРЯЕМ, ЧТО ПЕРЕДАНО
                logger.debug(f"🔍 dashboard_data для Gemini: {dashboard_data}")

                # ✅ ИСПОЛЬЗУЕМ ПРАВИЛЬНЫЙ МЕТОД С await
                ai_text = await gemini.interpret_metrics(dashboard_data)

                # ====================================================
                # ✅ ФОРМАТИРУЕМ AI INTERPRETATION С ПОЯСНЕНИЯМИ
                # ====================================================

                # CVD интерпретация
                cvd = scenario_data["metrics"]["cvd"]
                if cvd < -20:
                    cvd_emoji = "🔴"
                    cvd_text = "Сильная активность продавцов"
                    cvd_explanation = "Продавцов намного больше, чем покупателей"
                elif cvd > 20:
                    cvd_emoji = "🟢"
                    cvd_text = "Сильная активность покупателей"
                    cvd_explanation = "Покупателей намного больше, чем продавцов"
                else:
                    cvd_emoji = "⚪"
                    cvd_text = "Нейтральный баланс"
                    cvd_explanation = "Покупатели и продавцы примерно равны"

                # Funding интерпретация
                funding = scenario_data["metrics"]["funding"]
                if funding > 0.01:
                    funding_emoji = "🟢"
                    funding_text = "Позитивный Funding"
                    funding_explanation = "Лонги платят шортам → много лонгов"
                elif funding < -0.01:
                    funding_emoji = "🔴"
                    funding_text = "Негативный Funding"
                    funding_explanation = "Шорты платят лонгам → много шортов"
                else:
                    funding_emoji = "⚪"
                    funding_text = "Нейтральный Funding"
                    funding_explanation = "Рынок сбалансирован"

                # L/S Ratio
                ls_ratio = scenario_data["metrics"]["ratio"]
                if ls_ratio > 1:
                    ls_emoji = "🟢"
                    ls_text = "Преобладают лонги"
                else:
                    ls_emoji = "🔴"
                    ls_text = "Преобладают шорты"

                # Рекомендация на основе всех индикаторов
                if cvd < -20 and funding > 0:
                    recommendation = """⚠️ ПРОТИВОРЕЧИВЫЕ СИГНАЛЫ:
                CVD показывает продажи, но Funding позитивный.
                💡 Действие: ⏸️ Жди подтверждения перед входом."""
                elif cvd > 20 and funding > 0:
                    recommendation = """✅ БЫЧЬИ СИГНАЛЫ:
                CVD растёт + Funding позитивный.
                💡 Действие: 🚀 Рассмотри лонг-позиции."""
                else:
                    recommendation = """⏸️ НЕОПРЕДЕЛЁННОСТЬ:
                Сигналы смешанные.
                💡 Действие: Жди подтверждения тренда."""

                # Добавляем к сообщению С ПОЯСНЕНИЯМИ
                message += (
                    f"\n\n AI INTERPRETATION\n"
                    f"{'━' * 30}\n\n"
                    f"📊 Технический анализ:\n\n"
                    f"CVD: {cvd_emoji} {cvd:+.1f}% — {cvd_text}\n"
                    f"└─ {cvd_explanation}\n\n"
                    f"Funding Rate: {funding_emoji} {funding*100:+.2f}% — {funding_text}\n"
                    f"└─ {funding_explanation}\n\n"
                    f"L/S Ratio: {ls_emoji} {ls_ratio:.2f} — {ls_text}\n\n"
                    f"{recommendation}\n\n"
                    f"{'━' * 30}\n\n"
                    f"AI ANALYSIS:\n{ai_text}\n"
                    f"{'━' * 30}\n"
                )

                logger.info("✅ AI Interpretation added successfully")

            except Exception as e:
                logger.error(f"❌ Gemini AI error: {e}", exc_info=True)
                message += f"\n\n⚠️ AI Interpretation недоступна\n"

            return message

        except Exception as e:
            logger.error(f"❌ MM Scenario error: {e}", exc_info=True)
            return f"⚠️ MM Scenario: {e}"

    async def _get_hot_pairs(self) -> str:
        """Получить ТОП-3 пары по объёму"""
        try:
            async with aiohttp.ClientSession() as session:
                url = "https://api.binance.com/api/v3/ticker/24hr"

                async with session.get(url) as resp:
                    data = await resp.json()

                    # Фильтруем USDT пары
                    usdt_pairs = [d for d in data if d["symbol"].endswith("USDT")]

                    # Сортируем по объёму
                    top_pairs = sorted(
                        usdt_pairs, key=lambda x: float(x["quoteVolume"]), reverse=True
                    )[:3]

                    message = "🔥 HOT Pairs\n"
                    for pair in top_pairs:
                        symbol = pair["symbol"]
                        volume = float(pair["quoteVolume"]) / 1e9
                        message += f"• {symbol} - Vol: ${volume:.1f}B\n"

                    return message.strip()

        except Exception as e:
            logger.error(f"HOT Pairs error: {e}")
            return "⚠️ HOT Pairs недоступны"

    def _get_active_signals(self) -> str:
        """Получить активные сигналы из БД"""
        try:
            # ✅ ИСПРАВЛЕНО: правильный путь к БД
            conn = sqlite3.connect("data/gio_crypto_bot.db")
            cursor = conn.cursor()

            # ✅ ИСПРАВЛЕНО: используем существующие колонки
            cursor.execute(
                """
                SELECT symbol, direction, entry_price, tp1
                FROM signals
                WHERE status = 'active'
                ORDER BY timestamp DESC
                LIMIT 3
            """
            )

            signals = cursor.fetchall()
            conn.close()

            if not signals:
                return "📈 Active Signals\n• Нет активных сигналов"

            message = "📈 Active Signals\n"
            for symbol, direction, entry, tp in signals:
                message += f"• {symbol} {direction.upper() if direction else 'N/A'} - Entry: {entry:.0f} | TP: {tp:.0f}\n"

            return message.strip()

        except Exception as e:
            logger.error(f"Active Signals error: {e}")
            return "⚠️ Active Signals недоступны"

    async def _get_news_summary(self) -> str:
        """
        Получить краткую сводку новостей (топ-3)

        Returns:
            Форматированная сводка новостей
        """
        try:
            # Проверяем, есть ли у бота news_analyzer
            if not hasattr(self.bot, 'news_analyzer') or not self.bot.news_analyzer:
                return "📰 News Summary\n⚠️ Новости недоступны"

            # Получаем последние 3 новости
            news_list = await self.bot.news_analyzer.get_latest_news(hours=6, limit=3)

            if not news_list:
                return "📰 News Summary\n⚠️ Нет свежих новостей"

            # Анализируем sentiment
            news_list = await self.bot.news_analyzer.analyze_sentiment(news_list)

            # Рассчитываем общий sentiment
            overall = self.bot.news_analyzer.calculate_overall_sentiment(news_list)

            # Определяем emoji для overall sentiment
            overall_emoji = (
                "🟢" if overall["overall"] == "BULLISH"
                else "🔴" if overall["overall"] == "BEARISH"
                else "🟡"
            )

            # Формируем сообщение
            message_lines = [
                "📰 News Summary",
                f"Overall: {overall_emoji} {overall['overall']} (Score: {overall['score']:+.2f})",
                ""
            ]

            # Добавляем топ-3 новости
            for news in news_list[:3]:
                emoji = news.get("sentiment_emoji", "🟡")
                title = news["title"][:60]  # Обрезаем до 60 символов

                message_lines.append(f"{emoji} {title}...")

            return "\n".join(message_lines)

        except Exception as e:
            logger.error(f"❌ News Summary error: {e}")
            return "📰 News Summary\n⚠️ Ошибка загрузки новостей"

    async def _get_whale_activity_summary(self) -> str:
        """
        Получить сводку китовой активности (крупные сделки за 15 мин)

        Returns:
            Форматированная сводка whale activity
        """
        try:
            # Проверяем, есть ли у бота market_dashboard
            if not hasattr(self.bot, 'market_dashboard'):
                return "🐋 Whale Activity\n⚠️ Данные недоступны"

            # Получаем whale activity для BTC и ETH
            symbols = ["BTCUSDT", "ETHUSDT"]
            total_whales = 0
            whale_trades = []

            for symbol in symbols:
                try:
                    # Получаем крупные сделки
                    whale_data = await self.bot.market_dashboard.get_whale_activity(symbol)

                    if whale_data and 'large_trades' in whale_data:
                        trades = whale_data['large_trades']
                        total_whales += len(trades)

                        # Берём топ-2 крупнейшие сделки
                        sorted_trades = sorted(trades, key=lambda x: x.get('volume', 0), reverse=True)[:2]

                        for trade in sorted_trades:
                            whale_trades.append({
                                'symbol': symbol,
                                'side': trade.get('side', 'unknown'),
                                'volume': trade.get('volume', 0),
                                'price': trade.get('price', 0)
                            })

                except Exception as e:
                    logger.debug(f"⚠️ Whale data for {symbol} unavailable: {e}")
                    continue

            # Формируем сообщение
            if total_whales == 0:
                return "🐋 Whale Activity\n⚪ Нет крупных сделок (15 мин)"

            message_lines = [
                "🐋 Whale Activity",
                f"├─ Крупных сделок: {total_whales} (15 мин)",
                ""
            ]

            # Добавляем топ крупнейшие сделки
            for trade in whale_trades[:3]:
                symbol_clean = trade['symbol'].replace('USDT', '')
                side = trade['side'].upper()
                emoji = "🟢" if side == "BUY" else "🔴"
                volume_k = trade['volume'] / 1000

                message_lines.append(
                    f"{emoji} {symbol_clean} {side} ${volume_k:.0f}K @ ${trade['price']:,.0f}"
                )

            return "\n".join(message_lines).strip()

        except Exception as e:
            logger.error(f"❌ Whale Activity error: {e}")
            return "🐋 Whale Activity\n⚠️ Ошибка загрузки данных"


    def _get_signal_performance(self) -> str:
        """Получить статистику сигналов"""
        try:
            # ✅ ИСПРАВЛЕНО: правильный путь к БД
            conn = sqlite3.connect("data/gio_crypto_bot.db")
            cursor = conn.cursor()

            # Win Rate
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'closed' AND roi > 0 THEN 1 ELSE 0 END) as wins
                FROM signals
                WHERE status = 'closed'
            """
            )

            total, wins = cursor.fetchone()
            win_rate = (wins / total * 100) if total > 0 else 0

            # Avg ROI
            cursor.execute(
                """
                SELECT AVG(roi) FROM signals WHERE status = 'closed' AND roi > 0
            """
            )

            avg_roi = cursor.fetchone()[0] or 0
            conn.close()

            return f"""📉 Signal Performance
        • Win Rate: {win_rate:.0f}%
        • Total Signals: {total}
        • Avg ROI: {avg_roi:+.1f}%"""

        except Exception as e:
            logger.error(f"Performance error: {e}")
            return "⚠️ Performance недоступна"
