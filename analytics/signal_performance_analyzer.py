#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Performance Analyzer
Расширенная аналитика производительности сигналов
"""

import asyncio
import sqlite3
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict
from config.settings import logger, DATA_DIR


class SignalPerformanceAnalyzer:
    """
    Signal Performance Analyzer

    Анализирует производительность торговых сигналов:
    - Win Rate по символам и типам
    - Average ROI, Max Drawdown
    - Sharpe Ratio расчёты
    - Статистика по времени удержания
    """

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.db_path = DATA_DIR / "gio_crypto_bot.db"
        logger.info("✅ SignalPerformanceAnalyzer инициализирован")

    async def get_performance_overview(self, days: int = 30) -> Dict:
        """
        Получить общую статистику производительности

        Args:
            days: За сколько дней анализировать

        Returns:
            {
                "total_signals": 145,
                "closed_signals": 98,
                "active_signals": 47,
                "win_rate": 67.3,
                "avg_roi": 0.89,
                "total_roi": 12.45,
                "best_trade": {...},
                "worst_trade": {...},
                "sharpe_ratio": 1.82,
                "by_symbol": {...},
                "by_type": {...},
                "avg_hold_time_minutes": 263
            }
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff_date.strftime("%Y-%m-%d %H:%M:%S")

            # ✅ ИСПРАВЛЕНО: timestamp вместо created_at
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END) as closed,
                    SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active
                FROM signals
                WHERE timestamp >= ?
            """,
                (cutoff_str,),
            )

            row = cursor.fetchone()
            total_signals = row[0] if row else 0
            closed_signals = row[1] if row else 0
            active_signals = row[2] if row else 0

            # ✅ ИСПРАВЛЕНО: timestamp вместо created_at, close_time вместо exit_time
            cursor.execute(
                """
                SELECT
                    symbol,
                    direction,
                    roi,
                    timestamp,
                    close_time
                FROM signals
                WHERE status = 'closed'
                  AND timestamp >= ?
                  AND roi IS NOT NULL
            """,
                (cutoff_str,),
            )

            closed_trades = cursor.fetchall()
            conn.close()

            if not closed_trades:
                return self._empty_performance()

            # Подсчёты
            wins = sum(1 for trade in closed_trades if trade[2] > 0)
            losses = len(closed_trades) - wins
            win_rate = (wins / len(closed_trades)) * 100 if closed_trades else 0

            rois = [trade[2] for trade in closed_trades]
            avg_roi = sum(rois) / len(rois) if rois else 0
            total_roi = sum(rois)

            # Best/Worst trades
            best_trade = max(closed_trades, key=lambda x: x[2])
            worst_trade = min(closed_trades, key=lambda x: x[2])

            # Sharpe Ratio (упрощённый)
            if rois:
                std_roi = self._calculate_std(rois)
                sharpe_ratio = (avg_roi / std_roi) if std_roi > 0 else 0
            else:
                sharpe_ratio = 0

            # Среднее время удержания
            hold_times = []
            for trade in closed_trades:
                if trade[3] and trade[4]:  # timestamp и close_time
                    try:
                        entry = datetime.fromisoformat(trade[3])
                        exit_time = datetime.fromisoformat(trade[4])
                        hold_minutes = (exit_time - entry).total_seconds() / 60
                        hold_times.append(hold_minutes)
                    except:
                        pass

            avg_hold_time_minutes = (
                sum(hold_times) / len(hold_times) if hold_times else 0
            )

            # По символам
            by_symbol = self._group_by_symbol(closed_trades)

            # По типам (direction)
            by_type = self._group_by_type(closed_trades)

            return {
                "total_signals": total_signals,
                "closed_signals": closed_signals,
                "active_signals": active_signals,
                "win_rate": round(win_rate, 1),
                "wins": wins,
                "losses": losses,
                "avg_roi": round(avg_roi, 2),
                "total_roi": round(total_roi, 2),
                "best_trade": {"symbol": best_trade[0], "roi": round(best_trade[2], 2)},
                "worst_trade": {
                    "symbol": worst_trade[0],
                    "roi": round(worst_trade[2], 2),
                },
                "sharpe_ratio": round(sharpe_ratio, 2),
                "avg_hold_time_minutes": round(avg_hold_time_minutes, 0),
                "by_symbol": by_symbol,
                "by_type": by_type,
            }

        except Exception as e:
            logger.error(f"get_performance_overview error: {e}", exc_info=True)
            return self._empty_performance()

    def _group_by_symbol(self, trades: List) -> Dict:
        """Группировать по символам"""
        grouped = defaultdict(lambda: {"trades": [], "rois": []})

        for trade in trades:
            symbol = trade[0]
            roi = trade[2]
            grouped[symbol]["trades"].append(trade)
            grouped[symbol]["rois"].append(roi)

        result = {}
        for symbol, data in grouped.items():
            rois = data["rois"]
            wins = sum(1 for r in rois if r > 0)
            win_rate = (wins / len(rois)) * 100 if rois else 0
            total_roi = sum(rois)

            result[symbol] = {
                "win_rate": round(win_rate, 1),
                "total_roi": round(total_roi, 2),
                "count": len(rois),
            }

        # Сортировка по total_roi
        result = dict(
            sorted(result.items(), key=lambda x: x[1]["total_roi"], reverse=True)
        )

        return result

    def _group_by_type(self, trades: List) -> Dict:
        """Группировать по типам сигналов"""
        grouped = defaultdict(lambda: {"trades": [], "rois": []})

        for trade in trades:
            direction = trade[1] or "UNKNOWN"
            roi = trade[2]
            grouped[direction]["trades"].append(trade)
            grouped[direction]["rois"].append(roi)

        result = {}
        for direction, data in grouped.items():
            rois = data["rois"]
            wins = sum(1 for r in rois if r > 0)
            win_rate = (wins / len(rois)) * 100 if rois else 0
            total_roi = sum(rois)

            result[direction] = {
                "win_rate": round(win_rate, 1),
                "total_roi": round(total_roi, 2),
                "count": len(rois),
            }

        return result

    def _calculate_std(self, values: List[float]) -> float:
        """Расчёт стандартного отклонения"""
        if not values:
            return 0

        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return variance**0.5

    def format_performance_overview(self, stats: Dict) -> str:
        """Форматировать для Telegram"""
        try:
            lines = []
            lines.append("📊 SIGNAL PERFORMANCE OVERVIEW")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("")

            # Overall stats
            lines.append("📈 OVERALL STATISTICS (Last 30 Days)")
            lines.append(f"├─ Total Signals: {stats['total_signals']}")
            lines.append(f"├─ Closed Signals: {stats['closed_signals']}")
            lines.append(f"├─ Active Signals: {stats['active_signals']}")
            lines.append(
                f"├─ Win Rate: {stats['win_rate']}% ({stats['wins']}/{stats['closed_signals']})"
            )

            # Hold time
            hold_time_hours = stats["avg_hold_time_minutes"] / 60
            hold_time_mins = stats["avg_hold_time_minutes"] % 60
            lines.append(
                f"└─ Avg Hold Time: {int(hold_time_hours)}h {int(hold_time_mins)}m"
            )
            lines.append("")

            # Profitability
            lines.append("💰 PROFITABILITY")
            lines.append(f"├─ Total ROI: {stats['total_roi']:+.2f}%")
            lines.append(f"├─ Avg ROI per Trade: {stats['avg_roi']:+.2f}%")
            lines.append(
                f"├─ Best Trade: {stats['best_trade']['roi']:+.2f}% ({stats['best_trade']['symbol']})"
            )
            lines.append(
                f"├─ Worst Trade: {stats['worst_trade']['roi']:+.2f}% ({stats['worst_trade']['symbol']})"
            )
            lines.append(f"└─ Sharpe Ratio: {stats['sharpe_ratio']}")
            lines.append("")

            # By Symbol
            by_symbol = stats.get("by_symbol", {})
            if by_symbol:
                lines.append("📊 BY SYMBOL")
                for symbol, data in list(by_symbol.items())[:5]:  # Top 5
                    lines.append(
                        f"├─ {symbol}: {data['win_rate']}% WR | {data['total_roi']:+.1f}% ROI ({data['count']} signals)"
                    )
                lines.append("")

            # By Type
            by_type = stats.get("by_type", {})
            if by_type:
                lines.append("🎯 BY SIGNAL TYPE")
                for sig_type, data in by_type.items():
                    lines.append(
                        f"├─ {sig_type}: {data['win_rate']}% WR | {data['total_roi']:+.1f}% ROI"
                    )
                lines.append("")

            lines.append(f"⏱️ Updated: {datetime.now().strftime('%H:%M:%S')}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"format_performance_overview error: {e}")
            return "⚠️ Ошибка форматирования"

    def _empty_performance(self) -> Dict:
        """Пустая статистика"""
        return {
            "total_signals": 0,
            "closed_signals": 0,
            "active_signals": 0,
            "win_rate": 0,
            "wins": 0,
            "losses": 0,
            "avg_roi": 0,
            "total_roi": 0,
            "best_trade": {"symbol": "N/A", "roi": 0},
            "worst_trade": {"symbol": "N/A", "roi": 0},
            "sharpe_ratio": 0,
            "avg_hold_time_minutes": 0,
            "by_symbol": {},
            "by_type": {},
        }
