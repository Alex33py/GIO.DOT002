#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Advanced Technical Indicators
Продвинутые технические индикаторы для криптовалют
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional
from config.settings import logger


class AdvancedIndicators:
    """Продвинутые технические индикаторы"""

    def __init__(self, bybit_connector):
        self.bybit = bybit_connector
        logger.info("✅ AdvancedIndicators инициализирован")

    # ==========================================
    # MACD (Moving Average Convergence Divergence)
    # ==========================================

    def calculate_macd(self, closes: List[float], fast=12, slow=26, signal=9) -> Dict:
        """Расчёт MACD"""
        try:
            closes_series = pd.Series(closes)

            # EMA
            ema_fast = closes_series.ewm(span=fast, adjust=False).mean()
            ema_slow = closes_series.ewm(span=slow, adjust=False).mean()

            # MACD линия
            macd_line = ema_fast - ema_slow

            # Signal линия
            signal_line = macd_line.ewm(span=signal, adjust=False).mean()

            # Гистограмма
            histogram = macd_line - signal_line

            # Тренд
            trend = "BULLISH" if histogram.iloc[-1] > 0 else "BEARISH"

            return {
                "macd": f"{macd_line.iloc[-1]:.2f}",
                "signal": f"{signal_line.iloc[-1]:.2f}",
                "histogram": f"{histogram.iloc[-1]:.2f}",
                "trend": trend,
            }
        except Exception as e:
            logger.error(f"❌ MACD error: {e}")
            return {"macd": "N/A", "signal": "N/A", "histogram": "N/A", "trend": "N/A"}

    # ==========================================
    # Stochastic RSI
    # ==========================================

    def calculate_stoch_rsi(self, closes: List[float], period=14) -> Dict:
        """Расчёт Stochastic RSI"""
        try:
            closes_series = pd.Series(closes)

            # RSI
            delta = closes_series.diff()
            gain = delta.where(delta > 0, 0).rolling(window=period).mean()
            loss = -delta.where(delta < 0, 0).rolling(window=period).mean()
            rs = gain / loss
            rsi = 100 - (100 / (1 + rs))

            # Stoch RSI
            rsi_min = rsi.rolling(window=period).min()
            rsi_max = rsi.rolling(window=period).max()
            stoch_rsi = (rsi - rsi_min) / (rsi_max - rsi_min) * 100

            # %K и %D
            k = stoch_rsi.rolling(window=3).mean()
            d = k.rolling(window=3).mean()

            # Сигнал
            if k.iloc[-1] > 80:
                signal = "OVERBOUGHT"
            elif k.iloc[-1] < 20:
                signal = "OVERSOLD"
            else:
                signal = "NEUTRAL"

            return {
                "k": f"{k.iloc[-1]:.2f}",
                "d": f"{d.iloc[-1]:.2f}",
                "signal": signal,
            }
        except Exception as e:
            logger.error(f"❌ Stoch RSI error: {e}")
            return {"k": "N/A", "d": "N/A", "signal": "N/A"}

    # ==========================================
    # Bollinger Bands
    # ==========================================

    def calculate_bollinger_bands(
        self, closes: List[float], period=20, std_dev=2
    ) -> Dict:
        """Расчёт Bollinger Bands"""
        try:
            closes_series = pd.Series(closes)

            # SMA
            sma = closes_series.rolling(window=period).mean()

            # Стандартное отклонение
            std = closes_series.rolling(window=period).std()

            # Верхняя и нижняя полосы
            upper = sma + (std * std_dev)
            lower = sma - (std * std_dev)

            # Ширина полос
            width = ((upper - lower) / sma * 100).iloc[-1]

            # Squeeze (сжатие)
            squeeze = width < 2.0

            return {
                "upper": upper.iloc[-1],
                "middle": sma.iloc[-1],
                "lower": lower.iloc[-1],
                "width": width,
                "squeeze": squeeze,
            }
        except Exception as e:
            logger.error(f"❌ Bollinger Bands error: {e}")
            return {"upper": 0, "middle": 0, "lower": 0, "width": 0, "squeeze": False}

    # ==========================================
    # ATR (Average True Range)
    # ==========================================

    def calculate_atr(
        self, highs: List[float], lows: List[float], closes: List[float], period=14
    ) -> Dict:
        """Расчёт ATR"""
        try:
            highs_series = pd.Series(highs)
            lows_series = pd.Series(lows)
            closes_series = pd.Series(closes)

            # True Range
            tr1 = highs_series - lows_series
            tr2 = abs(highs_series - closes_series.shift())
            tr3 = abs(lows_series - closes_series.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

            # ATR
            atr = tr.rolling(window=period).mean().iloc[-1]

            # ATR в процентах
            atr_pct = (atr / closes[-1]) * 100

            # Волатильность
            if atr_pct > 3:
                volatility = "HIGH"
            elif atr_pct > 1.5:
                volatility = "MEDIUM"
            else:
                volatility = "LOW"

            return {
                "atr": f"{atr:.2f}",
                "atr_percentage": f"{atr_pct:.2f}",
                "volatility": volatility,
            }
        except Exception as e:
            logger.error(f"❌ ATR error: {e}")
            return {"atr": "N/A", "atr_percentage": "N/A", "volatility": "N/A"}

    # ==========================================
    # ADX (Average Directional Index)
    # ==========================================

    def calculate_adx(
        self, highs: List[float], lows: List[float], closes: List[float], period=14
    ) -> Dict:
        """Расчёт ADX"""
        try:
            highs_series = pd.Series(highs)
            lows_series = pd.Series(lows)
            closes_series = pd.Series(closes)

            # +DM и -DM
            plus_dm = highs_series.diff()
            minus_dm = -lows_series.diff()

            plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0)
            minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0)

            # True Range
            tr1 = highs_series - lows_series
            tr2 = abs(highs_series - closes_series.shift())
            tr3 = abs(lows_series - closes_series.shift())
            tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

            # ATR
            atr = tr.rolling(window=period).mean()

            # +DI и -DI
            plus_di = 100 * (plus_dm.rolling(window=period).mean() / atr)
            minus_di = 100 * (minus_dm.rolling(window=period).mean() / atr)

            # DX
            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)

            # ADX
            adx = dx.rolling(window=period).mean().iloc[-1]

            # Сила тренда
            if adx > 50:
                strength = "VERY STRONG"
            elif adx > 25:
                strength = "STRONG"
            elif adx > 20:
                strength = "MEDIUM"
            else:
                strength = "WEAK"

            return {"adx": f"{adx:.2f}", "trend_strength": strength}
        except Exception as e:
            logger.error(f"❌ ADX error: {e}")
            return {"adx": "N/A", "trend_strength": "N/A"}

    # ==========================================
    # Candlestick Patterns
    # ==========================================

    def detect_candlestick_patterns(self, klines: List[Dict]) -> Dict:
        """Детект свечных паттернов"""
        try:
            patterns = []

            if len(klines) < 3:
                return {"patterns": [], "signal": "NEUTRAL"}

            # Последние 3 свечи
            k1, k2, k3 = klines[-3:]

            o1, h1, l1, c1 = (
                float(k1["open"]),
                float(k1["high"]),
                float(k1["low"]),
                float(k1["close"]),
            )
            o2, h2, l2, c2 = (
                float(k2["open"]),
                float(k2["high"]),
                float(k2["low"]),
                float(k2["close"]),
            )
            o3, h3, l3, c3 = (
                float(k3["open"]),
                float(k3["high"]),
                float(k3["low"]),
                float(k3["close"]),
            )

            # Doji
            if abs(c3 - o3) / (h3 - l3) < 0.1:
                patterns.append({"name": "Doji", "strength": "MEDIUM"})

            # Hammer
            body = abs(c3 - o3)
            lower_shadow = min(c3, o3) - l3
            upper_shadow = h3 - max(c3, o3)

            if lower_shadow > body * 2 and upper_shadow < body:
                patterns.append({"name": "Hammer", "strength": "STRONG"})

            # Shooting Star
            if upper_shadow > body * 2 and lower_shadow < body:
                patterns.append({"name": "Shooting Star", "strength": "STRONG"})

            # Engulfing
            if c2 < o2 and c3 > o3 and c3 > o2 and o3 < c2:
                patterns.append(
                    {"name": "Bullish Engulfing", "strength": "VERY STRONG"}
                )

            if c2 > o2 and c3 < o3 and c3 < o2 and o3 > c2:
                patterns.append(
                    {"name": "Bearish Engulfing", "strength": "VERY STRONG"}
                )

            # Сигнал
            bullish = any(
                "Bullish" in p["name"] or "Hammer" in p["name"] for p in patterns
            )
            bearish = any(
                "Bearish" in p["name"] or "Shooting Star" in p["name"] for p in patterns
            )

            if bullish:
                signal = "BULLISH"
            elif bearish:
                signal = "BEARISH"
            else:
                signal = "NEUTRAL"

            return {"patterns": patterns, "signal": signal}
        except Exception as e:
            logger.error(f"❌ Candlestick patterns error: {e}")
            return {"patterns": [], "signal": "NEUTRAL"}

    # ==========================================
    # Trend Structure
    # ==========================================

    def analyze_trend_structure(
        self, highs: List[float], lows: List[float], closes: List[float]
    ) -> Dict:
        """Анализ структуры тренда"""
        try:
            # Higher Highs / Lower Lows
            recent_highs = highs[-10:]
            recent_lows = lows[-10:]

            hh = all(
                recent_highs[i] < recent_highs[i + 1]
                for i in range(len(recent_highs) - 1)
            )
            ll = all(
                recent_lows[i] > recent_lows[i + 1] for i in range(len(recent_lows) - 1)
            )

            if hh:
                trend = "UPTREND"
                structure = "Higher Highs"
            elif ll:
                trend = "DOWNTREND"
                structure = "Lower Lows"
            else:
                trend = "SIDEWAYS"
                structure = "Consolidation"

            return {"trend": trend, "structure": structure}
        except Exception as e:
            logger.error(f"❌ Trend structure error: {e}")
            return {"trend": "N/A", "structure": "N/A"}

    # ==========================================
    # Wyckoff Phase
    # ==========================================

    def analyze_wyckoff_phase(self, closes: List[float], volumes: List[float]) -> Dict:
        """Анализ фазы Wyckoff"""
        try:
            # Упрощённый анализ
            price_change = (closes[-1] - closes[-20]) / closes[-20] * 100
            volume_avg = np.mean(volumes[-20:])
            volume_recent = np.mean(volumes[-5:])

            if price_change > 5 and volume_recent > volume_avg * 1.2:
                phase = "Markup (Phase D)"
                confidence = "HIGH"
            elif price_change < -5 and volume_recent > volume_avg * 1.2:
                phase = "Markdown (Phase D)"
                confidence = "HIGH"
            elif abs(price_change) < 2:
                phase = "Accumulation/Distribution"
                confidence = "MEDIUM"
            else:
                phase = "Transition"
                confidence = "LOW"

            return {"phase": phase, "confidence": confidence}
        except Exception as e:
            logger.error(f"❌ Wyckoff analysis error: {e}")
            return {"phase": "N/A", "confidence": "N/A"}

    # ==========================================
    # Market Regime
    # ==========================================

    def detect_market_regime(self, closes: List[float], volumes: List[float]) -> Dict:
        """Детект режима рынка"""
        try:
            volatility = np.std(closes[-20:]) / np.mean(closes[-20:]) * 100
            volume_trend = (
                (np.mean(volumes[-5:]) - np.mean(volumes[-20:]))
                / np.mean(volumes[-20:])
                * 100
            )

            if volatility > 3:
                regime = "HIGH VOLATILITY"
                strength = "STRONG"
            elif volatility > 1.5:
                regime = "MEDIUM VOLATILITY"
                strength = "MEDIUM"
            else:
                regime = "LOW VOLATILITY"
                strength = "WEAK"

            return {
                "regime": regime,
                "strength": strength,
                "volatility_pct": volatility,
            }
        except Exception as e:
            logger.error(f"❌ Market regime error: {e}")
            return {"regime": "N/A", "strength": "N/A", "volatility_pct": 0}

    # ==========================================
    # Market Bias
    # ==========================================

    def calculate_market_bias(self, closes: List[float], volumes: List[float]) -> Dict:
        """Расчёт рыночного смещения"""
        try:
            # Momentum
            momentum = (closes[-1] - closes[-10]) / closes[-10] * 100

            # Volume trend
            vol_trend = (
                (np.mean(volumes[-5:]) - np.mean(volumes[-20:]))
                / np.mean(volumes[-20:])
                * 100
            )

            if momentum > 3 and vol_trend > 10:
                bias = "STRONG BULLISH"
                strength = "VERY STRONG"
            elif momentum > 1:
                bias = "BULLISH"
                strength = "MEDIUM"
            elif momentum < -3 and vol_trend > 10:
                bias = "STRONG BEARISH"
                strength = "VERY STRONG"
            elif momentum < -1:
                bias = "BEARISH"
                strength = "MEDIUM"
            else:
                bias = "NEUTRAL"
                strength = "WEAK"

            return {"bias": bias, "strength": strength, "momentum_pct": momentum}
        except Exception as e:
            logger.error(f"❌ Market bias error: {e}")
            return {"bias": "N/A", "strength": "N/A", "momentum_pct": 0}

    # ==========================================
    # 🤖 AI INTERPRETATION (Статический метод)
    # ==========================================

    @staticmethod
    def get_ai_interpretation(
        macd: Dict, stoch_rsi: Dict, bollinger: Dict, atr: Dict, adx: Dict
    ) -> str:
        """Генерация AI-интерпретации индикаторов"""
        try:
            # Упрощённая AI-логика
            interpretation = []

            # MACD
            if macd["trend"] == "BULLISH":
                interpretation.append("🟢 MACD показывает бычий сигнал")
            else:
                interpretation.append("🔴 MACD показывает медвежий сигнал")

            # Stoch RSI
            if stoch_rsi["signal"] == "OVERBOUGHT":
                interpretation.append("⚠️ Рынок перекуплен (Stoch RSI)")
            elif stoch_rsi["signal"] == "OVERSOLD":
                interpretation.append("💎 Рынок перепродан (Stoch RSI)")

            # Bollinger Bands
            if bollinger.get("squeeze"):
                interpretation.append(
                    "🔥 Bollinger Bands сжаты — ожидается сильное движение!"
                )

            # ATR
            if atr["volatility"] == "HIGH":
                interpretation.append("⚡ Высокая волатильность!")

            # ADX
            if adx["trend_strength"] in ["STRONG", "VERY STRONG"]:
                interpretation.append(f"💪 Сильный тренд (ADX: {adx['adx']})")

            return (
                "\n".join(interpretation)
                if interpretation
                else "📊 Рынок в нейтральном состоянии"
            )

        except Exception as e:
            logger.error(f"❌ AI interpretation error: {e}")
            return "⚠️ AI-интерпретация недоступна"
