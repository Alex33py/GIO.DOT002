#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурация фильтров для GIO Crypto Bot
ОПТИМИЗИРОВАННАЯ ВЕРСИЯ - снижены пороги для увеличения генерации сигналов
"""


# ============================================
# CONFIRM FILTER - Фильтр подтверждения
# ============================================
CONFIRM_FILTER_CONFIG = {
    "enabled": True,
    # CVD Threshold: 0.2% → 0.15%
    # Более реалистичное значение для детекции дисбаланса
    "cvd_threshold": 0.15,  # Минимальный дисбаланс orderbook (%)
    # Volume Multiplier: 1.5x → 1.2x
    # Менее строгое требование к объему
    "volume_threshold_multiplier": 1.2,  # Множитель среднего объёма
    # Candle Confirmation: остается False (быстрая реакция)
    "require_candle_confirmation": False,
    # Min Large Trade: $10,000 → $5,000
    # Более чувствительная детекция крупных сделок
    "min_large_trade_value": 5000,  # Минимальный размер large trade ($)
}


# ============================================
# MULTI-TF FILTER - Фильтр множественных таймфреймов
# 🔥 КЛЮЧЕВЫЕ ИЗМЕНЕНИЯ!
# ============================================
MULTI_TF_FILTER_CONFIG = {
    "enabled": True,
    # Require All Aligned: остается False
    "require_all_aligned": False,  # Требовать согласование всех TF
    # 🔥 Min Aligned Count: 2 → 1 (КРИТИЧНО!)
    # Это разблокирует генерацию сигналов при текущем downtrend
    # Старое значение (2) требовало 2 из 3 TF aligned (66%)
    # Новое значение (1) требует только 1 из 3 TF aligned (33%)
    "min_aligned_count": 1,  # Минимальное количество согласованных TF
    # Higher TF Weight: остается 2.0 (адекватный вес)
    "higher_tf_weight": 2.0,  # Вес старших таймфреймов
    # Timeframes: остается без изменений
    "timeframes": ["1h", "4h", "1d"],  # Проверяемые таймфреймы
}


# ============================================
# SCENARIO MATCHER CONFIG - Настройки сопоставления сценариев
# ============================================
SCENARIO_MATCHER_CONFIG = {
    # Deal Threshold: 50 → 40
    # Более агрессивная генерация сигналов
    "deal_threshold": 40,  # Confidence %
    # Risky Threshold: 40 → 30
    # Разрешаем больше возможностей
    "risky_threshold": 30,  # Confidence %
}


# ============================================
# DECISION MATRIX CONFIG - Матрица решений
# 🔥 КЛЮЧЕВЫЕ ИЗМЕНЕНИЯ!
# ============================================
DECISION_MATRIX_CONFIG = {
    # 🔥 Min Confidence: 0.65 → 0.50 (КРИТИЧНО!)
    # Это второе ключевое изменение
    # Старое значение (65%) было слишком консервативным
    # Новое значение (50%) - сбалансированное
    "min_confidence": 0.50,  # 50% минимальная уверенность
    # Strong Signal Threshold: 0.75 → 0.65
    # Порог для сильных сигналов
    "strong_signal_threshold": 0.65,  # 65% для сильных сигналов
}


# ============================================
# RISK MANAGEMENT CONFIG - Управление рисками
# ============================================
RISK_MANAGEMENT_CONFIG = {
    # Min RR: остается 1.5 (адекватное значение)
    "min_rr": 1.5,
    # SL ATR Multiplier: остается 1.5
    "default_sl_atr_multiplier": 1.5,
    # TP1 Percent: остается 1.5%
    "default_tp1_percent": 1.5,
    # Trailing Stop: включено
    "use_trailing_stop": True,
}


# ============================================
# ALERT SYSTEM CONFIG - Система алертов
# ============================================
ALERT_SYSTEM_CONFIG = {
    # Alert Cooldown: 300s → 180s
    # Более частые алерты
    "alert_cooldown": 180,  # секунды
    # Max Alerts: 10 → 15
    # Больше алертов в час
    "max_alerts_per_hour": 15,
}


# ============================================
# FILTERS ORDER - Порядок применения фильтров
# ============================================
FILTERS_ORDER = [
    "confirm_filter",  # Сначала Confirm Filter
    "multi_tf_filter",  # Потом Multi-TF Filter
]
