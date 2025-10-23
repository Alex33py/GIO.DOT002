#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MM Scenario Interpreter — AI-like объяснения действий маркетмейкера
"""

import logging

logger = logging.getLogger(__name__)


class ScenarioInterpreter:
    """Интерпретирует MM сценарии и генерирует объяснения действий маркетмейкера"""

    # MM Scenario Interpretations
    INTERPRETATIONS = {
        "accumulation": {
            "spring": (
                "Market Maker собирает позицию после шейкаута. "
                "CVD показывает сброс слабых рук (negative), "
                "но институциональные покупки растут. "
                "Wyckoff Spring → готовность к росту."
            ),
            "test": (
                "MM тестирует поддержку перед набором позиции. "
                "Funding низкий, объемы падают. "
                "Готовится импульс вверх после consolidation."
            ),
            "default": (
                "MM собирает позицию в низу диапазона. "
                "Funding rate отрицательный (shorts платят), "
                "CVD negative (сброс слабых рук), "
                "но институциональные покупки +{institutional}%. "
                "Wyckoff phase: {wyckoff_phase}."
            )
        },

        "distribution": {
            "upthrust": (
                "MM выходит из позиции под видом роста. "
                "CVD сильно negative ({cvd}%), "
                "Open Interest растет (longs входят), "
                "но крупные игроки сбрасывают. "
                "Коррекция продолжится."
            ),
            "utad": (
                "Ловушка для лонгов (UTAD). "
                "MM сбрасывает на росте, создавая FOMO. "
                "Funding rate перегрет ({funding}%), "
                "L/S Ratio extreme. Разворот вниз."
            ),
            "default": (
                "MM распродает позицию под видом роста. "
                "CVD negative {cvd}%, OI растет, "
                "но институциональный flow negative. "
                "Wyckoff phase: {wyckoff_phase}. Риск коррекции."
            )
        },

        "trap": {
            "bear_trap": (
                "Ложный пробой вниз (Bear Trap). "
                "L/S Ratio {ratio} (bullish), "
                "Institutional flow +{institutional}%. "
                "MM собрал стопы — готовится отскок вверх."
            ),
            "bull_trap": (
                "Ложный пробой вверх (Bull Trap). "
                "Funding перегрет ({funding}%), "
                "CVD negative {cvd}%. "
                "MM сбросил на breakout — коррекция вниз."
            ),
            "default": (
                "Ложный пробой уровня. "
                "MM собирает ликвидность за уровнем, "
                "затем разворот в противоположную сторону. "
                "Volume spike + CVD divergence."
            )
        },

        "squeeze": {
            "long_squeeze": (
                "Long Squeeze в процессе. "
                "Массовые ликвидации longs ({liquidations}M), "
                "Funding rate падает резко. "
                "После завершения — разворот вверх."
            ),
            "short_squeeze": (
                "Short Squeeze в процессе. "
                "Массовые ликвидации shorts ({liquidations}M), "
                "Funding rate растет резко. "
                "После завершения — разворот вниз."
            ),
            "default": (
                "Squeeze detected: массовые ликвидации позиций. "
                "L/S Ratio extreme ({ratio}), "
                "после завершения — сильный импульс в противоположную сторону."
            )
        },

        "overheat": {
            "default": (
                "Рынок перегрет: толпа агрессивно входит. "
                "Funding rate {funding}% (extreme), "
                "L/S Ratio {ratio} (one-sided). "
                "MM готовит вынос стопов — осторожность!"
            )
        },

        "equilibrium": {
            "default": (
                "Период равновесия — накопление энергии. "
                "ATR низкий, Volume падает, "
                "Funding neutral. Готовится импульс — "
                "направление пока не ясно."
            )
        },

        "impulse": {
            "default": (
                "Импульсное движение на объемах. "
                "CVD подтверждает направление ({cvd}%), "
                "пробой VAH/VAL с volume. "
                "Trend следование — работает!"
            )
        },

        "reversal": {
            "default": (
                "Разворот тренда формируется. "
                "MACD divergence, RSI extreme, "
                "Volume растет на противоположной стороне. "
                "Завершение цикла — смена направления."
            )
        }
    }

    @staticmethod
    def interpret(scenario: str, phase: str, metrics: dict) -> str:
        """
        Генерирует AI-like интерпретацию MM сценария

        Args:
            scenario: accumulation, distribution, trap, squeeze, etc.
            phase: spring, test, upthrust, utad, etc.
            metrics: dict с CVD, funding, ratio, liquidations, institutional, etc.

        Returns:
            str: Интерпретация действий MM
        """
        try:
            scenario = scenario.lower() if scenario else "default"
            phase = phase.lower() if phase else "default"

            # Получаем шаблон интерпретации
            scenario_templates = ScenarioInterpreter.INTERPRETATIONS.get(scenario, {})
            template = scenario_templates.get(phase, scenario_templates.get("default", ""))

            if not template:
                return f"{scenario.title()} phase detected. Анализ в процессе..."

            # Форматируем шаблон с метриками
            interpretation = template.format(
                cvd=round(metrics.get("cvd", 0), 1),
                funding=round(metrics.get("funding", 0) * 100, 2),
                ratio=round(metrics.get("ratio", 1.0), 2),
                liquidations=round(metrics.get("liquidations", 0) / 1_000_000, 1),
                institutional=round(metrics.get("institutional", 0), 1),
                wyckoff_phase=metrics.get("wyckoff_phase", "Unknown"),
                oi_change=round(metrics.get("oi_change", 0), 1)
            )

            return interpretation

        except Exception as e:
            logger.error(f"Interpret error: {e}")
            return f"{scenario.title()} phase. Monitoring..."


# Emoji маппинг для сценариев
SCENARIO_EMOJI = {
    "accumulation": "🟢",
    "distribution": "🔴",
    "trap": "⚠️",
    "squeeze": "🔥",
    "overheat": "🌡️",
    "equilibrium": "⚖️",
    "impulse": "🚀",
    "reversal": "🔄"
}


def get_scenario_emoji(scenario: str) -> str:
    """Возвращает emoji для сценария"""
    return SCENARIO_EMOJI.get(scenario.lower(), "📊")
