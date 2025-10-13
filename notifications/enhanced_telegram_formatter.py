# -*- coding: utf-8 -*-
"""
Enhanced Telegram Message Formatter
Форматирование сообщений с новыми полями из EnhancedScenarioMatcher
"""

from typing import Dict, Optional
from datetime import datetime


class EnhancedTelegramFormatter:
    """Улучшенное форматирование Telegram сообщений"""

    # Emoji для разных элементов
    EMOJI = {
        # Направления
        "LONG": "🟢",
        "SHORT": "🔴",

        # Confidence
        "high": "🔥",
        "medium": "⚡",
        "low": "⚠️",

        # Market Regime
        "trending": "📈",
        "ranging": "↔️",
        "volatile": "🌪️",
        "breakout": "💥",
        "squeeze": "🎯",

        # Strategies
        "momentum": "🚀",
        "breakout": "💥",
        "mean_reversion": "🔄",
        "counter_trend": "↩️",
        "squeeze": "🎯",

        # Risk Profile
        "conservative": "🛡️",
        "moderate": "⚖️",
        "aggressive": "⚔️",

        # Status
        "active": "✅",
        "closed": "🔒",
        "tp_hit": "🎯",
    }

    @staticmethod
    def format_new_signal(signal: Dict) -> str:
        """
        Форматирование нового сигнала с расширенной информацией

        Args:
            signal: Dict с полями сигнала из EnhancedScenarioMatcher

        Returns:
            Отформатированное сообщение для Telegram
        """
        direction = signal.get("direction", "UNKNOWN")
        symbol = signal.get("symbol", "UNKNOWN")

        # Основной заголовок
        direction_emoji = EnhancedTelegramFormatter.EMOJI.get(direction, "⚪")

        message = f"{direction_emoji} <b>НОВЫЙ СИГНАЛ: {direction}</b>\n\n"

        # Базовая информация
        message += f"📊 <b>Пара:</b> {symbol}\n"
        message += f"🆔 <b>Сценарий:</b> {signal.get('scenario_id', 'N/A')}\n"
        message += f"📝 <b>Название:</b> {signal.get('scenario_name', 'N/A')}\n\n"

        # ========== НОВЫЕ ПОЛЯ ==========

        # Strategy
        strategy = signal.get("strategy", "unknown")
        strategy_emoji = EnhancedTelegramFormatter.EMOJI.get(strategy, "📊")
        message += f"{strategy_emoji} <b>Стратегия:</b> {strategy.upper()}\n"

        # Market Regime
        market_regime = signal.get("market_regime", "neutral")
        regime_emoji = EnhancedTelegramFormatter.EMOJI.get(market_regime, "📊")
        message += f"{regime_emoji} <b>Режим рынка:</b> {market_regime.upper()}\n"

        # Confidence
        confidence = signal.get("confidence", "medium")
        confidence_emoji = EnhancedTelegramFormatter.EMOJI.get(confidence, "⚡")
        message += f"{confidence_emoji} <b>Уверенность:</b> {confidence.upper()}\n"

        # Phase
        phase = signal.get("phase", "unknown")
        message += f"🔄 <b>Фаза:</b> {phase.upper()}\n"

        # Risk Profile
        risk_profile = signal.get("risk_profile", "moderate")
        risk_emoji = EnhancedTelegramFormatter.EMOJI.get(risk_profile, "⚖️")
        message += f"{risk_emoji} <b>Риск-профиль:</b> {risk_profile.upper()}\n\n"

        # ========== УРОВНИ ВХОДА/ВЫХОДА ==========
        message += "💰 <b>ЦЕНЫ:</b>\n"
        message += f"├ Entry: <code>{signal.get('entry_price', 0):.8f}</code>\n"
        message += f"├ Stop Loss: <code>{signal.get('stop_loss', 0):.8f}</code>\n"
        message += f"├ TP1: <code>{signal.get('tp1', 0):.8f}</code>\n"
        message += f"├ TP2: <code>{signal.get('tp2', 0):.8f}</code>\n"
        message += f"└ TP3: <code>{signal.get('tp3', 0):.8f}</code>\n\n"

        # ========== МЕТРИКИ ==========
        message += "📊 <b>МЕТРИКИ:</b>\n"

        # Quality Score
        quality_score = signal.get("quality_score", 0)
        message += f"├ Качество: {quality_score:.2f}/100\n"

        # Risk/Reward
        rr_ratio = signal.get("risk_reward", 0)
        message += f"├ R/R: {rr_ratio:.2f}\n"

        # Validation Score
        validation = signal.get("validation", {})
        if isinstance(validation, dict):
            passed = sum(1 for v in validation.values() if v)
            total = len(validation)
            val_score = (passed / total * 100) if total > 0 else 0
            message += f"└ Validation: {passed}/{total} ({val_score:.0f}%)\n\n"

        # ========== INFLUENCED METRICS ==========
        influenced = signal.get("influenced_metrics", {})
        if influenced:
            message += "🔍 <b>КЛЮЧЕВЫЕ ПОКАЗАТЕЛИ:</b>\n"

            adx = influenced.get("adx", "N/A")
            message += f"├ ADX: {adx}\n"

            volume_ratio = influenced.get("volume_ratio", 0)
            message += f"├ Volume Ratio: {volume_ratio:.2f}x\n"

            trend_1h = influenced.get("trend_1h", "N/A")
            trend_4h = influenced.get("trend_4h", "N/A")
            message += f"├ Trend 1H: {trend_1h}\n"
            message += f"└ Trend 4H: {trend_4h}\n\n"

        # ========== TIMESTAMP ==========
        timestamp = signal.get("timestamp", datetime.now())
        if isinstance(timestamp, datetime):
            time_str = timestamp.strftime("%H:%M:%S")
            message += f"🕐 <b>Время:</b> {time_str}\n"

        # Footer
        message += "\n<i>✨ Powered by EnhancedScenarioMatcher v2.0</i>"

        return message

    @staticmethod
    def format_tp_hit(signal: Dict, tp_level: int, price: float, roi: float) -> str:
        """
        Форматирование уведомления о достижении TP

        Args:
            signal: Dict с данными сигнала
            tp_level: Уровень TP (1, 2, 3)
            price: Цена закрытия
            roi: ROI в процентах

        Returns:
            Отформатированное сообщение
        """
        symbol = signal.get("symbol", "UNKNOWN")
        direction = signal.get("direction", "UNKNOWN")

        message = f"🎯 <b>TP{tp_level} ДОСТИГНУТ!</b>\n\n"
        message += f"📊 <b>Пара:</b> {symbol}\n"
        message += f"🆔 <b>Сигнал:</b> #{signal.get('id', 'N/A')}\n"
        message += f"🎯 <b>Направление:</b> {direction}\n\n"

        # Strategy & Market Regime
        strategy = signal.get("strategy", "unknown")
        market_regime = signal.get("market_regime", "neutral")
        message += f"📈 <b>Стратегия:</b> {strategy.upper()}\n"
        message += f"🌐 <b>Режим:</b> {market_regime.upper()}\n\n"

        message += f"💰 <b>Цена закрытия:</b> <code>{price:.8f}</code>\n"
        message += f"📊 <b>ROI:</b> {roi:+.2f}%\n\n"

        # Entry price для справки
        entry = signal.get("entry_price", 0)
        message += f"📍 <b>Entry:</b> <code>{entry:.8f}</code>\n"

        # Remaining TPs
        if tp_level < 3:
            remaining_tps = 3 - tp_level
            message += f"\n⏳ <i>Осталось {remaining_tps} TP</i>"
        else:
            message += f"\n🏁 <i>Все TP достигнуты!</i>"

        return message

    @staticmethod
    def format_signal_closed(signal: Dict, exit_price: float, roi: float, status: str) -> str:
        """
        Форматирование уведомления о закрытии сигнала

        Args:
            signal: Dict с данными сигнала
            exit_price: Цена выхода
            roi: ROI в процентах
            status: Статус закрытия

        Returns:
            Отформатированное сообщение
        """
        symbol = signal.get("symbol", "UNKNOWN")
        direction = signal.get("direction", "UNKNOWN")

        # Emoji в зависимости от результата
        if roi > 0:
            result_emoji = "✅"
            result_text = "ПРИБЫЛЬ"
        else:
            result_emoji = "❌"
            result_text = "УБЫТОК"

        message = f"{result_emoji} <b>СИГНАЛ ЗАКРЫТ: {result_text}</b>\n\n"
        message += f"📊 <b>Пара:</b> {symbol}\n"
        message += f"🆔 <b>Сигнал:</b> #{signal.get('id', 'N/A')}\n"
        message += f"🎯 <b>Направление:</b> {direction}\n\n"

        # Strategy & Market Regime
        strategy = signal.get("strategy", "unknown")
        market_regime = signal.get("market_regime", "neutral")
        confidence = signal.get("confidence", "medium")

        message += f"📈 <b>Стратегия:</b> {strategy.upper()}\n"
        message += f"🌐 <b>Режим:</b> {market_regime.upper()}\n"
        message += f"⚡ <b>Уверенность:</b> {confidence.upper()}\n\n"

        # Prices
        entry = signal.get("entry_price", 0)
        message += f"💰 <b>РЕЗУЛЬТАТЫ:</b>\n"
        message += f"├ Entry: <code>{entry:.8f}</code>\n"
        message += f"├ Exit: <code>{exit_price:.8f}</code>\n"
        message += f"└ ROI: <b>{roi:+.2f}%</b>\n\n"

        # Status
        message += f"📌 <b>Статус:</b> {status.upper()}\n"

        return message


# Экспорт
__all__ = ["EnhancedTelegramFormatter"]
