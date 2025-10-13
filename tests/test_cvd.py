#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests для CVD Calculator
Тестирование Cumulative Volume Delta
"""

import pytest
from analytics.cvd_calculator import CumulativeVolumeDelta


class TestCVDCalculator:
    """Тесты для CVD Calculator"""

    @pytest.fixture
    def cvd(self):
        """Фикстура CVD Calculator"""
        return CumulativeVolumeDelta(max_history=100)

    @pytest.fixture
    def buy_trades(self):
        """Тестовые покупки"""
        return [
            {"price": 100, "size": 10, "side": "BUY", "timestamp": 1000000000 + i}
            for i in range(10)
        ]

    @pytest.fixture
    def sell_trades(self):
        """Тестовые продажи"""
        return [
            {"price": 100, "size": 5, "side": "SELL", "timestamp": 1000000000 + i}
            for i in range(10)
        ]

    # ========== ТЕСТЫ update() ==========

    def test_cvd_initialization(self, cvd):
        """Тест: инициализация CVD"""
        assert cvd.get_current_cvd() == 0.0
        assert cvd.total_buy_volume == 0.0
        assert cvd.total_sell_volume == 0.0

    def test_cvd_buy_trades(self, cvd, buy_trades):
        """Тест: CVD растёт при покупках"""
        initial_cvd = cvd.get_current_cvd()

        cvd.update(buy_trades)

        # CVD должен вырасти
        assert cvd.get_current_cvd() > initial_cvd

        # Должно быть 10 покупок по 10 = 100
        assert cvd.total_buy_volume == 100.0

    def test_cvd_sell_trades(self, cvd, sell_trades):
        """Тест: CVD падает при продажах"""
        initial_cvd = cvd.get_current_cvd()

        cvd.update(sell_trades)

        # CVD должен упасть
        assert cvd.get_current_cvd() < initial_cvd

        # Должно быть 10 продаж по 5 = 50
        assert cvd.total_sell_volume == 50.0

    def test_cvd_mixed_trades(self, cvd):
        """Тест: CVD при смешанных сделках"""
        trades = [
            {"price": 100, "size": 10, "side": "BUY", "timestamp": 1000000000},
            {"price": 100, "size": 5, "side": "SELL", "timestamp": 1000000001},
            {"price": 100, "size": 8, "side": "BUY", "timestamp": 1000000002},
            {"price": 100, "size": 3, "side": "SELL", "timestamp": 1000000003},
        ]

        cvd.update(trades)

        # CVD = 10 - 5 + 8 - 3 = 10
        assert cvd.get_current_cvd() == 10.0

    def test_cvd_empty_trades(self, cvd):
        """Тест: CVD при пустом списке trades"""
        initial_cvd = cvd.get_current_cvd()

        cvd.update([])

        # CVD не должен измениться
        assert cvd.get_current_cvd() == initial_cvd

    # ========== ТЕСТЫ get_trend() ==========

    def test_cvd_bullish_trend(self, cvd):
        """Тест: определение бычьего тренда"""
        # Добавляем 15 покупок подряд
        for i in range(15):
            trades = [{"price": 100, "size": 10, "side": "BUY", "timestamp": 1000000000 + i}]
            cvd.update(trades)

        trend = cvd.get_trend(lookback_periods=10)

        assert trend == "BULLISH"

    def test_cvd_bearish_trend(self, cvd):
        """Тест: определение медвежьего тренда"""
        # Добавляем 15 продаж подряд
        for i in range(15):
            trades = [{"price": 100, "size": 10, "side": "SELL", "timestamp": 1000000000 + i}]
            cvd.update(trades)

        trend = cvd.get_trend(lookback_periods=10)

        assert trend == "BEARISH"

    def test_cvd_neutral_trend(self, cvd):
        """Тест: нейтральный тренд при недостаточных данных"""
        trend = cvd.get_trend(lookback_periods=10)

        assert trend == "NEUTRAL"

    # ========== ТЕСТЫ get_statistics() ==========

    def test_cvd_statistics(self, cvd, buy_trades, sell_trades):
        """Тест: статистика CVD"""
        cvd.update(buy_trades)
        cvd.update(sell_trades)

        stats = cvd.get_statistics(last_n_seconds=300)

        assert "cvd" in stats
        assert "trend" in stats
        assert "buy_volume" in stats
        assert "sell_volume" in stats
        assert "buy_sell_ratio" in stats

    def test_cvd_buy_sell_ratio(self, cvd):
        """Тест: соотношение покупок/продаж"""
        trades = [
            {"price": 100, "size": 100, "side": "BUY", "timestamp": 1000000000},
            {"price": 100, "size": 50, "side": "SELL", "timestamp": 1000000001},
        ]

        cvd.update(trades)

        ratio = cvd.get_buy_sell_ratio()

        # 100 покупок / 50 продаж = 2.0
        assert ratio == 2.0

    # ========== ТЕСТЫ get_divergence() ==========

    def test_cvd_bullish_divergence(self, cvd):
        """Тест: бычья дивергенция (цена падает, CVD растёт)"""
        # Симулируем CVD рост
        for i in range(25):
            trades = [{"price": 100, "size": 10, "side": "BUY", "timestamp": 1000000000 + i}]
            cvd.update(trades)

        # Симулируем падение цены
        price_history = [100 - i for i in range(25)]

        divergence = cvd.get_divergence(price_history)

        assert divergence == "BULLISH_DIV"

    def test_cvd_bearish_divergence(self, cvd):
        """Тест: медвежья дивергенция (цена растёт, CVD падает)"""
        # Симулируем CVD падение
        for i in range(25):
            trades = [{"price": 100, "size": 10, "side": "SELL", "timestamp": 1000000000 + i}]
            cvd.update(trades)

        # Симулируем рост цены
        price_history = [100 + i for i in range(25)]

        divergence = cvd.get_divergence(price_history)

        assert divergence == "BEARISH_DIV"

    def test_cvd_no_divergence(self, cvd):
        """Тест: нет дивергенции при недостаточных данных"""
        divergence = cvd.get_divergence([100, 101, 102])

        assert divergence is None

    # ========== ТЕСТЫ reset() ==========

    def test_cvd_reset(self, cvd, buy_trades):
        """Тест: сброс CVD"""
        cvd.update(buy_trades)

        assert cvd.get_current_cvd() != 0.0

        cvd.reset()

        assert cvd.get_current_cvd() == 0.0
        assert cvd.total_buy_volume == 0.0
        assert cvd.total_sell_volume == 0.0
        assert len(cvd.history) == 0


# Запуск тестов
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
