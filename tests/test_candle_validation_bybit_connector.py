#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit-тесты для Bybit Connector
"""

import pytest
import asyncio
from connectors.bybit_connector import EnhancedBybitConnector


@pytest.mark.asyncio
async def test_get_klines_validation():
    """Тест валидации свечей"""
    connector = EnhancedBybitConnector()
    await connector.initialize()

    # Получаем свечи
    candles = await connector.get_klines("BTCUSDT", "60", limit=10)

    # Проверяем что не None
    assert candles is not None

    # Проверяем что есть свечи
    assert len(candles) > 0

    # Проверяем структуру
    for candle in candles:
        assert "timestamp" in candle
        assert "open" in candle
        assert "high" in candle
        assert "low" in candle
        assert "close" in candle
        assert "volume" in candle

        # Проверяем валидность OHLC
        assert candle["low"] <= candle["open"] <= candle["high"]
        assert candle["low"] <= candle["close"] <= candle["high"]
        assert candle["volume"] >= 0


@pytest.mark.asyncio
async def test_get_ticker():
    """Тест получения тикера"""
    connector = EnhancedBybitConnector()
    await connector.initialize()

    ticker = await connector.get_ticker("BTCUSDT")

    assert ticker is not None
    assert "lastPrice" in ticker or "last_price" in ticker
