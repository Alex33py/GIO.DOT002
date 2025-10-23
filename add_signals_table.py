import sqlite3
import os

# Путь к вашей БД
DB_PATH = "data/gio_crypto_bot.db"

print(f"🔍 Подключаемся к БД: {DB_PATH}")

# Проверяем существование БД
if not os.path.exists(DB_PATH):
    print(f"❌ БД не найдена: {DB_PATH}")
    exit(1)

# Подключаемся к БД
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

print("📋 Создаём таблицу signals...")

# Создаём таблицу signals
cursor.execute("""
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    timeframe TEXT,
    signal_type TEXT,
    price REAL,
    confidence REAL,
    indicators TEXT,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
)
""")

conn.commit()

# Проверяем создание
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signals'")
result = cursor.fetchone()

if result:
    print("✅ Таблица signals создана успешно!")

    # Показываем структуру таблицы
    cursor.execute("PRAGMA table_info(signals)")
    columns = cursor.fetchall()
    print("\n📊 Структура таблицы signals:")
    for col in columns:
        print(f"   - {col[1]} ({col[2]})")
else:
    print("❌ Ошибка создания таблицы!")

conn.close()
print("\n🎉 Готово!")
