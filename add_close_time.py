import sqlite3

# Путь к базе данных
DB_PATH = "gio_trading.db"

def add_close_time_column():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        cursor.execute("PRAGMA table_info(signals)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'close_time' not in columns:
            print("⏳ Добавляем колонку close_time...")
            cursor.execute("""
                ALTER TABLE signals 
                ADD COLUMN close_time TEXT DEFAULT NULL
            """)
            conn.commit()
            print("✅ Колонка close_time успешно добавлена!")
        else:
            print("ℹ️ Колонка close_time уже существует")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    add_close_time_column()
