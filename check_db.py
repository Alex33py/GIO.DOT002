import sqlite3

conn = sqlite3.connect('gio_bot.db')
cursor = conn.cursor()

# Список таблиц
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print('📊 Таблицы в БД:', [t[0] for t in tables])

# Если нет signals — создай
if 'signals' not in [t[0] for t in tables]:
    cursor.execute('''
        CREATE TABLE signals (
            id INTEGER PRIMARY KEY,
            symbol TEXT,
            direction TEXT,
            entry_price REAL,
            stop_loss REAL,
            take_profit_1 REAL,
            take_profit_2 REAL,
            take_profit_3 REAL,
            scenario TEXT,
            confidence REAL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active'
        )
    ''')
    conn.commit()
    print('✅ Таблица signals создана!')
else:
    print('✅ Таблица signals уже существует!')

conn.close()
