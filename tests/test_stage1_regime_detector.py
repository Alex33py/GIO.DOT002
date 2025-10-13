# -*- coding: utf-8 -*-
"""
Тестирование MarketRegimeDetector
"""

import sys
from pathlib import Path

# Добавляем корневую директорию в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from systems.market_regime_detector import MarketRegimeDetector


def test_regime_trending():
    """Тест: Детекция trending режима"""
    print("\n🔍 ТЕСТ: Trending Regime")
    print("=" * 70)

    detector = MarketRegimeDetector()

    market_data = {
        "adx": 35,
        "volume": 2000,
        "volume_ma20": 1000,
        "bb_width_percentile": 50,
        "atr_percentile": 60
    }

    regime = detector.detect(market_data)
    print(f"📊 Входные данные: ADX=35, Volume Ratio=2.0")
    print(f"✅ Определён режим: {regime}")
    print(f"📝 Описание: {detector.get_regime_description(regime)}")
    print(f"🎯 Рекомендованные стратегии: {detector.get_recommended_strategies(regime)}")

    assert regime == "trending", f"❌ Ожидалось 'trending', получено '{regime}'"
    print("✅ ТЕСТ ПРОЙДЕН\n")


def test_regime_ranging():
    """Тест: Детекция ranging режима"""
    print("\n🔍 ТЕСТ: Ranging Regime")
    print("=" * 70)

    detector = MarketRegimeDetector()

    market_data = {
        "adx": 15,
        "volume": 700,
        "volume_ma20": 1000,
        "bb_width_percentile": 35,
        "atr_percentile": 30
    }

    regime = detector.detect(market_data)
    print(f"📊 Входные данные: ADX=15, Volume Ratio=0.7, BB Width=35%")
    print(f"✅ Определён режим: {regime}")
    print(f"📝 Описание: {detector.get_regime_description(regime)}")
    print(f"🎯 Рекомендованные стратегии: {detector.get_recommended_strategies(regime)}")

    assert regime == "ranging", f"❌ Ожидалось 'ranging', получено '{regime}'"
    print("✅ ТЕСТ ПРОЙДЕН\n")


def test_regime_squeezing():
    """Тест: Детекция squeezing режима"""
    print("\n🔍 ТЕСТ: Squeezing Regime")
    print("=" * 70)

    detector = MarketRegimeDetector()

    market_data = {
        "adx": 18,
        "volume": 600,
        "volume_ma20": 1000,
        "bb_width_percentile": 25,
        "atr_percentile": 20
    }

    regime = detector.detect(market_data)
    print(f"📊 Входные данные: ADX=18, Volume Ratio=0.6, BB Width=25%")
    print(f"✅ Определён режим: {regime}")
    print(f"📝 Описание: {detector.get_regime_description(regime)}")
    print(f"🎯 Рекомендованные стратегии: {detector.get_recommended_strategies(regime)}")

    assert regime == "squeezing", f"❌ Ожидалось 'squeezing', получено '{regime}'"
    print("✅ ТЕСТ ПРОЙДЕН\n")


def test_regime_expanding():
    """Тест: Детекция expanding режима"""
    print("\n🔍 ТЕСТ: Expanding Regime")
    print("=" * 70)

    detector = MarketRegimeDetector()

    market_data = {
        "adx": 28,
        "volume": 2000,
        "volume_ma20": 1000,
        "bb_width_percentile": 70,
        "atr_percentile": 75
    }

    regime = detector.detect(market_data)
    print(f"📊 Входные данные: ADX=28, Volume Ratio=2.0, BB Width=70%")
    print(f"✅ Определён режим: {regime}")
    print(f"📝 Описание: {detector.get_regime_description(regime)}")
    print(f"🎯 Рекомендованные стратегии: {detector.get_recommended_strategies(regime)}")

    assert regime == "expanding", f"❌ Ожидалось 'expanding', получено '{regime}'"
    print("✅ ТЕСТ ПРОЙДЕН\n")


def test_all_regimes():
    """Запуск всех тестов"""
    print("\n" + "=" * 70)
    print("🧪 ТЕСТИРОВАНИЕ MarketRegimeDetector")
    print("=" * 70)

    tests = [
        ("Trending Regime", test_regime_trending),
        ("Ranging Regime", test_regime_ranging),
        ("Squeezing Regime", test_regime_squeezing),
        ("Expanding Regime", test_regime_expanding)
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"❌ ТЕСТ ПРОВАЛЕН: {name}")
            print(f"   Причина: {e}\n")
            failed += 1
        except Exception as e:
            print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {name}")
            print(f"   Причина: {e}\n")
            failed += 1

    print("\n" + "=" * 70)
    print("📊 ИТОГИ")
    print("=" * 70)
    print(f"✅ Пройдено: {passed}")
    print(f"❌ Провалено: {failed}")
    print(f"📊 Всего: {passed + failed}")

    if failed == 0:
        print("\n🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ!")
    else:
        print("\n⚠️ ЕСТЬ ОШИБКИ!")

    print("=" * 70 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = test_all_regimes()
    exit(0 if success else 1)
