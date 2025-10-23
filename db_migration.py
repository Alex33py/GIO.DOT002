#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Database Migration Tool
Автоматическое добавление колонки close_time в таблицу signals
"""

import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def migrate_database():
    """
    Выполняет миграцию базы данных: добавляет колонку close_time если её нет
    """
    # Ищем файл базы данных (ОБНОВЛЁННЫЕ ПУТИ!)
    possible_db_paths = [
        "gio_crypto_bot.db",  # ✅ Корень
        "data/gio_bot.db",  # ✅ Папка data
        "data/gio_crypto.db",  # ✅ На случай если есть ещё одна БД
        "signals.db",  # Резервный вариант
        "gio_signals.db",  # Резервный вариант
    ]

    db_path = None
    for path in possible_db_paths:
        if Path(path).exists():
            db_path = path
            logger.info(f"📂 Найдена база данных: {path}")
            break

    if not db_path:
        logger.warning("⚠️ База данных не найдена! Пропускаем миграцию.")
        return False

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Проверяем существует ли колонка close_time
        cursor.execute("PRAGMA table_info(signals)")
        columns = [col[1] for col in cursor.fetchall()]

        if "close_time" not in columns:
            logger.info("🔧 Начинаем миграцию: добавление колонки close_time...")

            # Добавляем колонку
            cursor.execute(
                """
                ALTER TABLE signals
                ADD COLUMN close_time TEXT
            """
            )

            conn.commit()
            logger.info("✅ Миграция завершена! Колонка 'close_time' добавлена.")

            # Показываем текущую структуру
            cursor.execute("PRAGMA table_info(signals)")
            columns_info = cursor.fetchall()
            logger.info(
                f"📋 Текущие колонки в таблице 'signals': {', '.join([col[1] for col in columns_info])}"
            )

            return True
        else:
            logger.info(
                "✅ Колонка 'close_time' уже существует. Миграция не требуется."
            )
            return True

    except sqlite3.OperationalError as e:
        logger.error(f"❌ Ошибка миграции: {e}")
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    # Настройка логирования для теста
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    migrate_database()
