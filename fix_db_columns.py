#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Добавление колонок tp1_hit, tp2_hit, tp3_hit в таблицу signals
"""

import sqlite3

# Путь к БД
DB_PATH = "D:\\GIO.BOT.02\\data\\gio_bot.db"


def fix_database():
    """Добавление недостающих колонок"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Проверяем существующие колонки
        cursor.execute("PRAGMA table_info(signals)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"✅ Существующие колонки: {len(columns)}")

        # Добавляем tp1_hit
        if "tp1_hit" not in columns:
            cursor.execute("ALTER TABLE signals ADD COLUMN tp1_hit INTEGER DEFAULT 0")
            print("✅ Добавлена колонка tp1_hit")
        else:
            print("⏭️  Колонка tp1_hit уже существует")

        # Добавляем tp2_hit
        if "tp2_hit" not in columns:
            cursor.execute("ALTER TABLE signals ADD COLUMN tp2_hit INTEGER DEFAULT 0")
            print("✅ Добавлена колонка tp2_hit")
        else:
            print("⏭️  Колонка tp2_hit уже существует")

        # Добавляем tp3_hit
        if "tp3_hit" not in columns:
            cursor.execute("ALTER TABLE signals ADD COLUMN tp3_hit INTEGER DEFAULT 0")
            print("✅ Добавлена колонка tp3_hit")
        else:
            print("⏭️  Колонка tp3_hit уже существует")

        conn.commit()

        # Проверяем результат
        cursor.execute("PRAGMA table_info(signals)")
        columns_after = [row[1] for row in cursor.fetchall()]
        print(f"\n✅ ИТОГО колонок: {len(columns_after)}")
        print(f"   tp1_hit: {'✅' if 'tp1_hit' in columns_after else '❌'}")
        print(f"   tp2_hit: {'✅' if 'tp2_hit' in columns_after else '❌'}")
        print(f"   tp3_hit: {'✅' if 'tp3_hit' in columns_after else '❌'}")

        conn.close()
        print("\n🎉 ГОТОВО! ПЕРЕЗАПУСКАЙ БОТА!")

    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    fix_database()
