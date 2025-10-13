#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурация фильтров для GIO Crypto Bot
"""

# Confirm Filter настройки
CONFIRM_FILTER_CONFIG = {
    "enabled": True,
    "cvd_threshold": 0.2,  # Минимальный дисбаланс orderbook (%)
    "volume_threshold_multiplier": 1.5,  # Множитель среднего объёма
    "require_candle_confirmation": False,
    "min_large_trade_value": 10000,  # Минимальный размер large trade ($)
}

# Multi-TF Filter настройки
MULTI_TF_FILTER_CONFIG = {
    "enabled": True,
    "require_all_aligned": False,  # Требовать согласование всех TF
    "min_aligned_count": 2,  # Минимальное количество согласованных TF
    "higher_tf_weight": 2.0,  # Вес старших таймфреймов
    "timeframes": ["1h", "4h", "1d"],  # Проверяемые таймфреймы
}

# Combined Filters (порядок применения)
FILTERS_ORDER = [
    "confirm_filter",  # Сначала Confirm Filter
    "multi_tf_filter",  # Потом Multi-TF Filter
]
