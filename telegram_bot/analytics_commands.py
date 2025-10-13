# -*- coding: utf-8 -*-
"""
Telegram Analytics Commands
Команды для просмотра аналитики сигналов
"""

from typing import Optional
from telegram import Update
from telegram.ext import ContextTypes

from analytics.signal_analytics import SignalAnalytics
from config.settings import logger


class AnalyticsCommands:
    """Класс для обработки команд аналитики"""

    def __init__(self):
        self.analytics = SignalAnalytics()
        logger.info("✅ AnalyticsCommands инициализирован")

    async def stats_overall(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Команда /stats - Общая статистика
        Использование: /stats [days]
        Пример: /stats 7
        """
        try:
            # Получаем период (по умолчанию 30 дней)
            days = 30
            if context.args and len(context.args) > 0:
                try:
                    days = int(context.args[0])
                    if days < 1 or days > 365:
                        days = 30
                except:
                    days = 30

            # Получаем статистику
            stats = self.analytics.get_overall_stats(days)

            if stats["total_signals"] == 0:
                await update.message.reply_text(
                    f"📊 За последние {days} дней нет закрытых сигналов",
                    parse_mode="HTML"
                )
                return

            # Форматируем сообщение
            message = f"""
📊 <b>ОБЩАЯ СТАТИСТИКА</b>
<i>За последние {days} дней</i>

━━━━━━━━━━━━━━━━━━━
📈 <b>Сигналы:</b>
├ Всего: {stats['total_signals']}
├ ✅ Прибыльных: {stats['winning']}
├ ❌ Убыточных: {stats['losing']}
└ 📊 Win Rate: <b>{stats['win_rate']:.1f}%</b>

💰 <b>Доходность:</b>
├ Средний ROI: <b>{stats['avg_roi']:+.2f}%</b>
├ Макс. прибыль: +{stats['max_profit']:.2f}%
└ Макс. убыток: {stats['max_loss']:.2f}%

📊 <b>Метрики:</b>
├ Ср. качество: {stats['avg_quality']:.1f}/100
├ Ср. R/R: {stats['avg_rr']:.2f}
├ Символов торговано: {stats['symbols_traded']}
└ Сценариев использовано: {stats['scenarios_used']}

━━━━━━━━━━━━━━━━━━━
<i>Используйте /stats_scenarios для детальной статистики</i>
"""

            await update.message.reply_text(message, parse_mode="HTML")

        except Exception as e:
            logger.error(f"❌ Ошибка /stats: {e}")
            await update.message.reply_text(
                "❌ Ошибка получения статистики",
                parse_mode="HTML"
            )

    async def stats_scenarios(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Команда /stats_scenarios - Статистика по сценариям
        Использование: /stats_scenarios [days]
        """
        try:
            days = 30
            if context.args and len(context.args) > 0:
                try:
                    days = int(context.args[0])
                except:
                    days = 30

            stats = self.analytics.get_stats_by_scenario(days)

            if not stats:
                await update.message.reply_text(
                    f"📊 За последние {days} дней нет данных по сценариям",
                    parse_mode="HTML"
                )
                return

            # Сортируем по win_rate
            sorted_scenarios = sorted(
                stats.items(),
                key=lambda x: x[1]["win_rate"],
                reverse=True
            )

            message = f"""
🎯 <b>СТАТИСТИКА ПО СЦЕНАРИЯМ</b>
<i>За последние {days} дней</i>

━━━━━━━━━━━━━━━━━━━
"""

            for scenario_id, data in sorted_scenarios[:10]:  # Топ-10
                message += f"""
<b>{scenario_id}</b>
├ Сигналов: {data['total_signals']} (✅{data['winning']}/❌{data['losing']})
├ Win Rate: <b>{data['win_rate']:.1f}%</b>
├ Ср. ROI: {data['avg_roi']:+.2f}%
├ Качество: {data['avg_quality']:.1f}/100
└ R/R: {data['avg_rr']:.2f}

"""

            message += "━━━━━━━━━━━━━━━━━━━"

            await update.message.reply_text(message, parse_mode="HTML")

        except Exception as e:
            logger.error(f"❌ Ошибка /stats_scenarios: {e}")
            await update.message.reply_text(
                "❌ Ошибка получения статистики по сценариям",
                parse_mode="HTML"
            )

    async def stats_strategies(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Команда /stats_strategies - Статистика по стратегиям
        """
        try:
            days = 30
            if context.args and len(context.args) > 0:
                try:
                    days = int(context.args[0])
                except:
                    days = 30

            stats = self.analytics.get_stats_by_strategy(days)

            if not stats:
                await update.message.reply_text(
                    f"📊 За последние {days} дней нет данных по стратегиям",
                    parse_mode="HTML"
                )
                return

            # Emoji для стратегий
            strategy_emoji = {
                "momentum": "🚀",
                "breakout": "💥",
                "mean_reversion": "🔄",
                "counter_trend": "↩️",
                "squeeze": "🎯",
            }

            message = f"""
📈 <b>СТАТИСТИКА ПО СТРАТЕГИЯМ</b>
<i>За последние {days} дней</i>

━━━━━━━━━━━━━━━━━━━
"""

            for strategy, data in sorted(
                stats.items(),
                key=lambda x: x[1]["win_rate"],
                reverse=True
            ):
                emoji = strategy_emoji.get(strategy, "📊")
                message += f"""
{emoji} <b>{strategy.upper()}</b>
├ Сигналов: {data['total_signals']} (✅{data['winning']})
├ Win Rate: <b>{data['win_rate']:.1f}%</b>
├ Ср. ROI: {data['avg_roi']:+.2f}%
├ Качество: {data['avg_quality']:.1f}/100
└ Символов: {data['symbols_count']}

"""

            message += "━━━━━━━━━━━━━━━━━━━"

            await update.message.reply_text(message, parse_mode="HTML")

        except Exception as e:
            logger.error(f"❌ Ошибка /stats_strategies: {e}")
            await update.message.reply_text(
                "❌ Ошибка получения статистики по стратегиям",
                parse_mode="HTML"
            )

    async def stats_regimes(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Команда /stats_regimes - Статистика по рыночным режимам
        """
        try:
            days = 30
            if context.args and len(context.args) > 0:
                try:
                    days = int(context.args[0])
                except:
                    days = 30

            stats = self.analytics.get_stats_by_market_regime(days)

            if not stats:
                await update.message.reply_text(
                    f"📊 За последние {days} дней нет данных по режимам",
                    parse_mode="HTML"
                )
                return

            # Emoji для режимов
            regime_emoji = {
                "trending": "📈",
                "ranging": "↔️",
                "volatile": "🌪️",
                "breakout": "💥",
                "squeeze": "🎯",
            }

            message = f"""
🌐 <b>СТАТИСТИКА ПО РЫНОЧНЫМ РЕЖИМАМ</b>
<i>За последние {days} дней</i>

━━━━━━━━━━━━━━━━━━━
"""

            for regime, data in sorted(
                stats.items(),
                key=lambda x: x[1]["win_rate"],
                reverse=True
            ):
                emoji = regime_emoji.get(regime, "📊")
                best_strategy = data.get("best_strategy", "N/A")
                best_wr = data.get("best_strategy_win_rate", 0)

                message += f"""
{emoji} <b>{regime.upper()}</b>
├ Сигналов: {data['total_signals']} (✅{data['winning']})
├ Win Rate: <b>{data['win_rate']:.1f}%</b>
├ Лучшая стратегия: <b>{best_strategy}</b>
└ Win Rate стратегии: {best_wr:.1f}%

"""

            message += "━━━━━━━━━━━━━━━━━━━"

            await update.message.reply_text(message, parse_mode="HTML")

        except Exception as e:
            logger.error(f"❌ Ошибка /stats_regimes: {e}")
            await update.message.reply_text(
                "❌ Ошибка получения статистики по режимам",
                parse_mode="HTML"
            )

    async def stats_top(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Команда /stats_top - Топ-5 лучших сценариев
        """
        try:
            days = 30
            if context.args and len(context.args) > 0:
                try:
                    days = int(context.args[0])
                except:
                    days = 30

            top_scenarios = self.analytics.get_top_performing_scenarios(days, limit=5)

            if not top_scenarios:
                await update.message.reply_text(
                    f"📊 За последние {days} дней нет данных",
                    parse_mode="HTML"
                )
                return

            message = f"""
🏆 <b>ТОП-5 ЛУЧШИХ СЦЕНАРИЕВ</b>
<i>За последние {days} дней (мин. 5 сигналов)</i>

━━━━━━━━━━━━━━━━━━━
"""

            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

            for i, scenario in enumerate(top_scenarios):
                medal = medals[i] if i < len(medals) else f"{i+1}️⃣"
                message += f"""
{medal} <b>{scenario['scenario_id']}</b>
├ Win Rate: <b>{scenario['win_rate']:.1f}%</b>
├ Сигналов: {scenario['total_signals']} (✅{scenario['winning']})
├ Ср. ROI: {scenario['avg_roi']:+.2f}%
└ Качество: {scenario['avg_quality']:.1f}/100

"""

            message += "━━━━━━━━━━━━━━━━━━━"

            await update.message.reply_text(message, parse_mode="HTML")

        except Exception as e:
            logger.error(f"❌ Ошибка /stats_top: {e}")
            await update.message.reply_text(
                "❌ Ошибка получения топ сценариев",
                parse_mode="HTML"
            )


# Экспорт
__all__ = ["AnalyticsCommands"]
