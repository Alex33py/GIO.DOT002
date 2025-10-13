# -*- coding: utf-8 -*-
"""
Менеджер торговых сценариев для GIO Crypto Bot
Управление загрузкой, валидацией и хранением торговых сценариев
"""

import hashlib
import asyncio
import aiosqlite
import json
from typing import Dict, List, Optional, Any
from pathlib import Path

from config.settings import logger, DB_FILE, SCENARIOS_DIR
from config.constants import EnhancedTradingSignal, SignalStatusEnum
from utils.helpers import current_epoch_ms, save_json_file, load_json_file
from utils.validators import validate_scenario_data, validate_json_data


class ScenarioManager:
    """Менеджер торговых сценариев с поддержкой JSON и базы данных"""

    def __init__(self):
        """Инициализация менеджера сценариев"""
        self.scenarios_cache: Dict[str, Dict] = {}
        self.scenarios_metadata: Dict[str, Dict] = {}

        # Статистика сценариев
        self.scenario_stats = {
            "total_scenarios": 0,
            "active_scenarios": 0,
            "successful_scenarios": 0,
            "scenario_usage": {},
            "last_load_time": 0,
        }

        # Настройки
        self.manager_settings = {
            "auto_reload": True,
            "cache_timeout_ms": 3600000,  # 1 час
            "validate_on_load": True,
            "backup_on_change": True,
        }

        logger.info("✅ ScenarioManager инициализирован")

    async def initialize_database(self):
        """Инициализация таблиц базы данных"""
        try:
            async with aiosqlite.connect(DB_FILE) as db:
                # Таблица сценариев
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS trading_scenarios (
                        scenario_id TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        signal_type TEXT NOT NULL,
                        conditions TEXT NOT NULL,
                        risk_management TEXT,
                        metadata TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        success_rate REAL DEFAULT 0.0,
                        usage_count INTEGER DEFAULT 0,
                        created_timestamp INTEGER NOT NULL,
                        updated_timestamp INTEGER NOT NULL,
                        file_hash TEXT
                    )
                """)

                # Таблица сигналов
                await db.execute("""
                    CREATE TABLE IF NOT EXISTS trading_signals (
                        signal_id TEXT PRIMARY KEY,
                        symbol TEXT NOT NULL,
                        side TEXT NOT NULL,
                        scenario_id TEXT NOT NULL,
                        status TEXT NOT NULL,
                        price_entry REAL NOT NULL,
                        sl REAL NOT NULL,
                        tp1 REAL NOT NULL,
                        tp2 REAL,
                        tp3 REAL,
                        rr1 REAL NOT NULL,
                        rr2 REAL,
                        rr3 REAL,
                        confidence_score REAL NOT NULL,
                        reason TEXT,
                        indicators TEXT,
                        market_conditions TEXT,
                        news_impact TEXT,
                        timestamp INTEGER NOT NULL,
                        FOREIGN KEY (scenario_id) REFERENCES trading_scenarios (scenario_id)
                    )
                """)

                # Индексы для производительности
                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_signals_symbol_timestamp
                    ON trading_signals (symbol, timestamp)
                """)

                await db.execute("""
                    CREATE INDEX IF NOT EXISTS idx_signals_scenario_id
                    ON trading_signals (scenario_id)
                """)

                await db.commit()
                logger.info("✅ Таблицы базы данных инициализированы")

            await self.migrate_scenarios_table()
        except Exception as e:
            logger.error(f"❌ Ошибка инициализации БД: {e}")
            raise

    async def migrate_scenarios_table(self):
            """Миграция старой таблицы scenarios на новую структуру"""
            try:
                async with aiosqlite.connect(DB_FILE) as db:
                    # Проверяем существование колонки scenario_data
                    async with db.execute("PRAGMA table_info(scenarios)") as cursor:
                        columns = await cursor.fetchall()
                        column_names = [col[1] for col in columns]

                    if "scenario_data" not in column_names:
                        logger.info("🔧 Миграция таблицы scenarios...")

                        # Переименовываем старую таблицу
                        await db.execute("ALTER TABLE scenarios RENAME TO scenarios_old")

                        # Создаём новую таблицу
                        await db.execute("""
                            CREATE TABLE IF NOT EXISTS scenarios (
                                scenario_id TEXT PRIMARY KEY,
                                scenario_data TEXT NOT NULL,
                                is_active BOOLEAN DEFAULT 1,
                                created_at INTEGER NOT NULL,
                                updated_at INTEGER NOT NULL
                            )
                        """)

                        # Копируем данные если есть
                        try:
                            await db.execute("""
                                INSERT INTO scenarios (scenario_id, scenario_data, is_active, created_at, updated_at)
                                SELECT scenario_id, '{}', is_active, created_at, updated_at
                                FROM scenarios_old
                            """)
                        except:
                            pass

                        # Удаляем старую таблицу
                        await db.execute("DROP TABLE IF EXISTS scenarios_old")

                        await db.commit()
                        logger.info("✅ Миграция таблицы scenarios завершена")

            except Exception as e:
                logger.error(f"❌ Ошибка миграции: {e}")

    async def load_all_scenarios(self) -> List[Dict[str, Any]]:
        """
        Загрузка всех торговых сценариев
        Сначала пытаемся загрузить из JSON файла, потом из базы данных
        """
        try:
            scenarios = []

            # 1. ПРИОРИТЕТ: Загружаем из JSON файла gio_scenarios_100_with_features_v3.json
            json_file_path = SCENARIOS_DIR / "gio_scenarios_100_with_features_v3.json"

            if json_file_path.exists():
                logger.info(f"📂 Найден файл сценариев: {json_file_path.name}")

                try:
                    with open(json_file_path, 'r', encoding='utf-8') as f:
                        json_data = json.load(f)

                    # Проверяем формат файла
                    if isinstance(json_data, dict):
                        # Формат с метаданными (version, count, scenarios)
                        if "scenarios" in json_data:
                            scenarios_list = json_data["scenarios"]
                            logger.info(f"📊 Загружено {len(scenarios_list)} сценариев из JSON (формат с метаданными)")

                            # Валидируем и добавляем
                            valid_count = 0
                            for idx, scenario in enumerate(scenarios_list):
                                if self._validate_scenario_structure(scenario):
                                    scenarios.append(scenario)
                                    valid_count += 1
                                else:
                                    # Добавим диагностику для первых 3 невалидных
                                    if idx < 3:
                                        logger.warning(
                                            f"⚠️ Сценарий #{idx} не прошёл валидацию: "
                                            f"name={scenario.get('name', 'MISSING')}, "
                                            f"keys={list(scenario.keys())[:5]}"
                                        )

                            logger.info(f"✅ Прошло валидацию: {valid_count}/{len(scenarios_list)} сценариев")

                        # Если это один сценарий в корне
                        elif "name" in json_data and "conditions" in json_data:
                            if self._validate_scenario_structure(json_data):
                                scenarios.append(json_data)
                                logger.info(f"📊 Загружен 1 сценарий из JSON")

                    elif isinstance(json_data, list):
                        # Формат массива сценариев
                        scenarios_list = json_data
                        logger.info(f"📊 Загружено {len(scenarios_list)} сценариев из JSON (формат массива)")

                        if scenarios_list:
                            first_scenario = scenarios_list[0]
                            logger.info(f"📋 Пример первого сценария:")
                            logger.info(f"   name={first_scenario.get('name', 'MISSING')}")
                            logger.info(f"   keys={list(first_scenario.keys())[:10]}")

                        valid_count = 0
                        for idx, scenario in enumerate(scenarios_list):
                            if self._validate_scenario_structure(scenario):
                                scenarios.append(scenario)
                                valid_count += 1
                            else:
                                if idx < 3:
                                    logger.warning(
                                        f"⚠️ Сценарий #{idx} не прошёл валидацию: "
                                        f"name={scenario.get('name', 'MISSING')}, "
                                        f"keys={list(scenario.keys())[:5]}"
                                    )

                        logger.info(f"✅ Прошло валидацию: {valid_count}/{len(scenarios_list)} сценариев")

                    logger.info(f"✅ Успешно загружено {len(scenarios)} валидных сценариев из JSON")

                    # Сохраняем в базу данных для кэширования
                    if scenarios:
                        logger.info("💾 Сохраняем сценарии в базу данных...")
                        saved_count = 0
                        for scenario in scenarios:
                            if await self._save_scenario_to_db(scenario):
                                saved_count += 1
                        logger.info(f"✅ {saved_count} сценариев сохранены в БД")

                    return scenarios

                except json.JSONDecodeError as e:
                    logger.error(f"❌ Ошибка парсинга JSON: {e}")
                except Exception as e:
                    logger.error(f"❌ Ошибка загрузки JSON файла: {e}")

            # 2. FALLBACK: Загружаем из базы данных
            logger.info("📂 JSON файл не найден, загружаем сценарии из базы данных...")

            async with aiosqlite.connect(DB_FILE) as db:
                async with db.execute("""
                    SELECT scenario_data FROM scenarios
                    WHERE is_active = 1
                    ORDER BY created_at DESC
                """) as cursor:
                    rows = await cursor.fetchall()

                    for row in rows:
                        try:
                            scenario = json.loads(row[0])
                            if self._validate_scenario_structure(scenario):
                                scenarios.append(scenario)
                        except json.JSONDecodeError:
                            continue

            if not scenarios:
                logger.warning("⚠️ Не найдено торговых сценариев")
                return []

            logger.info(f"✅ Загружено {len(scenarios)} торговых сценариев из БД")
            return scenarios

        except Exception as e:
            logger.error(f"❌ Ошибка загрузки сценариев: {e}")
            return []

    def _validate_scenario_structure(self, scenario: Dict[str, Any]) -> bool:
        """
        Улучшенная валидация структуры сценария
        Поддерживает формат из gio_scenarios_100_with_features_v3.json
        """
        try:
            # Получаем имя сценария
            scenario_name = scenario.get("name", "")

            # Если name пустое, ищем другие идентификаторы
            if not scenario_name:
                scenario_name = scenario.get("scenario_name", "")

            if not scenario_name:
                scenario_name = scenario.get("id", "")

            # Если всё ещё нет имени - генерируем
            if not scenario_name:
                # Попробуем извлечь из описания или других полей
                if "description" in scenario:
                    # Генерируем имя из первых слов описания
                    desc_words = scenario["description"].split()[:3]
                    scenario_name = "_".join(desc_words).lower()
                else:
                    # Последняя попытка - используем хеш
                    scenario_json = json.dumps(scenario, sort_keys=True)
                    scenario_name = f"scenario_{hashlib.md5(scenario_json.encode()).hexdigest()[:8]}"

            # Обновляем name в сценарии
            scenario["name"] = scenario_name

            # Проверяем что это не служебное поле
            invalid_names = [
                "version", "count", "meta", "params_default", "params_overrides",
                "mtf_policy", "news_policy", "decision_policy", "tactics_policy",
                "sizing_policy", "scenarios", "trigger_policy_percent"
            ]

            if scenario_name.lower() in invalid_names:
                logger.debug(f"Пропущено служебное поле: {scenario_name}")
                return False

            # Проверяем что есть условия или другие обязательные поля
            has_required_fields = any([
                "conditions" in scenario,
                "entry_conditions" in scenario,
                "indicators" in scenario,
                "features" in scenario,
                "rules" in scenario
            ])

            if not has_required_fields:
                logger.debug(f"Сценарий {scenario_name} не имеет обязательных полей")
                return False

            logger.debug(f"✅ Сценарий {scenario_name} прошёл валидацию")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка валидации сценария: {e}")
            return False

    async def _save_scenario_to_db(self, scenario: Dict[str, Any]) -> bool:
        """Сохранение сценария в базу данных"""
        try:
            scenario_id = scenario.get("name", "").lower().replace(" ", "_")

            if not scenario_id:
                logger.warning("⚠️ Сценарий без имени, пропускаем")
                return False

            async with aiosqlite.connect(DB_FILE) as db:
                # Проверяем существование
                async with db.execute(
                    "SELECT scenario_id FROM scenarios WHERE scenario_id = ?",
                    (scenario_id,)
                ) as cursor:
                    existing = await cursor.fetchone()

                scenario_json = json.dumps(scenario, ensure_ascii=False)
                current_time = current_epoch_ms()

                if existing:
                    # Обновляем существующий
                    await db.execute("""
                        UPDATE scenarios
                        SET scenario_data = ?, updated_at = ?
                        WHERE scenario_id = ?
                    """, (scenario_json, current_time, scenario_id))
                else:
                    # Создаём новый
                    await db.execute("""
                        INSERT INTO scenarios
                        (scenario_id, scenario_data, is_active, created_at, updated_at)
                        VALUES (?, ?, 1, ?, ?)
                    """, (scenario_id, scenario_json, current_time, current_time))

                await db.commit()
                logger.debug(f"💾 Сценарий {scenario_id} сохранён в БД")
                return True

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения сценария в БД: {e}")
            return False

    async def save_signal_to_database(self, signal: EnhancedTradingSignal) -> bool:
        """Сохранение торгового сигнала в базу данных"""
        try:
            signal_id = f"{signal.symbol}_{signal.scenario_id}_{signal.timestamp}"

            async with aiosqlite.connect(DB_FILE) as db:
                await db.execute("""
                    INSERT OR REPLACE INTO trading_signals (
                        signal_id, symbol, side, scenario_id, status, price_entry,
                        sl, tp1, tp2, tp3, rr1, rr2, rr3, confidence_score,
                        reason, indicators, market_conditions, news_impact, timestamp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    signal_id,
                    signal.symbol,
                    signal.side,
                    signal.scenario_id,
                    signal.status.value,
                    signal.price_entry,
                    signal.sl,
                    signal.tp1,
                    signal.tp2,
                    signal.tp3,
                    signal.rr1,
                    signal.rr2,
                    signal.rr3,
                    signal.confidence_score,
                    signal.reason,
                    json.dumps(signal.indicators),
                    json.dumps(signal.market_conditions),
                    json.dumps(signal.news_impact),
                    signal.timestamp
                ))

                await db.commit()

            # Обновляем статистику использования сценария
            await self._update_scenario_usage(signal.scenario_id)

            logger.debug(f"💾 Сигнал сохранён в БД: {signal_id}")
            return True

        except Exception as e:
            logger.error(f"❌ Ошибка сохранения сигнала в БД: {e}")
            return False

    async def _update_scenario_usage(self, scenario_id: str):
        """Обновление статистики использования сценария"""
        try:
            async with aiosqlite.connect(DB_FILE) as db:
                await db.execute("""
                    UPDATE trading_scenarios
                    SET usage_count = usage_count + 1, updated_timestamp = ?
                    WHERE scenario_id = ?
                """, (current_epoch_ms(), scenario_id))

                await db.commit()

            # Обновляем локальную статистику
            if scenario_id not in self.scenario_stats["scenario_usage"]:
                self.scenario_stats["scenario_usage"][scenario_id] = 0
            self.scenario_stats["scenario_usage"][scenario_id] += 1

        except Exception as e:
            logger.error(f"❌ Ошибка обновления статистики сценария: {e}")

    def get_scenario(self, scenario_id: str) -> Optional[Dict]:
        """Получение конкретного сценария"""
        try:
            return self.scenarios_cache.get(scenario_id)
        except Exception as e:
            logger.error(f"❌ Ошибка получения сценария {scenario_id}: {e}")
            return None

    def get_scenarios_by_signal_type(self, signal_type: str) -> Dict[str, Dict]:
        """Получение сценариев по типу сигнала"""
        try:
            filtered_scenarios = {}

            for scenario_id, scenario_data in self.scenarios_cache.items():
                if scenario_data.get("signal_type", "").upper() == signal_type.upper():
                    filtered_scenarios[scenario_id] = scenario_data

            return filtered_scenarios

        except Exception as e:
            logger.error(f"❌ Ошибка фильтрации сценариев по типу {signal_type}: {e}")
            return {}


# Экспорт классов
__all__ = [
    'ScenarioManager',
]
