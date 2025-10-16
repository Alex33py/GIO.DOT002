#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlite3
import os

db_path = "data/gio_bot.db"

print(f"📊 Создание таблицы unified_signals в: {db_path}\n")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS unified_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id TEXT UNIQUE NOT NULL,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    scenario_id TEXT,
    scenario_score REAL DEFAULT 0,
    confidence REAL DEFAULT 0,
    tp1_price REAL,
    tp2_price REAL,
    tp3_price REAL,
    sl_price REAL,
    tp1_hit INTEGER DEFAULT 0,
    tp2_hit INTEGER DEFAULT 0,
    tp3_hit INTEGER DEFAULT 0,
    sl_hit INTEGER DEFAULT 0,
    current_roi REAL DEFAULT 0,
    max_roi REAL DEFAULT 0,
    status TEXT DEFAULT 'ACTIVE',
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    closed_at DATETIME,
    notes TEXT
);
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_symbol ON unified_signals(symbol);",
    "CREATE INDEX IF NOT EXISTS idx_status ON unified_signals(status);",
    "CREATE INDEX IF NOT EXISTS idx_timestamp ON unified_signals(timestamp DESC);",
    "CREATE INDEX IF NOT EXISTS idx_scenario_score ON unified_signals(scenario_score DESC);",
]

try:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()

        print("🔧 Создание таблицы unified_signals...")
        cursor.execute(CREATE_TABLE_SQL)
        print("✅ Таблица создана успешно!")

        print("\n🔧 Создание индексов...")
        for idx_sql in CREATE_INDEXES_SQL:
            cursor.execute(idx_sql)
        print("✅ Индексы созданы успешно!")

        conn.commit()

        cursor.execute("PRAGMA table_info(unified_signals)")
        columns = cursor.fetchall()

        print("\n📋 Структура таблицы unified_signals:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")

        print(f"\n✅ Таблица unified_signals готова!")
        print(f"📊 Всего колонок: {len(columns)}")

except Exception as e:
    print(f"❌ Ошибка: {e}")
    raise

print("\n🎉 Готово! Теперь можно запустить бота.")
