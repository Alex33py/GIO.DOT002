# -*- coding: utf-8 -*-
"""
Тест полной интеграции EnhancedScenarioMatcher в бота
"""

import sys
from pathlib import Path

# Добавляем корневую директорию в path
sys.path.insert(0, str(Path(__file__).parent.parent))

from systems.unified_scenario_matcher import EnhancedScenarioMatcher
from trading.signal_recorder import SignalRecorder
from notifications.enhanced_telegram_formatter import EnhancedTelegramFormatter


def test_full_integration():
    """Тест полного цикла: Matcher → Recorder → Telegram"""

    print("\n" + "=" * 70)
    print("🧪 ТЕСТ ПОЛНОЙ ИНТЕГРАЦИИ: End-to-End")
    print("=" * 70 + "\n")

    # ========== ШАГ 1: EnhancedScenarioMatcher ==========
    print("🔍 ШАГ 1: EnhancedScenarioMatcher")
    print("-" * 70)

    try:
        matcher = EnhancedScenarioMatcher()

        # Тестовые данные для momentum long
        market_data = {
            "symbol": "BTCUSDT",
            "close": 60000,
            "volume": 2000,
            "candles": [{"close": 60000} for _ in range(100)]
        }

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
            "bullish_continuation_candle": True
        }

        mtf_trends = {
            "1H": "bullish",
            "4H": "bullish",
            "1D": "bullish"
        }

        volume_profile = {
            "poc": 59500,
            "vah": 60500,
            "val": 59000,
            "vwap": 59800
        }

        news_sentiment = {
            "overall": "bullish",
            "overall_score": 0.2
        }

        veto_checks = {}

        signal = matcher.match_scenario(
            symbol="BTCUSDT",
            market_data=market_data,
            indicators=indicators,
            mtf_trends=mtf_trends,
            volume_profile=volume_profile,
            news_sentiment=news_sentiment,
            veto_checks=veto_checks
        )

        if not signal:
            print("❌ EnhancedScenarioMatcher не вернул сигнал!")
            return False

        signal["symbol"] = "BTCUSDT"

        print(f"✅ Сценарий найден: {signal['scenario_id']}")
        print(f"   Strategy: {signal['strategy']}")
        print(f"   Market Regime: {signal['market_regime']}")
        print(f"   Confidence: {signal['confidence']}")
        print(f"   Entry: ${signal['entry_price']:.2f}")
        print()

    except Exception as e:
        print(f"❌ Ошибка EnhancedScenarioMatcher: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ========== ШАГ 2: SignalRecorder ==========
    print("🔍 ШАГ 2: SignalRecorder")
    print("-" * 70)

    try:
        recorder = SignalRecorder()

        # Рассчитываем качество и R/R
        quality_score = 85.0
        rr_ratio = 2.5

        # Сохраняем сигнал
        signal_id = recorder.record_signal(
            symbol=signal["symbol"],
            direction=signal["direction"],
            entry_price=signal["entry_price"],
            stop_loss=signal["stop_loss"],
            tp1=signal["tp1"],
            tp2=signal["tp2"],
            tp3=signal["tp3"],
            scenario_id=signal["scenario_id"],
            status="active",
            quality_score=quality_score,
            risk_reward=rr_ratio,
            strategy=signal["strategy"],
            market_regime=signal["market_regime"],
            confidence=signal["confidence"],
            phase=signal["phase"],
            risk_profile=signal["risk_profile"],
            tactic_name=signal["tactic_name"],
            validation_score=0.85,
            trigger_score=1.0,
        )

        if signal_id == 0:
            print("❌ SignalRecorder не сохранил сигнал!")
            return False

        print(f"✅ Сигнал сохранён в БД с ID: #{signal_id}")

        # Проверяем что сигнал сохранился с новыми полями
        saved_signal = recorder.get_signal_by_id(signal_id)

        if not saved_signal:
            print("❌ Сигнал не найден в БД!")
            return False

        print(f"   Strategy (БД): {saved_signal.get('strategy', 'N/A')}")
        print(f"   Market Regime (БД): {saved_signal.get('market_regime', 'N/A')}")
        print(f"   Confidence (БД): {saved_signal.get('confidence', 'N/A')}")
        print()

        # Добавляем ID в signal для Telegram
        signal["id"] = signal_id
        signal["quality_score"] = quality_score
        signal["risk_reward"] = rr_ratio

    except Exception as e:
        print(f"❌ Ошибка SignalRecorder: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ========== ШАГ 3: EnhancedTelegramFormatter ==========
    print("🔍 ШАГ 3: EnhancedTelegramFormatter")
    print("-" * 70)

    try:
        # Форматируем сообщение
        telegram_message = EnhancedTelegramFormatter.format_new_signal(signal)

        print("✅ Telegram сообщение сформировано:")
        print()
        print(telegram_message)
        print()

        # Проверяем что сообщение содержит новые поля
        required_keywords = [
            "Стратегия:", "Режим рынка:", "Уверенность:",
            "Фаза:", "Риск-профиль:", "EnhancedScenarioMatcher"
        ]

        missing_keywords = []
        for keyword in required_keywords:
            if keyword not in telegram_message:
                missing_keywords.append(keyword)

        if missing_keywords:
            print(f"❌ Отсутствуют ключевые слова: {missing_keywords}")
            return False

        print("✅ Все ключевые поля присутствуют в сообщении")
        print()

    except Exception as e:
        print(f"❌ Ошибка EnhancedTelegramFormatter: {e}")
        import traceback
        traceback.print_exc()
        return False

    # ========== ИТОГОВАЯ ПРОВЕРКА ==========
    print("=" * 70)
    print("📊 ИТОГИ END-TO-END ТЕСТА")
    print("=" * 70)
    print("✅ EnhancedScenarioMatcher: OK")
    print("✅ SignalRecorder: OK")
    print("✅ EnhancedTelegramFormatter: OK")
    print()
    print("🎉 ПОЛНАЯ ИНТЕГРАЦИЯ РАБОТАЕТ!")
    print("=" * 70 + "\n")

    return True


if __name__ == "__main__":
    success = test_full_integration()
    exit(0 if success else 1)
