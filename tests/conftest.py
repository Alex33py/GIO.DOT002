#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Общие фикстуры для pytest
"""

import pytest
import asyncio
import sys
from pathlib import Path

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def event_loop():
    """Фикстура для event loop"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_btc_klines():
    """Образец данных BTCUSDT klines"""
    return [
        {
            "timestamp": 1728000000000,
            "open": 62000.0,
            "high": 62500.0,
            "low": 61800.0,
            "close": 62300.0,
            "volume": 1250.5
        },
        {
            "timestamp": 1727999700000,
            "open": 62100.0,
            "high": 62300.0,
            "low": 61900.0,
            "close": 62000.0,
            "volume": 980.3
        }
    ]


@pytest.fixture
def sample_ticker():
    """Образец данных ticker"""
    return {
        "symbol": "BTCUSDT",
        "last_price": 62300.0,
        "price_24h_pcnt": 2.5,
        "volume_24h": 15000.0,
        "high_24h": 62800.0,
        "low_24h": 60500.0,
        "timestamp": 1728000000000
    }


@pytest.fixture
def sample_orderbook():
    """Образец данных orderbook"""
    return {
        "symbol": "BTCUSDT",
        "timestamp": 1728000000000,
        "bids": [
            {"price": 62300.0, "size": 1.5},
            {"price": 62299.0, "size": 2.3},
            {"price": 62298.0, "size": 1.8}
        ],
        "asks": [
            {"price": 62301.0, "size": 1.2},
            {"price": 62302.0, "size": 2.1},
            {"price": 62303.0, "size": 1.6}
        ]
    }
