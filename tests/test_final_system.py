# -*- coding: utf-8 -*-
"""
Финальный системный тест GIO Bot
Проверка всех компонентов в комплексе
"""

import sys
from pathlib import Path
import asyncio

# Добавляем корневую директорию в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from systems.unified_scenario_matcher import EnhancedScenarioMatcher
from systems.market_regime_detector import MarketRegimeDetector
from trading.signal_recorder import SignalRecorder
from notifications.enhanced_telegram_formatter import EnhancedTelegramFormatter
from analytics.signal_analytics import SignalAnalytics
from config.settings import logger


class SystemTest:
    """Класс для системного тестирования бота"""

    def __init__(self):
        self.results = {
            "total_tests": 0,
            "passed": 0,
            "failed": 0,
            "errors": []
        }

    def test(self, name: str, func):
        """Wrapper для выполнения теста"""
        self.results["total_tests"] += 1
        print(f"\n🔍 Тест: {name}")
        print("-" * 70)

        try:
            result = func()
            if result:
                print(f"✅ ПРОЙДЕН")
                self.results["passed"] += 1
                return True
            else:
                print(f"❌ ПРОВАЛЕН")
                self.results["failed"] += 1
                self.results["errors"].append(name)
                return False
        except Exception as e:
            print(f"❌ ОШИБКА: {e}")
            self.results["failed"] += 1
            self.results["errors"].append(f"{name}: {e}")
            import traceback
            traceback.print_exc()
            return False

    def print_summary(self):
        """Вывод итогов тестирования"""
        print("\n" + "=" * 70)
        print("📊 ИТОГИ СИСТЕМНОГО ТЕСТИРОВАНИЯ")
        print("=" * 70)
        print(f"✅ Пройдено: {self.results['passed']}/{self.results['total_tests']}")
        print(f"❌ Провалено: {self.results['failed']}/{self.results['total_tests']}")

        if self.results['failed'] > 0:
            print(f"\n❌ Проваленные тесты:")
            for error in self.results['errors']:
                print(f"   - {error}")

        success_rate = (self.results['passed'] / self.results['total_tests'] * 100) if self.results['total_tests'] > 0 else 0
        print(f"\n📈 Success Rate: {success_rate:.1f}%")
        print("=" * 70 + "\n")


def test_market_regime_detector():
    """Тест 1: MarketRegimeDetector"""
    try:
        detector = MarketRegimeDetector()

        # ========== Тест 1: TRENDING ==========
        trending_data = {
            "close": 62000,
            "volume": 3000,
            "candles": [{"close": 58000 + i * 200} for i in range(100)],  # Сильный рост
            "atr": 1800,                    # Высокая волатильность
            "bb_width_percentile": 75,      # Широкие bollinger bands
            "atr_percentile": 80            # Высокий ATR percentile
        }

        regime_1 = detector.detect(trending_data)
        print(f"   Тест TRENDING: {regime_1}")

        # ========== Тест 2: RANGING ==========
        ranging_data = {
            "close": 60000,
            "volume": 1500,
            "candles": [
                {"close": 60000 + (100 if i % 2 == 0 else -100)}
                for i in range(100)
            ],  # Боковик
            "atr": 500,                     # Низкая волатильность
            "bb_width_percentile": 30,      # Узкие bollinger bands
            "atr_percentile": 25
        }

        regime_2 = detector.detect(ranging_data)
        print(f"   Тест RANGING: {regime_2}")

        # ========== Тест 3: VOLATILE ==========
        volatile_data = {
            "close": 60000,
            "volume": 4000,
            "candles": [
                {"close": 60000 + (500 if i % 3 == 0 else -400)}
                for i in range(100)
            ],  # Сильные колебания
            "atr": 2500,                    # Очень высокая волатильность
            "bb_width_percentile": 90,      # Очень широкие bands
            "atr_percentile": 95
        }

        regime_3 = detector.detect(volatile_data)
        print(f"   Тест VOLATILE: {regime_3}")

        # ========== Тест 4: BREAKOUT ==========
        breakout_data = {
            "close": 65000,                 # Резкий скачок
            "volume": 5000,                 # Высокий объём
            "candles": [
                {"close": 60000 if i < 50 else 60000 + (i - 50) * 300}
                for i in range(100)
            ],  # Прорыв после консолидации
            "atr": 2000,
            "bb_width_percentile": 85,
            "atr_percentile": 88
        }

        regime_4 = detector.detect(breakout_data)
        print(f"   Тест BREAKOUT: {regime_4}")

        # ========== Тест 5: SQUEEZE ==========
        squeeze_data = {
            "close": 60000,
            "volume": 800,                  # Очень низкий объём
            "candles": [
                {"close": 60000 + (10 if i % 2 == 0 else -10)}
                for i in range(100)
            ],  # Очень узкий диапазон
            "atr": 200,                     # Минимальная волатильность
            "bb_width_percentile": 10,      # Очень узкие bands
            "atr_percentile": 5
        }

        regime_5 = detector.detect(squeeze_data)
        print(f"   Тест SQUEEZE: {regime_5}")

        # ========== Проверка результатов ==========
        all_regimes = [regime_1, regime_2, regime_3, regime_4, regime_5]
        valid_regimes = [
            "trending", "ranging", "volatile", "breakout", "squeeze",
            "neutral", "expanding", "contracting", "consolidation"
        ]

        # Проверяем что все режимы валидны
        all_valid = all(r in valid_regimes for r in all_regimes)

        if all_valid:
            print(f"   ✅ Все режимы определены корректно")
            unique_count = len(set(all_regimes))
            print(f"   ✅ Уникальных режимов: {unique_count}/5")
            return True
        else:
            invalid = [r for r in all_regimes if r not in valid_regimes]
            print(f"   ❌ Некорректные режимы: {invalid}")
            return False

    except Exception as e:
        print(f"   Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False




def test_enhanced_scenario_matcher():
    """Тест 2: EnhancedScenarioMatcher"""
    try:
        matcher = EnhancedScenarioMatcher()

        market_data = {
            "symbol": "BTCUSDT",
            "close": 60000,
            "volume": 2000,
            "candles": [{"close": 60000} for _ in range(100)]
        }

        # ✅ ИСПРАВЛЕНО: Добавлены недостающие индикаторы
        indicators = {
            "adx": 35,
            "rsi": 65,
            "macd": 100,
            "macd_signal": 80,
            "macd_above_signal": True,
            "volume_ma20": 1000,
            "atr": 1200,
            "bb_width_percentile": 55,
            "atr_percentile": 60,
            "bullish_continuation_candle": True,  # ← ДОБАВЛЕНО
            "volume_spike": True,                  # ← ДОБАВЛЕНО
        }

        mtf_trends = {"1H": "bullish", "4H": "bullish", "1D": "bullish"}
        volume_profile = {"poc": 59500, "vah": 60500, "val": 59000, "vwap": 59800}
        news_sentiment = {"overall": "bullish", "overall_score": 0.2}

        signal = matcher.match_scenario(
            symbol="BTCUSDT",
            market_data=market_data,
            indicators=indicators,
            mtf_trends=mtf_trends,
            volume_profile=volume_profile,
            news_sentiment=news_sentiment,
            veto_checks={}
        )

        if signal:
            print(f"   Сценарий: {signal['scenario_id']}")
            print(f"   Стратегия: {signal['strategy']}")
            print(f"   Уверенность: {signal['confidence']}")
            return True
        else:
            print("   Сигнал не найден")
            return False

    except Exception as e:
        print(f"   Ошибка: {e}")
        return False



def test_signal_recorder():
    """Тест 3: SignalRecorder"""
    try:
        recorder = SignalRecorder()

        signal_id = recorder.record_signal(
            symbol="BTCUSDT",
            direction="LONG",
            entry_price=60000,
            stop_loss=58800,
            tp1=61800,
            tp2=63600,
            tp3=65400,
            scenario_id="SCN_001",
            status="active",
            quality_score=85.0,
            risk_reward=2.5,
            strategy="momentum",
            market_regime="trending",
            confidence="medium",
            phase="continuation",
            risk_profile="aggressive",
            tactic_name="momentum_aggr",
            validation_score=0.85,
            trigger_score=1.0,
        )

        if signal_id > 0:
            print(f"   Сигнал сохранён: ID #{signal_id}")

            # Проверяем что можем получить сигнал обратно
            saved = recorder.get_signal_by_id(signal_id)
            if saved:
                print(f"   Данные получены: {saved['symbol']} {saved['direction']}")
                print(f"   Strategy: {saved.get('strategy', 'N/A')}")
                return True

        return False

    except Exception as e:
        print(f"   Ошибка: {e}")
        return False


def test_telegram_formatter():
    """Тест 4: EnhancedTelegramFormatter"""
    try:
        signal = {
            "symbol": "BTCUSDT",
            "direction": "LONG",
            "scenario_id": "SCN_001",
            "scenario_name": "Momentum Long (Strong)",
            "strategy": "momentum",
            "market_regime": "trending",
            "confidence": "medium",
            "phase": "continuation",
            "risk_profile": "aggressive",
            "entry_price": 60000,
            "stop_loss": 58800,
            "tp1": 61800,
            "tp2": 63600,
            "tp3": 65400,
            "quality_score": 85.0,
            "risk_reward": 2.5,
            "validation": {
                "volume_confirmation": True,
                "trend_alignment": True,
                "momentum_check": True,
            },
            "influenced_metrics": {
                "adx": 35,
                "volume_ratio": 2.0,
                "trend_1h": "bullish",
                "trend_4h": "bullish",
            }
        }

        message = EnhancedTelegramFormatter.format_new_signal(signal)

        # Проверяем что сообщение содержит ключевые элементы
        required = [
            "НОВЫЙ СИГНАЛ", "BTCUSDT", "SCN_001",
            "MOMENTUM", "TRENDING", "MEDIUM"
        ]

        all_present = all(keyword in message for keyword in required)

        if all_present:
            print(f"   Сообщение сформировано ({len(message)} символов)")
            print(f"   Все ключевые элементы присутствуют")
            return True
        else:
            missing = [k for k in required if k not in message]
            print(f"   Отсутствуют элементы: {missing}")
            return False

    except Exception as e:
        print(f"   Ошибка: {e}")
        return False


def test_signal_analytics():
    """Тест 5: SignalAnalytics"""
    try:
        analytics = SignalAnalytics()

        # Получаем общую статистику
        overall = analytics.get_overall_stats(30)
        print(f"   Всего сигналов: {overall.get('total_signals', 0)}")
        print(f"   Win Rate: {overall.get('win_rate', 0):.1f}%")

        # Получаем статистику по стратегиям
        strategies = analytics.get_stats_by_strategy(30)
        print(f"   Стратегий отслеживается: {len(strategies)}")

        # Получаем топ сценариев
        top = analytics.get_top_performing_scenarios(30, limit=5)
        print(f"   Топ сценариев: {len(top)}")

        return True

    except Exception as e:
        print(f"   Ошибка: {e}")
        return False


def test_json_files():
    """Тест 6: Наличие и валидность JSON файлов"""
    import json

    try:
        # Проверяем scenarios
        scenarios_path = Path("data/scenarios/gio_scenarios_v2.json")
        if not scenarios_path.exists():
            print(f"   ❌ Файл не найден: {scenarios_path}")
            return False

        with open(scenarios_path, 'r', encoding='utf-8') as f:
            scenarios = json.load(f)
            print(f"   ✅ Сценариев загружено: {len(scenarios.get('scenarios', []))}")

        # Проверяем strategies
        strategies_path = Path("data/strategies/strategy_extensions_v1.1.json")
        if not strategies_path.exists():
            print(f"   ❌ Файл не найден: {strategies_path}")
            return False

        with open(strategies_path, 'r', encoding='utf-8') as f:
            strategies = json.load(f)
            print(f"   ✅ Стратегий загружено: {len(strategies.get('strategies', []))}")

        return True

    except Exception as e:
        print(f"   Ошибка: {e}")
        return False


def test_database_schema():
    """Тест 7: Схема базы данных"""
    import sqlite3

    try:
        from config.settings import DATABASE_PATH

        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(signals)")
        columns = cursor.fetchall()
        conn.close()

        column_names = [col[1] for col in columns]

        required_columns = [
            "scenario_id", "strategy", "market_regime",
            "confidence", "phase", "risk_profile",
            "tactic_name", "validation_score", "trigger_score"
        ]

        missing = [col for col in required_columns if col not in column_names]

        if missing:
            print(f"   ❌ Отсутствуют колонки: {missing}")
            return False

        print(f"   ✅ Всего колонок: {len(columns)}")
        print(f"   ✅ Все обязательные колонки присутствуют")
        return True

    except Exception as e:
        print(f"   Ошибка: {e}")
        return False


def main():
    """Главная функция теста"""
    print("\n" + "=" * 70)
    print("🧪 ФИНАЛЬНЫЙ СИСТЕМНЫЙ ТЕСТ GIO BOT")
    print("=" * 70)

    tester = SystemTest()

    # Выполняем все тесты
    tester.test("1. MarketRegimeDetector", test_market_regime_detector)
    tester.test("2. EnhancedScenarioMatcher", test_enhanced_scenario_matcher)
    tester.test("3. SignalRecorder", test_signal_recorder)
    tester.test("4. EnhancedTelegramFormatter", test_telegram_formatter)
    tester.test("5. SignalAnalytics", test_signal_analytics)
    tester.test("6. JSON Files Validation", test_json_files)
    tester.test("7. Database Schema", test_database_schema)

    # Итоги
    tester.print_summary()

    # Return exit code
    return 0 if tester.results['failed'] == 0 else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
