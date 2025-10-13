import sqlite3

# Подключаемся к БД
conn = sqlite3.connect("D:/GIO.BOT.02/data/gio_bot.db")
cursor = conn.cursor()

# Получаем структуру таблицы signals
cursor.execute("PRAGMA table_info(signals)")
columns = cursor.fetchall()

print("📊 Структура таблицы 'signals':")
print("=" * 50)
for col in columns:
    print(f"{col[1]:20} | {col[2]:10} | NOT NULL: {col[3]}")

conn.close()
