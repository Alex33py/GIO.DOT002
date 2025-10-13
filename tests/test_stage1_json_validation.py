# -*- coding: utf-8 -*-
"""
Тестирование Этапа 1: Валидация JSON файлов
"""

import json
import os
from pathlib import Path


def test_json_syntax():
    """Тест 1: Проверка синтаксиса JSON"""
    print("\n🔍 ТЕСТ 1: Проверка синтаксиса JSON файлов")
    print("=" * 70)

    files = {
        "scenarios": "data/scenarios/gio_scenarios_v2.json",
        "strategies": "data/strategies/strategy_extensions_v1.1.json"
    }

    results = {}

    for name, path in files.items():
        try:
            if not os.path.exists(path):
                print(f"❌ {name}: Файл не найден - {path}")
                results[name] = False
                continue

            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            print(f"✅ {name}: Синтаксис валиден")
            print(f"   📄 Размер: {os.path.getsize(path)} байт")
            print(f"   📊 Ключей верхнего уровня: {len(data.keys())}")
            results[name] = True

        except json.JSONDecodeError as e:
            print(f"❌ {name}: Ошибка JSON синтаксиса - {e}")
            results[name] = False
        except Exception as e:
            print(f"❌ {name}: Неожиданная ошибка - {e}")
            results[name] = False

    return all(results.values())


def test_scenarios_structure():
    """Тест 2: Проверка структуры сценариев"""
    print("\n🔍 ТЕСТ 2: Проверка структуры scenarios")
    print("=" * 70)

    try:
        with open("data/scenarios/gio_scenarios_v2.json", 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Проверка метаданных
        assert "version" in data, "❌ Отсутствует version"
        assert "scenarios" in data, "❌ Отсутствует массив scenarios"
        print(f"✅ Версия: {data['version']}")

        # Проверка сценариев
        scenarios = data["scenarios"]
        print(f"✅ Найдено сценариев: {len(scenarios)}")

        required_fields = [
            "id", "name", "strategy", "side", "mtf",
            "volume_profile", "metrics", "clusters",
            "triggers", "tactic", "risk_profile"
        ]

        errors = []
        for i, scenario in enumerate(scenarios):
            scenario_id = scenario.get("id", f"UNKNOWN_{i}")

            for field in required_fields:
                if field not in scenario:
                    errors.append(f"❌ {scenario_id}: Отсутствует поле '{field}'")

        if errors:
            print("\n⚠️ Найдены ошибки:")
            for error in errors[:10]:  # Показываем первые 10
                print(f"   {error}")
            if len(errors) > 10:
                print(f"   ... и ещё {len(errors) - 10} ошибок")
            return False

        print("✅ Все сценарии имеют правильную структуру")

        # Статистика
        strategies = {}
        for scenario in scenarios:
            strat = scenario.get("strategy", "unknown")
            strategies[strat] = strategies.get(strat, 0) + 1

        print("\n📊 Статистика по стратегиям:")
        for strat, count in strategies.items():
            print(f"   • {strat}: {count} сценариев")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def test_strategies_structure():
    """Тест 3: Проверка структуры strategies"""
    print("\n🔍 ТЕСТ 3: Проверка структуры strategies")
    print("=" * 70)

    try:
        with open("data/strategies/strategy_extensions_v1.1.json", 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Проверка основных секций
        required_sections = [
            "strategy_selector",
            "market_regime_detection",
            "global_rules",
            "condition_validator",
            "strategy_metadata"
        ]

        for section in required_sections:
            if section not in data:
                print(f"❌ Отсутствует секция: {section}")
                return False
            print(f"✅ Секция '{section}' найдена")

        # Проверка market_regime_detection
        regimes = data["market_regime_detection"]["regimes"]
        print(f"\n📊 Определено рыночных режимов: {len(regimes)}")
        for regime, info in regimes.items():
            print(f"   • {regime}: {info.get('description', 'Нет описания')}")

        # Проверка strategy_selector
        selector = data["strategy_selector"]["market_regime"]
        print(f"\n📊 Маппинг режимов на стратегии:")
        for regime, strategies in selector.items():
            print(f"   • {regime} → {', '.join(strategies)}")

        print("\n✅ Структура strategies корректна")
        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def test_cross_references():
    """Тест 4: Проверка перекрёстных ссылок"""
    print("\n🔍 ТЕСТ 4: Проверка перекрёстных ссылок")
    print("=" * 70)

    try:
        # Загружаем оба файла
        with open("data/scenarios/gio_scenarios_v2.json", 'r', encoding='utf-8') as f:
            scenarios_data = json.load(f)

        with open("data/strategies/strategy_extensions_v1.1.json", 'r', encoding='utf-8') as f:
            strategies_data = json.load(f)

        # Получаем список всех стратегий из scenarios
        used_strategies = set()
        for scenario in scenarios_data["scenarios"]:
            used_strategies.add(scenario["strategy"])

        # Получаем список определённых стратегий в strategy_metadata
        defined_strategies = set(strategies_data["strategy_metadata"].keys())

        print(f"📊 Используемые стратегии в scenarios: {sorted(used_strategies)}")
        print(f"📊 Определённые стратегии в metadata: {sorted(defined_strategies)}")

        # Проверяем что все используемые стратегии определены
        missing = used_strategies - defined_strategies
        if missing:
            print(f"\n❌ Стратегии используются, но не определены: {missing}")
            return False

        # Проверяем что все определённые стратегии используются
        unused = defined_strategies - used_strategies
        if unused:
            print(f"\n⚠️ Стратегии определены, но не используются: {unused}")

        print("\n✅ Все перекрёстные ссылки корректны")
        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def run_all_tests():
    """Запуск всех тестов"""
    print("\n" + "=" * 70)
    print("🧪 ТЕСТИРОВАНИЕ ЭТАПА 1: JSON ФАЙЛЫ")
    print("=" * 70)

    tests = [
        ("JSON Синтаксис", test_json_syntax),
        ("Структура Scenarios", test_scenarios_structure),
        ("Структура Strategies", test_strategies_structure),
        ("Перекрёстные ссылки", test_cross_references)
    ]

    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n❌ Критическая ошибка в тесте '{name}': {e}")
            results[name] = False

    # Итоги
    print("\n" + "=" * 70)
    print("📊 ИТОГИ ТЕСТИРОВАНИЯ")
    print("=" * 70)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status} - {name}")

    print("\n" + "=" * 70)
    print(f"Результат: {passed}/{total} тестов пройдено")

    if passed == total:
        print("🎉 ВСЕ ТЕСТЫ ПРОЙДЕНЫ! Можно переходить к Этапу 2")
    else:
        print("⚠️ Есть ошибки. Исправьте перед продолжением")

    print("=" * 70 + "\n")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
