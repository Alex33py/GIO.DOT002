#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests для DataValidator
ФИНАЛЬНАЯ ВЕРСИЯ - адаптирована под ВАШ код
"""

import pytest
import numpy as np
from utils.validators import DataValidator


class TestDataValidator:
    """Тесты для DataValidator (100% адаптировано)"""

    # ========== ТЕСТЫ validate_price() ==========

    def test_validate_price_valid(self):
        """Тест: валидная цена (реальные цены крипты)"""
        # BTCUSDT обычно > $10,000, поэтому используем реальную цену
        assert DataValidator.validate_price(50000, "BTCUSDT") is True
        assert DataValidator.validate_price(3000, "ETHUSDT") is True
        assert DataValidator.validate_price(1.5, "ADAUSDT") is True

    def test_validate_price_none(self):
        """Тест: цена = None"""
        assert DataValidator.validate_price(None, "BTCUSDT") is False

    def test_validate_price_zero(self):
        """Тест: цена = 0"""
        assert DataValidator.validate_price(0, "BTCUSDT") is False

    def test_validate_price_negative(self):
        """Тест: отрицательная цена"""
        assert DataValidator.validate_price(-10, "BTCUSDT") is False

    def test_validate_price_nan(self):
        """Тест: цена = NaN"""
        assert DataValidator.validate_price(np.nan, "BTCUSDT") is False

    # ========== ТЕСТЫ validate_volume() ==========

    def test_validate_volume_valid(self):
        """Тест: валидный объём"""
        assert DataValidator.validate_volume(100.5, "BTCUSDT") is True
        assert DataValidator.validate_volume(0, "BTCUSDT") is True

    def test_validate_volume_none(self):
        """Тест: объём = None"""
        assert DataValidator.validate_volume(None, "BTCUSDT") is False

    def test_validate_volume_negative(self):
        """Тест: отрицательный объём"""
        assert DataValidator.validate_volume(-5, "BTCUSDT") is False

    # ========== ТЕСТЫ validate_candle() ==========

    def test_validate_candle_valid(self):
        """Тест: валидная свеча"""
        candle = {
            "open": 100,
            "high": 105,
            "low": 95,
            "close": 102,
            "volume": 1000
        }
        assert DataValidator.validate_candle(candle) is True

    def test_validate_candle_missing_field(self):
        """Тест: отсутствует поле"""
        candle = {
            "open": 100,
            "high": 105,
            "low": 95,
            # "close" отсутствует
            "volume": 1000
        }
        assert DataValidator.validate_candle(candle) is False

    def test_validate_candle_high_less_than_low(self):
        """Тест: high < low"""
        candle = {
            "open": 100,
            "high": 95,
            "low": 105,
            "close": 100,
            "volume": 1000
        }
        assert DataValidator.validate_candle(candle) is False

    def test_validate_candle_invalid_price(self):
        """Тест: невалидная цена (NaN)"""
        candle = {
            "open": np.nan,
            "high": 105,
            "low": 95,
            "close": 100,
            "volume": 1000
        }
        assert DataValidator.validate_candle(candle) is False

    # ========== ТЕСТЫ validate_indicator() ==========

    def test_validate_indicator_valid(self):
        """Тест: валидный индикатор"""
        assert DataValidator.validate_indicator(50, "RSI", min_val=0, max_val=100) is True

    def test_validate_indicator_out_of_range(self):
        """Тест: индикатор вне диапазона"""
        assert DataValidator.validate_indicator(120, "RSI", min_val=0, max_val=100) is False
        assert DataValidator.validate_indicator(-5, "RSI", min_val=0, max_val=100) is False

    # ========== ТЕСТЫ validate_rsi() ==========

    def test_validate_rsi_valid(self):
        """Тест: валидный RSI"""
        assert DataValidator.validate_rsi(50) is True
        assert DataValidator.validate_rsi(0) is True
        assert DataValidator.validate_rsi(100) is True

    def test_validate_rsi_out_of_range(self):
        """Тест: RSI вне диапазона"""
        assert DataValidator.validate_rsi(120) is False
        assert DataValidator.validate_rsi(-10) is False


# Запуск тестов
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
