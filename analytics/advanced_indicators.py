#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Technical Indicators
Продвинутые технические индикаторы для трейдинга
"""

import numpy as np
from typing import List, Dict, Tuple, Optional
from config.settings import logger


class AdvancedIndicators:
    """Продвинутые технические индикаторы"""

    @staticmethod
    def calculate_macd(
        prices: List[float],
        fast_period: int = 12,
        slow_period: int = 26,
        signal_period: int = 9,
    ) -> Dict:
        """
        MACD - Moving Average Convergence Divergence

        Args:
            prices: Список цен закрытия
            fast_period: Быстрая EMA (default: 12)
            slow_period: Медленная EMA (default: 26)
            signal_period: Сигнальная линия (default: 9)

        Returns:
            Dict с MACD, Signal, Histogram
        """
        try:
            if len(prices) < slow_period:
                return {"macd": 0, "signal": 0, "histogram": 0}

            # Преобразуем в numpy
            prices_arr = np.array(prices, dtype=float)

            # EMA helper
            def ema(data, period):
                multiplier = 2 / (period + 1)
                ema_values = [data[0]]
                for price in data[1:]:
                    ema_values.append(
                        (price - ema_values[-1]) * multiplier + ema_values[-1]
                    )
                return ema_values

            # Вычисляем MACD
            fast_ema = ema(prices_arr, fast_period)
            slow_ema = ema(prices_arr, slow_period)

            macd_line = np.array(fast_ema) - np.array(slow_ema)
            signal_line = ema(macd_line, signal_period)
            histogram = macd_line - np.array(signal_line)

            return {
                "macd": round(float(macd_line[-1]), 4),
                "signal": round(float(signal_line[-1]), 4),
                "histogram": round(float(histogram[-1]), 4),
                "trend": "bullish" if histogram[-1] > 0 else "bearish",
            }

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта MACD: {e}")
            return {"macd": 0, "signal": 0, "histogram": 0}

    @staticmethod
    def calculate_stoch_rsi(
        prices: List[float], period: int = 14, smooth_k: int = 3, smooth_d: int = 3
    ) -> Dict:
        """
        Stochastic RSI - более чувствительная версия RSI

        Args:
            prices: Список цен
            period: Период RSI
            smooth_k: Период сглаживания %K
            smooth_d: Период сглаживания %D

        Returns:
            Dict с StochRSI K и D линиями
        """
        try:
            if len(prices) < period + smooth_k + smooth_d:
                return {"k": 50, "d": 50, "signal": "neutral"}

            # Вычисляем RSI
            deltas = np.diff(prices)
            gains = np.where(deltas > 0, deltas, 0)
            losses = np.where(deltas < 0, -deltas, 0)

            avg_gain = np.mean(gains[:period])
            avg_loss = np.mean(losses[:period])

            rsi_values = []
            for i in range(period, len(prices)):
                if avg_loss == 0:
                    rsi = 100
                else:
                    rs = avg_gain / avg_loss
                    rsi = 100 - (100 / (1 + rs))
                rsi_values.append(rsi)

                if i < len(prices) - 1:
                    avg_gain = (avg_gain * (period - 1) + gains[i]) / period
                    avg_loss = (avg_loss * (period - 1) + losses[i]) / period

            # Stochastic of RSI
            if len(rsi_values) < period:
                return {"k": 50, "d": 50, "signal": "neutral"}

            stoch_rsi = []
            for i in range(period, len(rsi_values) + 1):
                rsi_slice = rsi_values[i - period : i]
                min_rsi = min(rsi_slice)
                max_rsi = max(rsi_slice)

                if max_rsi - min_rsi == 0:
                    stoch = 50
                else:
                    stoch = ((rsi_values[i - 1] - min_rsi) / (max_rsi - min_rsi)) * 100
                stoch_rsi.append(stoch)

            # Сглаживание %K
            k_values = []
            for i in range(smooth_k, len(stoch_rsi) + 1):
                k_values.append(np.mean(stoch_rsi[i - smooth_k : i]))

            # Сглаживание %D
            d_values = []
            for i in range(smooth_d, len(k_values) + 1):
                d_values.append(np.mean(k_values[i - smooth_d : i]))

            k = k_values[-1] if k_values else 50
            d = d_values[-1] if d_values else 50

            # Определяем сигнал
            if k > 80:
                signal = "overbought"
            elif k < 20:
                signal = "oversold"
            else:
                signal = "neutral"

            return {"k": round(float(k), 2), "d": round(float(d), 2), "signal": signal}

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта Stochastic RSI: {e}")
            return {"k": 50, "d": 50, "signal": "neutral"}

    @staticmethod
    def calculate_bollinger_bands(
        prices: List[float], period: int = 20, std_dev: float = 2.0
    ) -> Dict:
        """
        Bollinger Bands - полосы Боллинджера

        Args:
            prices: Список цен
            period: Период SMA
            std_dev: Количество стандартных отклонений

        Returns:
            Dict с upper, middle, lower bands и width
        """
        try:
            if len(prices) < period:
                return {"upper": 0, "middle": 0, "lower": 0, "width": 0}

            prices_arr = np.array(prices[-period:], dtype=float)

            # Средняя линия (SMA)
            middle = np.mean(prices_arr)

            # Стандартное отклонение
            std = np.std(prices_arr)

            # Верхняя и нижняя полосы
            upper = middle + (std_dev * std)
            lower = middle - (std_dev * std)

            # Ширина полос (в %)
            width = ((upper - lower) / middle) * 100 if middle > 0 else 0

            # Позиция цены относительно полос
            current_price = prices[-1]
            position = (
                ((current_price - lower) / (upper - lower)) * 100
                if (upper - lower) > 0
                else 50
            )

            return {
                "upper": round(float(upper), 2),
                "middle": round(float(middle), 2),
                "lower": round(float(lower), 2),
                "width": round(float(width), 4),
                "position": round(float(position), 2),
                "squeeze": width < 10,  # Сжатие полос
            }

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта Bollinger Bands: {e}")
            return {"upper": 0, "middle": 0, "lower": 0, "width": 0}

    @staticmethod
    def calculate_atr(
        highs: List[float], lows: List[float], closes: List[float], period: int = 14
    ) -> Dict:
        """
        ATR - Average True Range (волатильность)

        Args:
            highs: Список максимумов
            lows: Список минимумов
            closes: Список цен закрытия
            period: Период расчёта

        Returns:
            Dict с ATR и уровнем волатильности
        """
        try:
            if len(closes) < period + 1:
                return {"atr": 0, "volatility": "low"}

            # True Range
            tr_list = []
            for i in range(1, len(closes)):
                high_low = highs[i] - lows[i]
                high_close = abs(highs[i] - closes[i - 1])
                low_close = abs(lows[i] - closes[i - 1])

                tr = max(high_low, high_close, low_close)
                tr_list.append(tr)

            # ATR (сглаженное среднее TR)
            atr = np.mean(tr_list[-period:])

            # Определяем уровень волатильности
            current_price = closes[-1]
            atr_percentage = (atr / current_price) * 100 if current_price > 0 else 0

            if atr_percentage > 3:
                volatility = "high"
            elif atr_percentage > 1.5:
                volatility = "medium"
            else:
                volatility = "low"

            return {
                "atr": round(float(atr), 2),
                "atr_percentage": round(float(atr_percentage), 2),
                "volatility": volatility,
            }

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта ATR: {e}")
            return {"atr": 0, "volatility": "low"}

    @staticmethod
    def calculate_adx(
        highs: List[float], lows: List[float], closes: List[float], period: int = 14
    ) -> Dict:
        """
        ADX - Average Directional Index (сила тренда)

        Args:
            highs: Список максимумов
            lows: Список минимумов
            closes: Список цен закрытия
            period: Период расчёта

        Returns:
            Dict с ADX, +DI, -DI и силой тренда
        """
        try:
            if len(closes) < period + 1:
                return {"adx": 0, "trend_strength": "weak"}

            # Упрощённый ADX (полный расчёт сложнее)
            # Используем ATR как proxy для направленного движения
            atr_result = AdvancedIndicators.calculate_atr(highs, lows, closes, period)
            atr = atr_result["atr"]

            # Примерный ADX (нормализованный ATR)
            current_price = closes[-1]
            adx_value = (
                (atr / current_price) * 100 * 10 if current_price > 0 else 0
            )  # Масштабируем
            adx_value = min(adx_value, 100)  # Ограничиваем 100

            # Определяем силу тренда
            if adx_value > 50:
                trend_strength = "very_strong"
            elif adx_value > 25:
                trend_strength = "strong"
            elif adx_value > 20:
                trend_strength = "moderate"
            else:
                trend_strength = "weak"

            return {"adx": round(float(adx_value), 2), "trend_strength": trend_strength}

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта ADX: {e}")
            return {"adx": 0, "trend_strength": "weak"}

    @staticmethod
    def get_ai_interpretation(
        macd: Dict,
        stoch_rsi: Dict,
        bollinger: Dict,
        atr: Dict,
        adx: Dict
    ) -> str:
        """
        AI интерпретация технических индикаторов

        Args:
            macd: MACD данные
            stoch_rsi: Stochastic RSI данные
            bollinger: Bollinger Bands данные
            atr: ATR данные
            adx: ADX данные

        Returns:
            Строка с AI интерпретацией
        """
        try:
            interpretation = []

            # 1. MACD
            macd_trend = macd.get("trend", "neutral")
            macd_histogram = macd.get("histogram", 0)

            if macd_trend == "bullish":
                if abs(macd_histogram) > 100:
                    interpretation.append("🟢 **MACD** показывает **сильный бычий тренд** — импульс вверх набирает силу.")
                else:
                    interpretation.append("🟢 **MACD** в бычьей зоне, но импульс слабый — подтверждения недостаточно.")
            elif macd_trend == "bearish":
                if abs(macd_histogram) > 100:
                    interpretation.append("🔴 **MACD** показывает **сильный медвежий тренд** — давление продавцов высокое.")
                else:
                    interpretation.append("🔴 **MACD** в медвежьей зоне, но импульс слабый — возможна стабилизация.")
            else:
                interpretation.append("⚪ **MACD** нейтрален — рынок в балансе, нет чёткого направления.")

            # 2. Stochastic RSI
            stoch_k = stoch_rsi.get("k", 50)

            if stoch_k > 80:
                interpretation.append(f"🔴 **Stoch RSI** перекуплен (%K {stoch_k:.1f}) — риск коррекции вниз.")
            elif stoch_k < 20:
                interpretation.append(f"🟢 **Stoch RSI** перепродан (%K {stoch_k:.1f}) — потенциал отскока вверх.")
            else:
                interpretation.append(f"⚪ **Stoch RSI** нейтрален (%K {stoch_k:.1f}) — нет экстремальных значений.")

            # 3. Bollinger Bands
            bb_squeeze = bollinger.get("squeeze", False)
            bb_width = bollinger.get("width", 0)

            if bb_squeeze:
                interpretation.append(f"⚡ **Bollinger Bands** сжимаются (width {bb_width:.1f}%) — готовится **сильное движение**!")
            elif bb_width > 5:
                interpretation.append(f"📊 **Bollinger Bands** расширены (width {bb_width:.1f}%) — **высокая волатильность**.")
            else:
                interpretation.append(f"⚪ **Bollinger Bands** в нейтральной зоне (width {bb_width:.1f}%) — умеренная волатильность.")

            # 4. ADX (Сила тренда)
            adx_value = adx.get("adx", 0)

            if adx_value > 25:
                interpretation.append(f"🔥 **ADX {adx_value:.1f}** — **сильный тренд**! Следуй за трендом.")
            elif adx_value > 15:
                interpretation.append(f"📊 **ADX {adx_value:.1f}** — умеренный тренд, возможно боковое движение.")
            else:
                interpretation.append(f"⚪ **ADX {adx_value:.1f}** — слабый тренд, рынок в боковике.")

            # 5. ATR (Волатильность)
            atr_volatility = atr.get("volatility", "medium")
            atr_percentage = atr.get("atr_percentage", 0)

            if atr_volatility == "high":
                interpretation.append(f"⚡ **ATR {atr_percentage:.2f}%** — **высокая волатильность**, увеличь стоп-лоссы!")
            elif atr_volatility == "low":
                interpretation.append(f"😴 **ATR {atr_percentage:.2f}%** — низкая волатильность, спокойный рынок.")
            else:
                interpretation.append(f"📊 **ATR {atr_percentage:.2f}%** — умеренная волатильность.")

            # 6. Рекомендация
            bullish_signals = sum([
                macd_trend == "bullish",
                stoch_k < 20,
                adx_value > 20
            ])

            bearish_signals = sum([
                macd_trend == "bearish",
                stoch_k > 80,
                adx_value > 20
            ])

            if bullish_signals >= 2:
                interpretation.append("\n💡 **РЕКОМЕНДАЦИЯ:** 🚀 Рассмотри **LONG** при подтверждении.")
            elif bearish_signals >= 2:
                interpretation.append("\n💡 **РЕКОМЕНДАЦИЯ:** 🔻 Рассмотри **SHORT** при подтверждении.")
            elif bb_squeeze:
                interpretation.append("\n💡 **РЕКОМЕНДАЦИЯ:** ⏸️ Жди пробоя Bollinger Bands — готовится сильное движение!")
            else:
                interpretation.append("\n💡 **РЕКОМЕНДАЦИЯ:** ⏸️ Ожидание подтверждения перед открытием позиций.")

            return " ".join(interpretation)

        except Exception as e:
            logger.error(f"❌ Ошибка AI интерпретации индикаторов: {e}")
            return "⚠️ Ошибка генерации AI интерпретации."


# Экспорт
__all__ = ["AdvancedIndicators"]
