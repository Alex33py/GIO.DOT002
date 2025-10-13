#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Alerts System для GIO Crypto Bot v3.0
Интеллектуальная система алертов с:
- Автоматическим мониторингом всех пар
- Защитой от спама (cooldown + throttling)
- Градацией важности
- Адаптивными порогами для крипто-рынка
- Мониторингом новостей, ликвидаций, всплесков объёмов

Версия: 3.0
Дата: 2025-10-12
"""

import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class EnhancedAlertsSystem:
    """
    Расширенная система алертов с автоматическим мониторингом

    Features:
    - L2 Orderbook дисбаланс (с адаптивными порогами 85-90%)
    - Критичные новости (каждые 5 минут)
    - Крупные ликвидации (>$100K)
    - Всплески объёмов (>3x среднего)
    - Смена сценариев Market Maker
    - Пробои Volume Profile уровней
    """

    def __init__(self, bot_instance, telegram_handler=None, tracked_symbols=None):
        """
        Инициализация системы алертов

        Args:
            bot_instance: Ссылка на главный экземпляр бота
            telegram_handler: Telegram handler для отправки уведомлений
            tracked_symbols: Список отслеживаемых пар (по умолчанию из config)
        """
        self.bot = bot_instance
        self.telegram_handler = telegram_handler

        # Список отслеживаемых пар
        if tracked_symbols:
            self.tracked_symbols = tracked_symbols
        elif (
            hasattr(bot_instance, "config") and "tracked_symbols" in bot_instance.config
        ):
            self.tracked_symbols = bot_instance.config["tracked_symbols"]
        else:
            # По умолчанию
            self.tracked_symbols = ["BTCUSDT", "ETHUSDT", "XRPUSDT"]

        # ========== ПАРАМЕТРЫ АЛЕРТОВ (АДАПТИВНЫЕ ДЛЯ КРИПТО) ==========
        self.config = {
            # L2 Orderbook
            "l2_normal_threshold": 85.0,  # Сильный дисбаланс (85-90%)
            "l2_extreme_threshold": 90.0,  # Экстремальный (>90%)
            # Ликвидации
            "liquidation_min_usd": 100000,  # Минимум $100K
            # Всплески объёмов
            "volume_spike_multiplier": 3.0,  # 3x от среднего
            # Новости
            "news_critical_keywords": [
                "SEC",
                "ETF",
                "lawsuit",
                "hack",
                "regulation",
                "ban",
                "approval",
                "crash",
                "surge",
                "破產",
                "investigation",
                "fraud",
                "bankruptcy",
            ],
            # Throttling (защита от спама)
            "l2_cooldown": 300,  # 5 минут между L2 алертами
            "mm_cooldown": 600,  # 10 минут между MM алертами
            "vp_cooldown": 900,  # 15 минут между VP алертами
            "liq_cooldown": 60,  # 1 минута между liquidation алертами
            "vol_cooldown": 60,  # 1 минута между volume spike алертами
            "news_cooldown": 300,  # 5 минут между news алертами
            # Интервалы мониторинга
            "monitoring_interval": 30,  # Основной цикл: 30 секунд
            "news_check_interval": 300,  # Проверка новостей: 5 минут
        }

        # Хранение времени последних алертов (для throttling)
        self.last_alert_time = defaultdict(lambda: 0)

        # Статистика алертов
        self.alert_stats = {
            "l2_imbalance": 0,
            "liquidations": 0,
            "volume_spike": 0,
            "news": 0,
            "mm_scenario": 0,
            "vp_break": 0,
            "total_sent": 0,
            "blocked_by_cooldown": 0,
            "blocked_by_threshold": 0,
        }

        # Кэш данных
        self.volume_history = {}  # Для расчёта среднего объёма
        self.last_news_check = 0  # Timestamp последней проверки новостей

        # Флаг работы
        self.is_running = False

        logger.info("✅ EnhancedAlertsSystem инициализирован")
        logger.info(f"   • Отслеживаемые пары: {len(self.tracked_symbols)}")
        logger.info(f"   • L2 порог (обычный): {self.config['l2_normal_threshold']}%")
        logger.info(
            f"   • L2 порог (экстремальный): {self.config['l2_extreme_threshold']}%"
        )
        logger.info(f"   • L2 Cooldown: {self.config['l2_cooldown']}s")

    async def start_monitoring(self):
        """
        Запуск автоматического мониторинга всех пар

        Основной цикл проверяет каждые 30 секунд:
        - L2 дисбаланс orderbook (все пары)
        - Критичные новости (раз в 5 минут)
        - Опционально: ликвидации и всплески объёмов
        """
        if self.is_running:
            logger.warning("⚠️ EnhancedAlertsSystem уже запущен")
            return

        self.is_running = True

        logger.info(
            f"🚨 Запуск мониторинга Enhanced Alerts для "
            f"{len(self.tracked_symbols)} пар: {', '.join(self.tracked_symbols)}"
        )

        cycle_count = 0

        while self.is_running:
            try:
                cycle_count += 1
                cycle_start = time.time()

                logger.debug(f"🔄 Enhanced Alerts цикл #{cycle_count}")

                # ========== 1️⃣ ПРОВЕРКА L2 ДИСБАЛАНСА ДЛЯ ВСЕХ ПАР ==========
                for symbol in self.tracked_symbols:
                    try:
                        await self.check_l2_imbalance_from_market_data(symbol)
                    except Exception as e:
                        logger.error(f"❌ Ошибка check_l2_imbalance для {symbol}: {e}")

                # ========== 2️⃣ ПРОВЕРКА НОВОСТЕЙ (раз в 5 минут) ==========
                try:
                    await self.check_news_alerts()
                except Exception as e:
                    logger.error(f"❌ Ошибка check_news_alerts: {e}")

                # ========== 3️⃣ ОПЦИОНАЛЬНО: ЛИКВИДАЦИИ И ОБЪЁМЫ ==========
                # Раскомментируйте если хотите мониторить:
                # for symbol in self.tracked_symbols:
                #     try:
                #         await self.check_liquidations(symbol)
                #     except Exception as e:
                #         logger.error(f"❌ Ошибка check_liquidations для {symbol}: {e}")
                #
                #     try:
                #         await self.check_volume_spike(symbol)
                #     except Exception as e:
                #         logger.error(f"❌ Ошибка check_volume_spike для {symbol}: {e}")

                # Расчёт времени выполнения цикла
                cycle_duration = time.time() - cycle_start
                logger.debug(
                    f"✅ Enhanced Alerts цикл #{cycle_count} завершён за "
                    f"{cycle_duration:.2f}s"
                )

                # Ожидание перед следующим циклом
                sleep_time = max(1, self.config["monitoring_interval"] - cycle_duration)
                logger.debug(f"⏳ Enhanced Alerts: ожидание {sleep_time:.0f} секунд...")
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                logger.info("🛑 Мониторинг остановлен (CancelledError)")
                break

            except Exception as e:
                logger.error(
                    f"❌ Критическая ошибка в цикле мониторинга "
                    f"Enhanced Alerts: {e}",
                    exc_info=True,
                )
                await asyncio.sleep(60)

    async def check_l2_imbalance_from_market_data(self, symbol: str):
        """
        Проверка L2 дисбаланса из bot.market_data
        (данные обновляются через WebSocket)

        Args:
            symbol: Торговая пара (BTCUSDT)
        """
        try:
            # Получаем данные из bot.market_data
            if not hasattr(self.bot, "market_data"):
                logger.debug("⚠️ bot.market_data не найден")
                return

            if symbol not in self.bot.market_data:
                logger.debug(f"⚠️ {symbol}: Нет данных в market_data")
                return

            market_data = self.bot.market_data[symbol]
            imbalance_pct = market_data.get("orderbook_imbalance", 0) * 100

            # Получаем bid/ask давление (если есть)
            bid_pct = market_data.get("bid_pressure_pct", 50.0)
            ask_pct = market_data.get("ask_pressure_pct", 50.0)

            # Вызываем основной метод проверки
            await self.check_l2_imbalance(
                symbol=symbol, imbalance=imbalance_pct, bid_pct=bid_pct, ask_pct=ask_pct
            )

        except Exception as e:
            logger.error(
                f"❌ Ошибка check_l2_imbalance_from_market_data для {symbol}: {e}"
            )

    async def check_l2_imbalance(
        self, symbol: str, imbalance: float, bid_pct: float, ask_pct: float
    ) -> bool:
        """
        Проверка L2 Orderbook дисбаланса с защитой от спама

        Args:
            symbol: Торговая пара (BTCUSDT)
            imbalance: Дисбаланс в % (-100 до +100)
            bid_pct: Процент BID давления
            ask_pct: Процент ASK давления

        Returns:
            bool: True если алерт был отправлен, False если блокирован
        """
        try:
            abs_imbalance = abs(imbalance)

            # 1️⃣ Проверка порога
            if abs_imbalance < self.config["l2_normal_threshold"]:
                # Обычный дисбаланс (<85%) - пропускаем
                self.alert_stats["blocked_by_threshold"] += 1
                logger.debug(
                    f"L2 {symbol}: {abs_imbalance:.1f}% - ниже порога, пропущен"
                )
                return False

            # 2️⃣ Проверка cooldown
            now = time.time()
            alert_key = f"l2_{symbol}"

            if alert_key in self.last_alert_time:
                time_since_last = now - self.last_alert_time[alert_key]

                if time_since_last < self.config["l2_cooldown"]:
                    # Cooldown ещё активен
                    self.alert_stats["blocked_by_cooldown"] += 1
                    remaining = int(self.config["l2_cooldown"] - time_since_last)
                    logger.debug(
                        f"L2 {symbol}: {abs_imbalance:.1f}% - cooldown "
                        f"({remaining}s осталось), пропущен"
                    )
                    return False

            # 3️⃣ Определить уровень важности
            if abs_imbalance >= self.config["l2_extreme_threshold"]:
                emoji = "🚨"
                level = "ЭКСТРЕМАЛЬНЫЙ"
                color = "🔴"
            else:
                emoji = "⚠️"
                level = "СИЛЬНЫЙ"
                color = "🟡"

            # 4️⃣ Определить направление
            if imbalance > 0:
                direction = "📈 BUY PRESSURE"
                side_color = "🟢"
                pressure_text = "Сильное давление покупок"
            else:
                direction = "📉 SELL PRESSURE"
                side_color = "🔴"
                pressure_text = "Сильное давление продаж"

            # 5️⃣ Формирование сообщения
            message = f"""{emoji} L2 ORDERBOOK - {level} ДИСБАЛАНС

{color} Пара: {symbol}
├─ Дисбаланс: {abs_imbalance:.1f}%
├─ Направление: {direction}
└─ Распределение:
   • BID: {bid_pct:.1f}%
   • ASK: {ask_pct:.1f}%

{side_color} {pressure_text}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""

            # 6️⃣ Отправить алерт
            success = await self.send_alert("l2_imbalance", message, priority="high")

            if success:
                self.last_alert_time[alert_key] = now
                logger.info(
                    f"✅ L2 Alert отправлен: {symbol} {imbalance:+.1f}% ({level})"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Ошибка check_l2_imbalance: {e}", exc_info=True)
            return False

    async def check_news_alerts(self):
        """Проверка критичных новостных событий"""
        try:
            # Throttling: проверяем новости не чаще раз в 5 минут
            current_time = time.time()

            if current_time - self.last_news_check < self.config["news_check_interval"]:
                return

            self.last_news_check = current_time

            logger.debug("🔍 Проверка новостных алертов...")

            # Проверяем наличие кэша новостей
            if not hasattr(self.bot, "news_cache") or not self.bot.news_cache:
                logger.debug("⚠️ Кэш новостей пуст")
                return

            # Анализируем последние новости (за последний час)
            one_hour_ago = datetime.now() - timedelta(hours=1)
            critical_news = []

            for news in self.bot.news_cache:
                # Проверяем время новости
                news_time = news.get("published_at", "")
                if not news_time:
                    continue

                try:
                    # Парсинг timestamp
                    news_dt = datetime.fromisoformat(news_time.replace("Z", "+00:00"))

                    # Фильтр: новости за последний час
                    if news_dt < one_hour_ago:
                        continue

                    # Проверяем критичные ключевые слова
                    title = news.get("title", "").lower()
                    body = news.get("body", "").lower()
                    text = f"{title} {body}"

                    for keyword in self.config["news_critical_keywords"]:
                        if keyword.lower() in text:
                            sentiment = news.get("sentiment", 0.0)
                            critical_news.append(
                                {
                                    "title": news.get("title", "N/A"),
                                    "keyword": keyword,
                                    "sentiment": sentiment,
                                    "time": news_dt.strftime("%H:%M"),
                                    "source": news.get("source", "Unknown"),
                                }
                            )
                            break  # Одна новость = один алерт

                except Exception as e:
                    logger.debug(f"⚠️ Ошибка парсинга новости: {e}")
                    continue

            if critical_news:
                # Throttling
                alert_key = "news_critical"
                if self._should_throttle(alert_key, self.config["news_cooldown"]):
                    return

                # Берём топ-3 критичные новости
                top_news = critical_news[:3]

                message = "🚨 КРИТИЧНЫЕ НОВОСТИ\n\n"
                for idx, news in enumerate(top_news, 1):
                    sentiment_emoji = (
                        "🟢"
                        if news["sentiment"] > 0
                        else "🔴" if news["sentiment"] < 0 else "⚪"
                    )
                    message += (
                        f"{idx}. {news['title'][:80]}...\n"
                        f"   Ключ.слово: {news['keyword']}\n"
                        f"   Тон: {sentiment_emoji} {news['sentiment']:.2f}\n"
                        f"   Источник: {news['source']}\n"
                        f"   Время: {news['time']}\n\n"
                    )

                await self.send_alert("news", message, priority="high")
                logger.info(f"🚨 News Alert: {len(critical_news)} критичных новостей")
            else:
                logger.debug("✅ Критичных новостей не обнаружено")

        except Exception as e:
            logger.error(f"❌ Ошибка check_news_alerts: {e}", exc_info=True)

    async def check_liquidations(self, symbol: str):
        """
        Проверка крупных ликвидаций

        Args:
            symbol: Торговая пара (BTCUSDT)
        """
        try:
            logger.debug(f"🔍 Проверка ликвидаций для {symbol}...")

            # Получаем последние сделки из Bybit
            if not hasattr(self.bot, "bybit_connector"):
                logger.debug("⚠️ bybit_connector не найден")
                return

            trades = await self.bot.bybit_connector.get_trades(symbol, limit=100)

            if not trades:
                logger.debug(f"⚠️ {symbol}: Нет данных о сделках")
                return

            # Анализируем крупные сделки
            current_time = time.time() * 1000  # ms
            large_trades = []

            for trade in trades:
                price = float(trade.get("price", 0))
                qty = float(trade.get("qty", 0))
                trade_time = int(trade.get("time", 0))
                side = trade.get("side", "")

                # Объём сделки в USD
                trade_usd = price * qty

                # Фильтр: сделки > $100k за последние 60 секунд
                if (
                    trade_usd > self.config["liquidation_min_usd"]
                    and (current_time - trade_time) < 60000
                ):

                    large_trades.append(
                        {
                            "price": price,
                            "qty": qty,
                            "usd": trade_usd,
                            "side": side,
                            "time": datetime.fromtimestamp(trade_time / 1000).strftime(
                                "%H:%M:%S"
                            ),
                        }
                    )

            if large_trades:
                # Throttling
                alert_key = f"liq_{symbol}"
                if self._should_throttle(alert_key, self.config["liq_cooldown"]):
                    return

                # Сортируем по объёму
                large_trades.sort(key=lambda x: x["usd"], reverse=True)
                top_trade = large_trades[0]

                emoji = "💥" if top_trade["usd"] > 500000 else "⚠️"
                side_emoji = (
                    "🟢 LONG" if top_trade["side"].upper() == "BUY" else "🔴 SHORT"
                )

                message = (
                    f"{emoji} КРУПНАЯ ЛИКВИДАЦИЯ\n"
                    f"Пара: {symbol}\n"
                    f"Объём: ${top_trade['usd']:,.0f}\n"
                    f"Сторона: {side_emoji}\n"
                    f"Цена: ${top_trade['price']:,.2f}\n"
                    f"Время: {top_trade['time']}\n"
                    f"Всего крупных сделок: {len(large_trades)}"
                )

                await self.send_alert("liquidations", message, priority="high")
                logger.info(
                    f"💥 Liquidation Alert: {symbol} (${top_trade['usd']:,.0f})"
                )
            else:
                logger.debug(f"✅ {symbol}: Крупных ликвидаций не обнаружено")

        except Exception as e:
            logger.error(f"❌ Ошибка check_liquidations: {e}", exc_info=True)

    async def check_volume_spike(self, symbol: str):
        """
        Проверка всплесков объёма торгов

        Args:
            symbol: Торговая пара (BTCUSDT)
        """
        try:
            logger.debug(f"🔍 Проверка всплеска объёма для {symbol}...")

            # Получаем последние свечи
            if not hasattr(self.bot, "bybit_connector"):
                logger.debug("⚠️ bybit_connector не найден")
                return

            candles = await self.bot.bybit_connector.get_klines(
                symbol=symbol, interval="60", limit=24  # 1H  # 24 часа
            )

            if not candles or len(candles) < 10:
                logger.debug(f"⚠️ {symbol}: Недостаточно данных свечей")
                return

            # Рассчитываем средний объём
            volumes = [float(c["volume"]) for c in candles[:-4]]
            avg_volume = sum(volumes) / len(volumes)

            # Текущий объём
            current_volume = float(candles[-1]["volume"])

            # Сохраняем историю
            if symbol not in self.volume_history:
                self.volume_history[symbol] = []

            self.volume_history[symbol].append(
                {"volume": current_volume, "time": time.time()}
            )

            # Держим только последние 100 записей
            if len(self.volume_history[symbol]) > 100:
                self.volume_history[symbol].pop(0)

            # Проверяем всплеск
            spike_ratio = current_volume / avg_volume if avg_volume > 0 else 0

            if spike_ratio > self.config["volume_spike_multiplier"]:
                # Throttling
                alert_key = f"vol_{symbol}"
                if self._should_throttle(alert_key, self.config["vol_cooldown"]):
                    return

                emoji = "🔥" if spike_ratio > 5.0 else "📊"

                message = (
                    f"{emoji} ВСПЛЕСК ОБЪЁМА\n"
                    f"Пара: {symbol}\n"
                    f"Текущий объём: {current_volume:,.0f}\n"
                    f"Средний объём: {avg_volume:,.0f}\n"
                    f"Множитель: {spike_ratio:.2f}x\n"
                    f"Время: {datetime.now().strftime('%H:%M:%S')}"
                )

                await self.send_alert("volume_spike", message, priority="medium")
                logger.info(f"📊 Volume Spike Alert: {symbol} ({spike_ratio:.2f}x)")
            else:
                logger.debug(f"✅ {symbol}: Всплеска объёма нет ({spike_ratio:.2f}x)")

        except Exception as e:
            logger.error(f"❌ Ошибка check_volume_spike: {e}", exc_info=True)

    async def check_mm_scenario_change(
        self,
        symbol: str,
        old_scenario: str,
        new_scenario: str,
        confidence: float,
        phase: str,
    ) -> bool:
        """
        Алерт при смене сценария Market Maker

        Args:
            symbol: Торговая пара
            old_scenario: Предыдущий сценарий
            new_scenario: Новый сценарий
            confidence: Уверенность (0-1)
            phase: Фаза рынка

        Returns:
            bool: True если алерт отправлен
        """
        try:
            # Throttling
            alert_key = f"mm_{symbol}"
            if self._should_throttle(alert_key, self.config["mm_cooldown"]):
                return False

            # Важные сценарии
            important_scenarios = ["Overheat", "Trap", "Reversal", "Squeeze"]

            emoji = "🚨" if new_scenario in important_scenarios else "🎲"

            message = f"""{emoji} СМЕНА СЦЕНАРИЯ МАРКЕТМЕЙКЕРА

💎 Пара: {symbol}

Было: {old_scenario}
   ⬇️
Стало: {new_scenario}

📊 Новая фаза: {phase}
🎯 Уверенность: {confidence*100:.0f}%

{"⚠️ Требует внимания!" if new_scenario in important_scenarios else ""}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""

            success = await self.send_alert("mm_scenario", message, priority="high")

            if success:
                logger.info(
                    f"✅ MM Scenario Alert: {symbol} {old_scenario}→{new_scenario}"
                )
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Ошибка check_mm_scenario_change: {e}", exc_info=True)
            return False

    async def check_volume_profile_break(
        self, symbol: str, level: str, price: float, direction: str
    ) -> bool:
        """
        Алерт при пробое Volume Profile уровня

        Args:
            symbol: Торговая пара
            level: Уровень (POC, VAH, VAL)
            price: Цена пробоя
            direction: Направление (UP/DOWN)

        Returns:
            bool: True если алерт отправлен
        """
        try:
            # Throttling
            alert_key = f"vp_{symbol}_{level}"
            if self._should_throttle(alert_key, self.config["vp_cooldown"]):
                return False

            emoji = "🚀" if direction == "UP" else "⚠️"

            message = f"""{emoji} VOLUME PROFILE BREAKOUT

💎 Пара: {symbol}
├─ Уровень: {level}
├─ Цена: ${price:,.2f}
└─ Направление: {"📈 Пробой вверх" if direction == "UP" else "📉 Пробой вниз"}

{"Возможен рост к следующему уровню" if direction == "UP" else "Возможно снижение к поддержке"}

⏰ {datetime.now().strftime('%H:%M:%S')}
"""

            success = await self.send_alert("vp_break", message, priority="medium")

            if success:
                logger.info(f"✅ VP Break Alert: {symbol} {level} {direction}")
                return True

            return False

        except Exception as e:
            logger.error(f"❌ Ошибка check_volume_profile_break: {e}", exc_info=True)
            return False

    async def send_alert(
        self, alert_type: str, message: str, priority: str = "medium"
    ) -> bool:
        """
        Отправка алерта в Telegram

        Args:
            alert_type: Тип алерта (l2_imbalance, news, etc.)
            message: Текст сообщения
            priority: Приоритет (low/medium/high)

        Returns:
            bool: True если успешно отправлен
        """
        try:
            # Обновляем статистику
            if alert_type in self.alert_stats:
                self.alert_stats[alert_type] += 1
            self.alert_stats["total_sent"] += 1

            # Логируем
            logger.info(f"📨 Отправка алерта [{alert_type}]: {message[:50]}...")

            # Отправляем в Telegram
            if self.telegram_handler:
                try:
                    # Проверяем наличие метода send_alert
                    if hasattr(self.telegram_handler, "send_alert"):
                        await self.telegram_handler.send_alert(message)
                    # Или send_message
                    elif hasattr(self.telegram_handler, "send_message"):
                        await self.telegram_handler.send_message(message)
                    # Или прямой вызов Telegram API
                    elif hasattr(self.telegram_handler, "application"):
                        await self.telegram_handler.application.bot.send_message(
                            chat_id=self.telegram_handler.chat_id,
                            text=message,
                            parse_mode="HTML",
                        )
                    else:
                        logger.warning("⚠️ Метод отправки не найден в telegram_handler")
                        return False

                    logger.info(f"✅ Алерт отправлен в Telegram: {alert_type}")
                    return True

                except Exception as e:
                    logger.error(f"❌ Ошибка отправки в Telegram: {e}")
                    return False
            else:
                logger.warning("⚠️ telegram_handler не настроен")
                return False

        except Exception as e:
            logger.error(f"❌ Ошибка send_alert: {e}", exc_info=True)
            return False

    def _should_throttle(self, alert_key: str, cooldown: int) -> bool:
        """
        Проверка throttling (защита от спама)

        Args:
            alert_key: Ключ алерта (l2_BTCUSDT)
            cooldown: Cooldown в секундах

        Returns:
            True если нужно пропустить, False если можно отправить
        """
        current_time = time.time()
        last_time = self.last_alert_time.get(alert_key, 0)

        if current_time - last_time < cooldown:
            remaining = cooldown - (current_time - last_time)
            logger.debug(f"⏸️ Throttle: {alert_key} (осталось {remaining:.0f}s)")
            return True  # Пропускаем

        self.last_alert_time[alert_key] = current_time
        return False  # Отправляем

    def get_stats(self) -> Dict:
        """Получить статистику алертов"""
        return self.alert_stats.copy()

    def reset_stats(self):
        """Сбросить статистику"""
        self.alert_stats = {
            "l2_imbalance": 0,
            "liquidations": 0,
            "volume_spike": 0,
            "news": 0,
            "mm_scenario": 0,
            "vp_break": 0,
            "total_sent": 0,
            "blocked_by_cooldown": 0,
            "blocked_by_threshold": 0,
        }
        logger.info("📊 Статистика алертов сброшена")

    async def stop(self):
        """Остановка системы мониторинга"""
        self.is_running = False
        logger.info("🛑 Остановка EnhancedAlertsSystem...")


# Пример использования
if __name__ == "__main__":
    # Тестирование
    import asyncio

    async def test_alerts():
        # Создаём mock bot
        class MockBot:
            def __init__(self):
                self.market_data = {}

        bot = MockBot()
        alerts = EnhancedAlertsSystem(bot_instance=bot)

        # Тест 1: Низкий дисбаланс (должен блокироваться)
        result = await alerts.check_l2_imbalance(
            symbol="BTCUSDT", imbalance=72.0, bid_pct=72.0, ask_pct=28.0
        )
        print(f"Тест 1 (72%): {'Отправлен' if result else 'Блокирован'}")

        # Тест 2: Высокий дисбаланс (должен пройти)
        result = await alerts.check_l2_imbalance(
            symbol="BTCUSDT", imbalance=88.0, bid_pct=88.0, ask_pct=12.0
        )
        print(f"Тест 2 (88%): {'Отправлен' if result else 'Блокирован'}")

        # Тест 3: Экстремальный (должен пройти)
        result = await alerts.check_l2_imbalance(
            symbol="BTCUSDT", imbalance=93.0, bid_pct=93.0, ask_pct=7.0
        )
        print(f"Тест 3 (93%): {'Отправлен' if result else 'Блокирован'}")

        # Статистика
        stats = alerts.get_stats()
        print(f"\nСтатистика: {stats}")

    asyncio.run(test_alerts())
