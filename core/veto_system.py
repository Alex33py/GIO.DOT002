# -*- coding: utf-8 -*-
from typing import Dict
from config.settings import logger

class EnhancedVetoSystem:
    def __init__(self):
        self.veto_rules = []
        logger.info("✅ EnhancedVetoSystem инициализирована")

    async def check_all_conditions(self, symbol: str, market_data: Dict, indicators: Dict) -> Dict:
        veto_checks = {
            'has_veto': False,
            'veto_reasons': [],
            'warnings': []
        }

        # Проверка волатильности
        atr = indicators.get('atr_1h', 0)
        if atr > 1000:
            veto_checks['warnings'].append('Высокая волатильность')

        # Проверка RSI
        rsi = indicators.get('rsi_1h', 50)
        if rsi > 80:
            veto_checks['warnings'].append('RSI перекуплен')
        elif rsi < 20:
            veto_checks['warnings'].append('RSI перепродан')

        logger.debug(f"🛡️ Veto проверки для {symbol}: {len(veto_checks['warnings'])} предупреждений")
        return veto_checks
