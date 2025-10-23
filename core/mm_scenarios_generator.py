#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MM Scenarios Generator — Генератор market-making сценариев
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MMScenariosGenerator:
    """Генератор MM сценариев на основе market data"""

    def __init__(self):
        self.scenarios_history = []

    def generate_scenario(self, market_data: dict) -> Optional[Dict]:
        """
        Генерирует MM сценарий на основе рыночных данных

        Args:
            market_data: dict с price, volume, cvd, funding, ratio, etc.

        Returns:
            Dict с scenario, phase, interpretation, metrics
        """
        try:
            scenario = self._detect_scenario(market_data)
            phase = self._detect_phase(market_data, scenario)

            return {
                "scenario": scenario,
                "phase": phase,
                "timestamp": datetime.now().isoformat(),
                "metrics": {
                    "cvd": market_data.get("cvd", 0),
                    "funding": market_data.get("funding", 0),
                    "ratio": market_data.get("ratio", 1.0),
                    "liquidations": market_data.get("liquidations", 0),
                    "institutional": market_data.get("institutional", 0),
                    "wyckoff_phase": market_data.get("wyckoff_phase", "Unknown")
                }
            }
        except Exception as e:
            logger.error(f"Generate scenario error: {e}")
            return None

    def _detect_scenario(self, data: dict) -> str:
        """Определяет тип сценария"""
        cvd = data.get("cvd", 0)
        funding = data.get("funding", 0)
        ratio = data.get("ratio", 1.0)

        # Accumulation
        if cvd < -5 and funding < 0.01:
            return "accumulation"

        # Distribution
        if cvd < -10 and funding > 0.05:
            return "distribution"

        # Squeeze
        if abs(ratio - 1.0) > 0.5:
            return "squeeze"

        # Overheat
        if abs(funding) > 0.1:
            return "overheat"

        # Equilibrium
        if abs(cvd) < 2 and abs(funding) < 0.02:
            return "equilibrium"

        return "impulse"

    def _detect_phase(self, data: dict, scenario: str) -> str:
        """Определяет фазу сценария"""
        if scenario == "accumulation":
            if data.get("wyckoff_phase") == "spring":
                return "spring"
            return "test"

        if scenario == "distribution":
            if data.get("cvd", 0) < -15:
                return "upthrust"
            return "utad"

        if scenario == "squeeze":
            ratio = data.get("ratio", 1.0)
            if ratio > 1.5:
                return "long_squeeze"
            return "short_squeeze"

        return "default"
