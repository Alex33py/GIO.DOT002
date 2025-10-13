# update_database.py
import sqlite3
from pathlib import Path

DATABASE_PATH = Path("data/gio_bot.db")


def update_signals_table():
    """Добавить недостающие колонки для ROI мониторинга"""

    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Список новых колонок
    columns_to_add = [
        ("roi", "REAL DEFAULT 0.0"),
        ("tp1_hit", "INTEGER DEFAULT 0"),
        ("tp2_hit", "INTEGER DEFAULT 0"),
        ("tp3_hit", "INTEGER DEFAULT 0"),
        ("sl_hit", "INTEGER DEFAULT 0"),
        ("close_time", "TEXT"),
    ]

    # Добавляем каждую колонку
    for column_name, column_type in columns_to_add:
        try:
            cursor.execute(
                f"ALTER TABLE signals ADD COLUMN {column_name} {column_type}"
            )
            print(f"✅ Колонка '{column_name}' добавлена")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"⚠️  Колонка '{column_name}' уже существует")
            else:
                print(f"❌ Ошибка добавления '{column_name}': {e}")

    conn.commit()
    conn.close()
    print("\n✅ База данных обновлена!")


if __name__ == "__main__":
    update_signals_table()
