# -*- coding: utf-8 -*-
"""
Батчинг логов - объединяет повторяющиеся сообщения
"""

import asyncio
from collections import defaultdict, Counter
from datetime import datetime
from typing import Dict, List
from config.settings import logger


class LogBatcher:
    """Агрегирует логи и выводит сводки"""

    def __init__(self, flush_interval: int = 30):
        """
        Args:
            flush_interval: Интервал вывода сводок (секунды)
        """
        self.flush_interval = flush_interval
        self.orderbook_updates: Counter = Counter()
        self.volume_calculations: Counter = Counter()
        self.scenario_matches: List[Dict] = []
        self.last_flush = datetime.now()
        self.is_running = False

    async def start(self):
        """Запуск батчера"""
        self.is_running = True
        asyncio.create_task(self._flush_loop())
        logger.info(f"✅ LogBatcher запущен (сводки каждые {self.flush_interval}s)")

    async def stop(self):
        """Остановка батчера"""
        self.is_running = False
        await self._flush()  # Финальный flush
        logger.info("🛑 LogBatcher остановлен")

    def log_orderbook_update(self, exchange: str, symbol: str):
        """Записать обновление orderbook"""
        key = f"{exchange}:{symbol}"
        self.orderbook_updates[key] += 1

    def log_volume_calculation(self, symbol: str):
        """Записать расчет volume profile"""
        self.volume_calculations[symbol] += 1

    def log_scenario_match(self, symbol: str, score: float, scenario: str):
        """Записать совпадение сценария"""
        self.scenario_matches.append({
            'symbol': symbol,
            'score': score,
            'scenario': scenario,
            'time': datetime.now()
        })

    async def _flush_loop(self):
        """Периодический вывод сводок"""
        while self.is_running:
            await asyncio.sleep(self.flush_interval)
            await self._flush()

    async def _flush(self):
        """Вывести сводку"""
        if not any([self.orderbook_updates, self.volume_calculations, self.scenario_matches]):
            return

        logger.info("=" * 70)
        logger.info(f"📊 СВОДКА АКТИВНОСТИ за {self.flush_interval}s")
        logger.info("=" * 70)

        # Orderbook обновления
        if self.orderbook_updates:
            logger.info(f"📈 Orderbook Updates ({sum(self.orderbook_updates.values())} total):")
            for key, count in self.orderbook_updates.most_common(10):
                exchange, symbol = key.split(':')
                logger.info(f"   • {exchange:10} {symbol:10} → {count:4} updates")
            self.orderbook_updates.clear()

        # Volume Profile
        if self.volume_calculations:
            logger.info(f"📊 Volume Profile Calculations ({sum(self.volume_calculations.values())} total):")
            for symbol, count in self.volume_calculations.most_common(5):
                logger.info(f"   • {symbol:10} → {count:4} calculations")
            self.volume_calculations.clear()

        # Scenario Matches
        if self.scenario_matches:
            logger.info(f"🎯 Scenario Matches ({len(self.scenario_matches)} total):")
            # Группируем по символу
            by_symbol = defaultdict(list)
            for match in self.scenario_matches:
                by_symbol[match['symbol']].append(match)

            for symbol, matches in by_symbol.items():
                avg_score = sum(m['score'] for m in matches) / len(matches)
                best_score = max(m['score'] for m in matches)
                logger.info(f"   • {symbol:10} → {len(matches):3} matches | Avg: {avg_score:.1f} | Best: {best_score:.1f}")
            self.scenario_matches.clear()

        logger.info("=" * 70)


# Глобальный экземпляр
log_batcher = LogBatcher(flush_interval=30)
