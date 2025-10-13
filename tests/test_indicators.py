#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests для технических индикаторов
Тестирование расчётов RSI, MACD, ATR без зависимости от MTF Analyzer
"""

import pytest
import numpy as np


class SimpleIndicators:
    """Простые индикаторы для тестирования (standalone)"""

    @staticmethod
    def calculate_rsi(closes: list, period: int = 14) -> float:
        """Упрощённый расчёт RSI"""
        if len(closes) < period + 1:
            return 50.0

        deltas = [closes[i] - closes[i-1] for i in range(1, len(closes))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return rsi

    @staticmethod
    def calculate_ema(data: list, period: int) -> float:
        """EMA"""
        if len(data) < period:
            return data[-1] if data else 0

        multiplier = 2 / (period + 1)
        ema = data[0]

        for price in data[1:]:
            ema = (price - ema) * multiplier + ema

        return ema

    @staticmethod
    def calculate_atr(candles: list, period: int = 14) -> float:
        """ATR"""
        if len(candles) < period:
            return candles[-1]["close"] * 0.01 if candles else 1.0

        true_ranges = []
        for i in range(1, len(candles)):
            high = float(candles[i]["high"])
            low = float(candles[i]["low"])
            prev_close = float(candles[i-1]["close"])

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        atr = sum(true_ranges[-period:]) / period
        return atr


class TestIndicators:
    """Тесты для технических индикаторов"""

    @pytest.fixture
    def sample_candles(self):
        """Тестовые данные - 100 свечей"""
        return [
            {
                "timestamp": 1000000000 + i * 60000,
                "open": 100 + i * 0.5,
                "high": 105 + i * 0.5,
                "low": 95 + i * 0.5,
                "close": 102 + i * 0.5,
                "volume": 1000 + i * 10
            }
            for i in range(100)
        ]

    @pytest.fixture
    def indicators(self):
        """Фикстура индикаторов"""
        return SimpleIndicators()

    # ========== ТЕСТЫ RSI ==========

    def test_rsi_calculation(self, indicators):
        """Тест: расчёт RSI"""
        closes = [100 + i * 0.5 for i in range(50)]
        rsi = indicators.calculate_rsi(closes, period=14)

        # RSI должен быть числом
        assert isinstance(rsi, (int, float))

        # RSI должен быть в диапазоне 0-100
        assert 0 <= rsi <= 100

    def test_rsi_uptrend(self, indicators):
        """Тест: RSI при восходящем тренде (должен быть > 50)"""
        closes = [100 + i for i in range(50)]
        rsi = indicators.calculate_rsi(closes, period=14)

        # При росте RSI должен быть выше 50
        assert rsi > 50

    def test_rsi_downtrend(self, indicators):
        """Тест: RSI при нисходящем тренде (должен быть < 50)"""
        closes = [100 - i for i in range(50)]
        rsi = indicators.calculate_rsi(closes, period=14)

        # При падении RSI должен быть ниже 50
        assert rsi < 50

    def test_rsi_insufficient_data(self, indicators):
        """Тест: RSI с недостаточными данными (< 15 свечей)"""
        closes = [100 for i in range(10)]
        rsi = indicators.calculate_rsi(closes, period=14)

        # Должен вернуть fallback (50.0)
        assert rsi == 50.0

    def test_rsi_overbought(self, indicators):
        """Тест: RSI перекупленность (должен быть > 70)"""
        # Сильный рост
        closes = [100 + i * 2 for i in range(50)]
        rsi = indicators.calculate_rsi(closes, period=14)

        assert rsi > 70

    def test_rsi_oversold(self, indicators):
        """Тест: RSI перепроданность (должен быть < 30)"""
        # Сильное падение
        closes = [100 - i * 2 for i in range(50)]
        rsi = indicators.calculate_rsi(closes, period=14)

        assert rsi < 30

    # ========== ТЕСТЫ ATR ==========

    def test_atr_calculation(self, indicators, sample_candles):
        """Тест: расчёт ATR"""
        atr = indicators.calculate_atr(sample_candles, period=14)

        # ATR должен быть числом
        assert isinstance(atr, (int, float))

        # ATR должен быть положительным
        assert atr > 0

    def test_atr_high_volatility(self, indicators):
        """Тест: ATR при высокой волатильности"""
        candles = [
            {
                "open": 100,
                "high": 150,  # Большая волатильность
                "low": 50,
                "close": 100,
                "volume": 1000
            }
            for i in range(50)
        ]

        atr = indicators.calculate_atr(candles, period=14)

        # ATR должен быть значительным (> 10)
        assert atr > 10

    def test_atr_low_volatility(self, indicators):
        """Тест: ATR при низкой волатильности"""
        candles = [
            {
                "open": 100,
                "high": 101,  # Низкая волатильность
                "low": 99,
                "close": 100,
                "volume": 1000
            }
            for i in range(50)
        ]

        atr = indicators.calculate_atr(candles, period=14)

        # ATR должен быть небольшим (< 5)
        assert atr < 5

    def test_atr_insufficient_data(self, indicators):
        """Тест: ATR с недостаточными данными"""
        candles = [
            {"open": 100, "high": 105, "low": 95, "close": 102, "volume": 1000}
            for i in range(10)
        ]

        atr = indicators.calculate_atr(candles, period=14)

        # Должен вернуть fallback (1% от цены = 1.02)
        assert isinstance(atr, float)
        assert 0.5 < atr < 2.0

    # ========== ТЕСТЫ EMA ==========

    def test_ema_calculation(self, indicators):
        """Тест: расчёт EMA"""
        data = [100, 102, 101, 103, 105, 107, 106, 108, 110, 109]

        ema = indicators.calculate_ema(data, period=5)

        # EMA должен быть числом
        assert isinstance(ema, (int, float))

        # EMA должен быть близок к последним значениям
        assert 105 < ema < 112

    def test_ema_uptrend(self, indicators):
        """Тест: EMA при восходящем тренде"""
        data = list(range(100, 150))  # Линейный рост

        ema = indicators.calculate_ema(data, period=10)

        # EMA должен быть близок к последним значениям
        assert ema > 140

    def test_ema_insufficient_data(self, indicators):
        """Тест: EMA с недостаточными данными"""
        data = [100, 102, 105]  # Всего 3 точки

        ema = indicators.calculate_ema(data, period=10)

        # Должен вернуть последнее значение
        assert ema == 105


# Запуск тестов
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
