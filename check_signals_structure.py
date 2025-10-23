import sqlite3

conn = sqlite3.connect('gio_trading.db')
cursor = conn.cursor()

# Получаем структуру таблицы signals
cursor.execute("PRAGMA table_info(signals)")
columns = cursor.fetchall()

print('📋 Структура таблицы signals:')
for col in columns:
    print(f'  - {col[1]} ({col[2]})')

conn.close()
