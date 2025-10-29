import sqlite3
import os

# Путь к базе данных
DB_PATH = "data/gio_crypto_bot.db"

def create_signals_table():
    """Создает таблицу signals в базе данных"""
    try:
        # Проверяем существование директории
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

        # Подключаемся к БД
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        print(f"📊 Подключение к БД: {DB_PATH}")

        # СНАЧАЛА создаем таблицу
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS signals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL,
                signal_type TEXT NOT NULL,
                direction TEXT,
                confidence REAL,
                price REAL,
                entry_price REAL,
                stop_loss REAL,
                take_profit REAL,
                status TEXT DEFAULT 'active',
                scenario_id TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                closed_at DATETIME,
                profit_loss REAL,
                roi_percent REAL,
                notes TEXT
            )
        """)
        print("✅ Таблица 'signals' создана")

        # Сохраняем изменения
        conn.commit()

        # ПОТОМ создаем индексы (каждый отдельной командой)
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_symbol ON signals(symbol)")
            print("✅ Индекс idx_signals_symbol создан")
        except Exception as e:
            print(f"⚠️ Индекс idx_signals_symbol: {e}")

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status)")
            print("✅ Индекс idx_signals_status создан")
        except Exception as e:
            print(f"⚠️ Индекс idx_signals_status: {e}")

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_timestamp ON signals(timestamp)")
            print("✅ Индекс idx_signals_timestamp создан")
        except Exception as e:
            print(f"⚠️ Индекс idx_signals_timestamp: {e}")

        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_signals_type ON signals(signal_type)")
            print("✅ Индекс idx_signals_type создан")
        except Exception as e:
            print(f"⚠️ Индекс idx_signals_type: {e}")

        # Сохраняем изменения
        conn.commit()

        # Проверяем таблицу
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='signals'")
        if cursor.fetchone():
            print("\n✅ Таблица 'signals' успешно создана и доступна")

            # Показываем структуру
            cursor.execute("PRAGMA table_info(signals)")
            columns = cursor.fetchall()
            print("\n📋 Структура таблицы 'signals':")
            for col in columns:
                print(f"   - {col[1]} ({col[2]})")

            # Показываем количество записей
            cursor.execute("SELECT COUNT(*) FROM signals")
            count = cursor.fetchone()[0]
            print(f"\n📊 Записей в таблице: {count}")
        else:
            print("❌ Ошибка: таблица не найдена после создания")

        conn.close()
        print("\n✅ Готово! Таблица signals успешно создана.")
        print("\n💡 Теперь можете перезапустить бота:")
        print("   python main.py")

    except Exception as e:
        print(f"❌ Ошибка при создании таблицы: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    create_signals_table()
