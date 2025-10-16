#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Миграция БД: Добавление колонки scenario_id в таблицу signals
"""

import sqlite3
import sys


def add_scenario_id_column():
    """Добавляет колонку scenario_id в таблицу signals"""
    try:
        # Подключаемся к БД
        conn = sqlite3.connect("data/gio_crypto_bot.db")
        cursor = conn.cursor()

        # Проверяем, существует ли колонка
        cursor.execute("PRAGMA table_info(signals)")
        columns = [col[1] for col in cursor.fetchall()]

        if "scenario_id" in columns:
            print("✅ Колонка scenario_id уже существует в таблице signals")
            conn.close()
            return True

        # Добавляем колонку
        cursor.execute(
            "ALTER TABLE signals ADD COLUMN scenario_id TEXT DEFAULT 'unknown'"
        )
        conn.commit()

        print("✅ Колонка scenario_id успешно добавлена в таблицу signals")

        # Проверяем результат
        cursor.execute("PRAGMA table_info(signals)")
        columns = [col[1] for col in cursor.fetchall()]

        if "scenario_id" in columns:
            print("✅ УСПЕХ! Колонка scenario_id теперь доступна")
            conn.close()
            return True
        else:
            print("❌ ОШИБКА: Колонка не была добавлена")
            conn.close()
            return False

    except sqlite3.Error as e:
        print(f"❌ Ошибка SQLite: {e}")
        return False
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        return False


if __name__ == "__main__":
    print("🔧 Запуск миграции БД...")
    success = add_scenario_id_column()

    if success:
        print("\n🎉 Миграция завершена успешно!")
        print("🚀 Теперь перезапустите бота: python main.py")
        sys.exit(0)
    else:
        print("\n❌ Миграция не удалась")
        sys.exit(1)
