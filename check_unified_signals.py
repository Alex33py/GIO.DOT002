import sqlite3
import os
from config.settings import DATA_DIR

db_path = os.path.join(DATA_DIR, "gio_crypto_bot.db")

print(f"📊 Проверка базы данных: {db_path}\n")

with sqlite3.connect(db_path) as conn:
    cursor = conn.cursor()

    # 1. Проверка существования таблицы
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='unified_signals'"
    )
    table_exists = cursor.fetchone()

    if not table_exists:
        print("❌ Таблица unified_signals НЕ СУЩЕСТВУЕТ!")
        print("\n💡 Нужно создать таблицу. Запусти бота один раз.")
        exit()

    print("✅ Таблица unified_signals существует\n")

    # 2. Проверка структуры таблицы
    cursor.execute("PRAGMA table_info(unified_signals)")
    columns = cursor.fetchall()
    print("📋 Структура таблицы:")
    for col in columns:
        print(f"  - {col[1]} ({col[2]})")

    # 3. Проверка общего количества записей
    cursor.execute("SELECT COUNT(*) FROM unified_signals")
    total_count = cursor.fetchone()[0]
    print(f"\n📈 Всего записей: {total_count}")

    # 4. Проверка ACTIVE записей
    cursor.execute("SELECT COUNT(*) FROM unified_signals WHERE status = 'ACTIVE'")
    active_count = cursor.fetchone()[0]
    print(f"✅ Активных записей: {active_count}")

    # 5. Проверка ACTIVE с условиями
    cursor.execute(
        """
        SELECT COUNT(*) FROM unified_signals
        WHERE status = 'ACTIVE'
            AND scenario_score >= 40
            AND entry_price > 0
    """
    )
    qualified_count = cursor.fetchone()[0]
    print(f"🎯 Подходящих записей (score>=40, entry>0): {qualified_count}")

    # 6. Показать последние 5 записей
    print("\n📊 Последние 5 записей:")
    cursor.execute(
        """
        SELECT id, symbol, direction, entry_price, scenario_id, scenario_score, status
        FROM unified_signals
        ORDER BY timestamp DESC
        LIMIT 5
    """
    )
    rows = cursor.fetchall()

    if rows:
        for row in rows:
            print(f"\n  ID: {row[0]}")
            print(f"  Symbol: {row[1]}")
            print(f"  Direction: {row[2]}")
            print(f"  Entry: ${row[3]:.2f}")
            print(f"  Scenario: {row[4]}")
            print(f"  Score: {row[5]:.1f}%")
            print(f"  Status: {row[6]}")
    else:
        print("  ⚠️ Нет записей")

    # 7. Статистика по статусам
    print("\n📊 Статистика по статусам:")
    cursor.execute("SELECT status, COUNT(*) FROM unified_signals GROUP BY status")
    status_counts = cursor.fetchall()
    for status, count in status_counts:
        print(f"  - {status}: {count}")

print("\n✅ Проверка завершена!")
