#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Trading модуль - экспорт всех компонентов
"""

# Основные компоненты
from trading.signal_generator import AdvancedSignalGenerator
from trading.risk_calculator import DynamicRiskCalculator
from trading.signal_recorder import SignalRecorder
from trading.position_tracker import PositionTracker
from trading.roi_tracker import ROITracker as AutoROITracker  # ✅ ТЕПЕРЬ РАБОТАЕТ!
from trading.unified_auto_scanner import UnifiedAutoScanner

# Экспорт
__all__ = [
    "AdvancedSignalGenerator",
    "DynamicRiskCalculator",
    "SignalRecorder",
    "PositionTracker",
    "AutoROITracker",
    "UnifiedAutoScanner",
]
