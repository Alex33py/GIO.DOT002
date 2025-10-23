#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Скрипт для добавления тестовых сигналов в unified_signals
"""

import sqlite3
import os
from datetime import datetime
from config.settings import DATA_DIR

db_path = os.path.join(DATA_DIR, "gio_crypto_bot.db")

print(f"📊 Добавление тестовых сигналов в: {db_path}\n")

# Тестовые сигналы
test_signals = [
    {
        "signal_id": "TEST_BTC_001",
        "symbol": "BTCUSDT",
        "direction": "LONG",
        "entry_price": 110542.0,
        "scenario_id": "ACCUMULATION_PHASE_1",
        "scenario_score": 78.5,
        "confidence": 78.5,
        "tp1_price": 112300.0,
        "tp2_price": 114500.0,
        "tp3_price": 117000.0,
        "sl_price": 109200.0,
        "status": "ACTIVE",
    },
    {
        "signal_id": "TEST_ETH_001",
        "symbol": "ETHUSDT",
        "direction": "SHORT",
        "entry_price": 3945.00,
        "scenario_id": "DISTRIBUTION_PHASE_2",
        "scenario_score": 65.2,
        "confidence": 65.2,
        "tp1_price": 3850.0,
        "tp2_price": 3720.0,
        "tp3_price": 3600.0,
        "sl_price": 4020.0,
        "status": "ACTIVE",
    },
    {
        "signal_id": "TEST_SOL_001",
        "symbol": "SOLUSDT",
        "direction": "LONG",
        "entry_price": 193.45,
        "scenario_id": "SPRING_BREAKOUT",
        "scenario_score": 61.8,
        "confidence": 61.8,
        "tp1_price": 198.50,
        "tp2_price": 205.00,
        "tp3_price": 212.00,
        "sl_price": 190.00,
        "status": "ACTIVE",
    },
    {
        "signal_id": "TEST_XRP_001",
        "symbol": "XRPUSDT",
        "direction": "LONG",
        "entry_price": 2.40,
        "scenario_id": "MARKUP_PHASE",
        "scenario_score": 55.3,
        "confidence": 55.3,
        "tp1_price": 2.50,
        "tp2_price": 2.62,
        "tp3_price": 2.75,
        "sl_price": 2.35,
        "status": "ACTIVE",
    },
    {
        "signal_id": "TEST_BNB_001",
        "symbol": "BNBUSDT",
        "direction": "SHORT",
        "entry_price": 1152.90,
        "scenario_id": "UPTHRUST",
        "scenario_score": 48.7,
        "confidence": 48.7,
        "tp1_price": 1130.0,
        "tp2_price": 1110.0,
        "tp3_price": 1090.0,
        "sl_price": 1170.0,
        "status": "ACTIVE",
    },
]

INSERT_SQL = """
INSERT OR REPLACE INTO unified_signals (
    signal_id, symbol, direction, entry_price,
    scenario_id, scenario_score, confidence,
    tp1_price, tp2_price, tp3_price, sl_price,
    status, timestamp
) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

try:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        print("🔧 Добавление тестовых сигналов...\n")

        for signal in test_signals:
            cursor.execute(
                INSERT_SQL,
                (
                    signal["signal_id"],
                    signal["symbol"],
                    signal["direction"],
                    signal["entry_price"],
                    signal["scenario_id"],
                    signal["scenario_score"],
                    signal["confidence"],
                    signal["tp1_price"],
                    signal["tp2_price"],
                    signal["tp3_price"],
                    signal["sl_price"],
                    signal["status"],
                    datetime.now().isoformat(),
                ),
            )

            emoji = "🟢" if signal["direction"] == "LONG" else "🔴"
            print(f"{emoji} {signal['symbol']} - {signal['scenario_id']}")
            print(f"   Entry: ${signal['entry_price']:.2f} | Score: {signal['scenario_score']:.1f}%")
            print(f"   TP1: ${signal['tp1_price']:.2f} | SL: ${signal['sl_price']:.2f}\n")

        conn.commit()

        # Проверка
        cursor.execute("SELECT COUNT(*) FROM unified_signals WHERE status = 'ACTIVE'")
        count = cursor.fetchone()[0]

        print(f"✅ Добавлено {count} активных сигналов!")

except Exception as e:
    print(f"❌ Ошибка при добавлении сигналов: {e}")
    raise

print("\n🎉 Тестовые данные готовы! Теперь /dashboard покажет сигналы.")
