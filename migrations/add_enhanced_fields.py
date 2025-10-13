# -*- coding: utf-8 -*-
"""
Migration: Добавление полей для EnhancedScenarioMatcher v2.0
"""

import sqlite3
from pathlib import Path
from datetime import datetime


def migrate_database(db_path: str = "data/gio_bot.db"):
    """Добавить новые поля в таблицу signals"""

    print(f"\n🔧 МИГРАЦИЯ БД: {db_path}")
    print("=" * 70)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверяем существует ли таблица
        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name='signals'
        """)

        if not cursor.fetchone():
            print("❌ Таблица signals не найдена!")
            return False

        # Список новых полей для добавления
        new_columns = [
            ("scenario_id", "TEXT"),
            ("strategy", "TEXT"),
            ("market_regime", "TEXT"),
            ("confidence", "TEXT"),
            ("phase", "TEXT"),
            ("risk_profile", "TEXT"),
            ("tactic_name", "TEXT"),
            ("validation_score", "REAL"),
            ("trigger_score", "REAL")
        ]

        added_count = 0

        for column_name, column_type in new_columns:
            try:
                # Пытаемся добавить колонку
                cursor.execute(f"""
                    ALTER TABLE signals
                    ADD COLUMN {column_name} {column_type}
                """)
                print(f"✅ Добавлена колонка: {column_name} ({column_type})")
                added_count += 1
            except sqlite3.OperationalError as e:
                if "duplicate column name" in str(e):
                    print(f"⚠️  Колонка уже существует: {column_name}")
                else:
                    print(f"❌ Ошибка добавления {column_name}: {e}")

        conn.commit()

        # Создаём индексы для новых полей
        indexes = [
            ("idx_scenario_id", "scenario_id"),
            ("idx_strategy", "strategy"),
            ("idx_market_regime", "market_regime"),
            ("idx_confidence", "confidence")
        ]

        for idx_name, column in indexes:
            try:
                cursor.execute(f"""
                    CREATE INDEX IF NOT EXISTS {idx_name}
                    ON signals({column})
                """)
                print(f"✅ Создан индекс: {idx_name}")
            except Exception as e:
                print(f"⚠️  Индекс {idx_name}: {e}")

        conn.commit()
        conn.close()

        print(f"\n🎉 Миграция завершена! Добавлено {added_count} новых колонок")
        print("=" * 70 + "\n")

        return True

    except Exception as e:
        print(f"❌ Критическая ошибка миграции: {e}")
        return False


def verify_schema(db_path: str = "data/gio_bot.db"):
    """Проверить схему БД после миграции"""

    print("\n🔍 ПРОВЕРКА СХЕМЫ БД")
    print("=" * 70)

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Получаем информацию о колонках
        cursor.execute("PRAGMA table_info(signals)")
        columns = cursor.fetchall()

        print(f"📊 Всего колонок в таблице signals: {len(columns)}\n")

        required_columns = [
            "scenario_id", "strategy", "market_regime",
            "confidence", "phase", "risk_profile", "tactic_name"
        ]

        existing_columns = [col[1] for col in columns]

        for req_col in required_columns:
            if req_col in existing_columns:
                print(f"✅ {req_col}")
            else:
                print(f"❌ {req_col} - ОТСУТСТВУЕТ!")

        conn.close()

        print("=" * 70 + "\n")
        return True

    except Exception as e:
        print(f"❌ Ошибка проверки схемы: {e}")
        return False


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🗄️  DATABASE MIGRATION - Enhanced Scenario Matcher v2.0")
    print("=" * 70)

    # Выполняем миграцию
    success = migrate_database()

    if success:
        # Проверяем схему
        verify_schema()
        print("\n✅ Миграция успешно завершена!")
    else:
        print("\n❌ Миграция провалена!")

    print("=" * 70 + "\n")
