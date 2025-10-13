#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Schema - Standalone Migration Script
NO DEPENDENCIES VERSION
"""

import sqlite3
import os
from pathlib import Path


# ==================== НАСТРОЙКИ ====================

# Автоматически определяем путь к БД
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATABASE_PATH = DATA_DIR / "gio_bot.db"

# Создаём папку data если её нет
DATA_DIR.mkdir(exist_ok=True)


# ==================== SQL СХЕМА ТАБЛИЦЫ SIGNALS ====================

CREATE_SIGNALS_TABLE = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    stop_loss REAL NOT NULL,
    tp1 REAL NOT NULL,
    tp2 REAL NOT NULL,
    tp3 REAL NOT NULL,
    exit_price REAL,
    profit_percent REAL,
    scenario_id TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    quality_score REAL,
    risk_reward REAL,

    -- НОВЫЕ ПОЛЯ ДЛЯ AUTO ROI TRACKER
    tp1_reached INTEGER DEFAULT 0,
    tp2_reached INTEGER DEFAULT 0,
    tp3_reached INTEGER DEFAULT 0,
    realized_roi REAL DEFAULT 0,

    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
"""


def initialize_database():
    """Инициализация базы данных с правильной схемой"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Создаём таблицу signals
        cursor.execute(CREATE_SIGNALS_TABLE)

        conn.commit()
        conn.close()

        print(f"✅ Database initialized: {DATABASE_PATH}")
        return True

    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        return False


def migrate_database():
    """Миграция существующей БД - добавление новых полей"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        # Проверяем какие колонки уже есть
        cursor.execute("PRAGMA table_info(signals)")
        existing_columns = [row[1] for row in cursor.fetchall()]

        print(f"📊 Existing columns: {len(existing_columns)}")

        # Добавляем новые колонки если их нет
        new_columns = {
            "tp1_reached": "INTEGER DEFAULT 0",
            "tp2_reached": "INTEGER DEFAULT 0",
            "tp3_reached": "INTEGER DEFAULT 0",
            "realized_roi": "REAL DEFAULT 0"
        }

        added_count = 0
        for column_name, column_def in new_columns.items():
            if column_name not in existing_columns:
                sql = f"ALTER TABLE signals ADD COLUMN {column_name} {column_def}"
                cursor.execute(sql)
                print(f"✅ Added column: {column_name}")
                added_count += 1
            else:
                print(f"⏭️ Column already exists: {column_name}")

        conn.commit()
        conn.close()

        if added_count > 0:
            print(f"✅ Migration completed: {added_count} columns added")
        else:
            print("✅ Migration completed: No new columns needed")

        return True

    except Exception as e:
        print(f"❌ Migration error: {e}")
        import traceback
        traceback.print_exc()
        return False


def verify_schema():
    """Проверка схемы БД"""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(signals)")
        columns = cursor.fetchall()

        print("\n" + "="*80)
        print("📊 TABLE SCHEMA: signals")
        print("="*80)

        for col in columns:
            col_id, name, col_type, not_null, default_val, pk = col
            null_str = "NOT NULL" if not_null else "NULL"
            default_str = f"DEFAULT {default_val}" if default_val else ""
            pk_str = "PK" if pk else ""

            print(f"{col_id:2d}. {name:20s} {col_type:10s} {null_str:8s} {default_str:20s} {pk_str}")

        print("="*80)
        print(f"Total columns: {len(columns)}")
        print("="*80 + "\n")

        conn.close()
        return True

    except Exception as e:
        print(f"❌ Schema verification error: {e}")
        return False


def main():
    """Run migration manually"""
    print("")
    print("="*80)
    print("  🔧 GIO CRYPTO BOT - DATABASE MIGRATION TOOL")
    print("="*80)
    print(f"  Database: {DATABASE_PATH}")
    print("="*80)
    print("")

    # 1. Initialize
    print("[1/3] Initializing database...")
    if not initialize_database():
        return False

    # 2. Migrate
    print("\n[2/3] Migrating schema...")
    if not migrate_database():
        return False

    # 3. Verify
    print("\n[3/3] Verifying schema...")
    if not verify_schema():
        return False

    print("="*80)
    print("  ✅ MIGRATION COMPLETED SUCCESSFULLY!")
    print("="*80)
    print("")
    print("Next steps:")
    print("  1. Check the log above for any errors")
    print("  2. Run the bot: python main.py")
    print("")

    return True


if __name__ == "__main__":
    try:
        success = main()
        exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n⚠️ Migration cancelled by user")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
