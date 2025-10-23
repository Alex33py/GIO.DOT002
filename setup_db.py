#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Setup database for GIO Bot
"""

import sqlite3

def setup_database():
    """Создаёт необходимые таблицы в БД"""
    conn = sqlite3.connect('gio.db')
    cursor = conn.cursor()

    # Создаём таблицу signals
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_price REAL NOT NULL,
            tp1 REAL,
            tp2 REAL,
            tp3 REAL,
            sl REAL,
            status TEXT DEFAULT 'active',
            roi REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            closed_at TIMESTAMP,
            notes TEXT
        )
    """)

    print("✅ Таблица 'signals' создана!")

    # Добавляем тестовые данные
    test_signals = [
        ('BTCUSDT', 'LONG', 67000.0, 68500.0, 69000.0, 70000.0, 66000.0, 'active', None),
        ('ETHUSDT', 'LONG', 3400.0, 3600.0, 3700.0, 3800.0, 3300.0, 'active', None),
        ('SOLUSDT', 'SHORT', 180.0, 175.0, 170.0, 165.0, 185.0, 'closed_profit', 2.8),
        ('BNBUSDT', 'LONG', 580.0, 600.0, 610.0, 620.0, 570.0, 'closed_profit', 3.4),
        ('ADAUSDT', 'SHORT', 0.65, 0.63, 0.62, 0.60, 0.67, 'closed_loss', -3.1),
    ]

    cursor.executemany("""
        INSERT INTO signals (symbol, direction, entry_price, tp1, tp2, tp3, sl, status, roi)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, test_signals)

    conn.commit()
    print(f"✅ Добавлено {len(test_signals)} тестовых сигналов!")

    # Проверяем результат
    cursor.execute("SELECT COUNT(*) FROM signals")
    count = cursor.fetchone()[0]
    print(f"📊 Всего сигналов в БД: {count}")

    conn.close()

if __name__ == "__main__":
    setup_database()
