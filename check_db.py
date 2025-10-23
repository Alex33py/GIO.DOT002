import sqlite3

conn = sqlite3.connect('gio_trading.db')
cursor = conn.cursor()

# Получаем список таблиц
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]

print('📊 Таблицы в базе данных gio_trading.db:')
for table in tables:
    print(f'  - {table}')

conn.close()
