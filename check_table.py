import sqlite3
import os

DB_PATH = "data/gio_crypto_bot.db"

if not os.path.exists(DB_PATH):
    print(f"❌ БД не найдена: {DB_PATH}")
    exit(1)

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Проверяем существование таблицы signals
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signals'")
result = cursor.fetchone()

if result:
    print("✅ Таблица signals СУЩЕСТВУЕТ!")

    # Показываем структуру
    cursor.execute("PRAGMA table_info(signals)")
    columns = cursor.fetchall()
    print("\n📊 Структура таблицы:")
    for col in columns:
        print(f"   {col[0]}. {col[1]} ({col[2]})")

    # Показываем количество записей
    cursor.execute("SELECT COUNT(*) FROM signals")
    count = cursor.fetchone()[0]
    print(f"\n📈 Количество записей: {count}")
else:
    print("❌ Таблица signals НЕ СУЩЕСТВУЕТ!")

conn.close()
