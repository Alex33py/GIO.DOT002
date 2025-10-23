import sqlite3

conn = sqlite3.connect('gio_trading.db')
cursor = conn.cursor()

# Список колонок, которые нужно добавить
columns_to_add = [
    ('close_price', 'REAL'),
    ('result_pnl', 'REAL'),
    ('pnl_usdt', 'REAL'),
    ('close_reason', 'TEXT')
]

# Получаем текущую структуру
cursor.execute("PRAGMA table_info(signals)")
existing_columns = [col[1] for col in cursor.fetchall()]

print('📋 Текущие колонки:', existing_columns)
print()

# Добавляем недостающие колонки
for col_name, col_type in columns_to_add:
    if col_name not in existing_columns:
        try:
            cursor.execute(f'ALTER TABLE signals ADD COLUMN {col_name} {col_type}')
            print(f'✅ Добавлена колонка: {col_name} ({col_type})')
        except Exception as e:
            print(f'❌ Ошибка при добавлении {col_name}: {e}')
    else:
        print(f'ℹ️ Колонка {col_name} уже существует')

conn.commit()
conn.close()

print()
print('✅ Миграция завершена!')
