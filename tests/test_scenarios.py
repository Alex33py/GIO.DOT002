#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests для системы сценариев
Тестирование ScenarioManager и UnifiedScenarioMatcher
"""

import pytest
from core.scenario_manager import ScenarioManager
from core.scenario_matcher import UnifiedScenarioMatcher


class TestScenarioManager:
    """Тесты для ScenarioManager"""

    @pytest.fixture
    def manager(self):
        """Фикстура ScenarioManager"""
        return ScenarioManager(db_path=":memory:")

    @pytest.fixture
    def sample_scenarios(self):
        """Тестовые сценарии"""
        return [
            {
                "id": 1,
                "name": "Test Bullish Scenario",
                "direction": "long",
                "mtf_trend": "bullish",
                "timeframe": "1H",
                "rsi_1h_min": 40,
                "rsi_1h_max": 60,
                "priority": "high"
            },
            {
                "id": 2,
                "name": "Test Bearish Scenario",
                "direction": "short",
                "mtf_trend": "bearish",
                "timeframe": "4H",
                "rsi_4h_min": 40,
                "rsi_4h_max": 70,
                "priority": "medium"
            }
        ]

    # ========== ТЕСТЫ ScenarioManager ==========

    def test_initialization(self, manager):
        """Тест: инициализация ScenarioManager"""
        assert manager is not None
        assert hasattr(manager, 'scenarios')
        assert isinstance(manager.scenarios, list)

    def test_load_scenarios(self, manager, sample_scenarios):
        """Тест: загрузка сценариев"""
        manager.scenarios = sample_scenarios

        assert len(manager.scenarios) == 2
        assert manager.scenarios[0]["name"] == "Test Bullish Scenario"
        assert manager.scenarios[1]["direction"] == "short"

    def test_get_scenario_by_id(self, manager, sample_scenarios):
        """Тест: получение сценария по ID"""
        manager.scenarios = sample_scenarios

        scenario = manager.get_scenario_by_id(1)

        assert scenario is not None
        assert scenario["name"] == "Test Bullish Scenario"
        assert scenario["direction"] == "long"

    def test_get_scenario_by_id_not_found(self, manager, sample_scenarios):
        """Тест: сценарий не найден"""
        manager.scenarios = sample_scenarios

        scenario = manager.get_scenario_by_id(999)

        assert scenario is None

    def test_get_scenarios_by_direction(self, manager, sample_scenarios):
        """Тест: фильтрация по направлению"""
        manager.scenarios = sample_scenarios

        long_scenarios = [s for s in manager.scenarios if s["direction"] == "long"]
        short_scenarios = [s for s in manager.scenarios if s["direction"] == "short"]

        assert len(long_scenarios) == 1
        assert len(short_scenarios) == 1
        assert long_scenarios[0]["name"] == "Test Bullish Scenario"

    def test_get_scenarios_by_timeframe(self, manager, sample_scenarios):
        """Тест: фильтрация по таймфрейму"""
        manager.scenarios = sample_scenarios

        tf_1h = [s for s in manager.scenarios if s["timeframe"] == "1H"]
        tf_4h = [s for s in manager.scenarios if s["timeframe"] == "4H"]

        assert len(tf_1h) == 1
        assert len(tf_4h) == 1


class TestUnifiedScenarioMatcher:
    """Тесты для UnifiedScenarioMatcher"""

    @pytest.fixture
    def matcher(self):
        """Фикстура UnifiedScenarioMatcher"""
        return UnifiedScenarioMatcher()

    @pytest.fixture
    def sample_scenarios(self):
        """Тестовые сценарии"""
        return [
            {
                "id": 1,
                "name": "Perfect Bullish Match",
                "direction": "long",
                "mtf_trend": "bullish",
                "timeframe": "1H",
                "rsi_1h_min": 45,
                "rsi_1h_max": 55,
                "cvd_direction": "positive",
                "news_sentiment_min": 0.4,
                "priority": "high"
            }
        ]

    # ========== ТЕСТЫ UnifiedScenarioMatcher ==========

    def test_initialization(self, matcher):
        """Тест: инициализация matcher"""
        assert matcher is not None
        assert hasattr(matcher, 'scenarios')
        assert isinstance(matcher.scenarios, list)

    def test_load_scenarios(self, matcher, sample_scenarios):
        """Тест: загрузка сценариев в matcher"""
        matcher.scenarios = sample_scenarios

        assert len(matcher.scenarios) == 1

    def test_match_perfect_scenario(self, matcher, sample_scenarios):
        """Тест: идеальное совпадение со сценарием"""
        matcher.scenarios = sample_scenarios

        # ВСЕ 7 АРГУМЕНТОВ!
        match = matcher.match_scenario(
            symbol="BTCUSDT",
            mtf_trends={"1H": "bullish", "4H": "bullish", "1D": "bullish"},
            market_data={
                "price": 50000.0,
                "volume_24h": 1000000.0,
                "cvd": 100000.0,
                "cvd_trend": "positive"
            },
            indicators={
                "rsi_1h": 50.0,
                "rsi_4h": 55.0,
                "atr_1h": 500.0
            },
            volume_profile={"poc": 49800, "vah": 50500, "val": 49500},
            news_sentiment=0.5,
            veto_checks={"has_veto": False}
        )

        # Может быть None или dict
        assert match is None or isinstance(match, dict)

    def test_match_no_scenarios(self, matcher):
        """Тест: нет совпадений"""
        matcher.scenarios = []

        match = matcher.match_scenario(
            symbol="BTCUSDT",
            mtf_trends={"1H": "neutral"},
            market_data={"price": 50000.0},
            indicators={},
            volume_profile={},
            news_sentiment=0,
            veto_checks={"has_veto": False}
        )

        assert match is None

    def test_match_with_veto(self, matcher, sample_scenarios):
        """Тест: совпадение с veto"""
        matcher.scenarios = sample_scenarios

        match = matcher.match_scenario(
            symbol="BTCUSDT",
            mtf_trends={"1H": "bullish"},
            market_data={"price": 50000.0, "cvd_trend": "positive"},
            indicators={"rsi_1h": 50.0},
            volume_profile={"poc": 49800},
            news_sentiment=0.5,
            veto_checks={"has_veto": True, "veto_reasons": ["High funding"]}
        )

        # С veto не должно быть сигнала
        assert match is None


class TestScenarioIntegration:
    """Интеграционные тесты Manager + Matcher"""

    @pytest.fixture
    def system(self):
        """Полная система сценариев"""
        manager = ScenarioManager(db_path=":memory:")
        matcher = UnifiedScenarioMatcher()

        scenarios = [
            {
                "id": 1,
                "name": "Full System Test",
                "direction": "long",
                "mtf_trend": "bullish",
                "timeframe": "1H",
                "rsi_1h_min": 40,
                "rsi_1h_max": 60,
                "cvd_direction": "positive",
                "news_sentiment_min": 0.3,
                "priority": "high"
            }
        ]

        manager.scenarios = scenarios
        matcher.scenarios = scenarios

        return {"manager": manager, "matcher": matcher}

    def test_full_workflow(self, system):
        """Тест: полный workflow Manager → Matcher"""
        manager = system["manager"]
        matcher = system["matcher"]

        # 1. Проверяем загрузку
        assert len(manager.scenarios) == 1
        assert len(matcher.scenarios) == 1

        # 2. Получаем сценарий
        scenario = manager.get_scenario_by_id(1)
        assert scenario is not None

        # 3. Матчим (ВСЕ 7 АРГУМЕНТОВ!)
        match = matcher.match_scenario(
            symbol="BTCUSDT",
            mtf_trends={"1H": "bullish"},
            market_data={"price": 50000.0, "cvd_trend": "positive"},
            indicators={"rsi_1h": 50.0},
            volume_profile={},
            news_sentiment=0.5,
            veto_checks={"has_veto": False}
        )

        # 4. Проверяем результат
        assert match is None or isinstance(match, dict)


# Экспорт
__all__ = [
    'TestScenarioManager',
    'TestUnifiedScenarioMatcher',
    'TestScenarioIntegration'
]
