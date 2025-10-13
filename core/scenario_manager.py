# -*- coding: utf-8 -*-
import json
import aiosqlite
from pathlib import Path
from typing import List, Dict, Optional
from config.settings import logger, SCENARIOS_DIR

class ScenarioManager:
    def __init__(self, db_path: str = None):
        self.db_path = db_path
        self.scenarios = []
        logger.info("✅ ScenarioManager инициализирован")
    
    async def load_scenarios_from_json(self, filename: str = "gio_scenarios_100_with_features_v3.json"):
        try:
            json_path = Path(SCENARIOS_DIR) / filename
            if not json_path.exists():
                logger.warning(f"⚠️ Файл сценариев не найден: {json_path}")
                return False
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                self.scenarios = data
            elif isinstance(data, dict) and 'scenarios' in data:
                self.scenarios = data['scenarios']
            else:
                logger.error("❌ Неверный формат JSON сценариев")
                return False
            logger.info(f"✅ Загружено {len(self.scenarios)} сценариев")
            return True
        except Exception as e:
            logger.error(f"❌ Ошибка загрузки сценариев: {e}")
            return False
    
    def get_all_scenarios(self) -> List[Dict]:
        return self.scenarios
    
    def get_scenario_by_id(self, scenario_id: int) -> Optional[Dict]:
        for scenario in self.scenarios:
            if scenario.get('id') == scenario_id:
                return scenario
        return None
