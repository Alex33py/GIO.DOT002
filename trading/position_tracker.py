# -*- coding: utf-8 -*-
"""
Модуль автоматического отслеживания достижения TP/SL
Проверяет активные сигналы и автоматически фиксирует результаты
"""

import asyncio
from typing import Dict, List
from datetime import datetime

from config.settings import logger
from trading.signal_recorder import SignalRecorder
from utils.helpers import safe_float


class PositionTracker:
    """Отслеживание активных позиций и автофиксация результатов"""

    def __init__(self, signal_recorder: SignalRecorder):
        """
        Инициализация tracker

        Параметры:
            signal_recorder: Экземпляр SignalRecorder для записи fills
        """
        self.recorder = signal_recorder
        self.tracked_positions = {}  # {signal_id: position_data}

        logger.info("✅ PositionTracker инициализирован")

    async def update_positions(self, current_prices: Dict[str, float]):
        """
        Обновление всех активных позиций

        Параметры:
            current_prices: Словарь {symbol: current_price}
        """
        try:
            # Получаем активные сигналы
            active_signals = self.recorder.get_active_signals()

            if not active_signals:
                return

            logger.debug(f"🔄 Проверка {len(active_signals)} активных сигналов")

            for signal in active_signals:
                try:
                    symbol = signal['symbol']
                    current_price = current_prices.get(symbol)

                    if not current_price:
                        continue

                    # Обновляем текущую цену
                    self.recorder.update_signal_price(signal['id'], current_price)

                    # Проверяем достижение уровней
                    await self._check_levels(signal, current_price)

                except Exception as e:
                    logger.warning(f"⚠️ Ошибка обработки сигнала #{signal['id']}: {e}")
                    continue

        except Exception as e:
            logger.error(f"❌ Ошибка update_positions: {e}")

    async def _check_levels(self, signal: Dict, current_price: float):
        """
        Проверка достижения TP/SL уровней

        Параметры:
            signal: Данные сигнала из БД
            current_price: Текущая цена
        """
        try:
            signal_id = signal['id']
            side = signal['side']
            entry_price = safe_float(signal['price_entry'])

            # Уровни
            sl = safe_float(signal['stop_loss'])
            tp1 = safe_float(signal['take_profit_1'])
            tp2 = safe_float(signal['take_profit_2'])
            tp3 = safe_float(signal['take_profit_3'])

            # Флаги уже достигнутых уровней
            tp1_hit = signal['tp1_hit'] == 1
            tp2_hit = signal['tp2_hit'] == 1
            tp3_hit = signal['tp3_hit'] == 1
            sl_hit = signal['sl_hit'] == 1

            if side == "LONG":
                # Проверка SL (приоритет)
                if current_price <= sl and not sl_hit:
                    pnl = ((current_price - entry_price) / entry_price) * 100
                    self.recorder.record_fill(signal_id, "SL", current_price, 100.0, pnl)
                    logger.warning(f"🛑 SL достигнут: Сигнал #{signal_id} @ {current_price} (P&L: {pnl:+.2f}%)")
                    return  # Позиция закрыта

                # Проверка TP1 (25% позиции)
                if current_price >= tp1 and not tp1_hit:
                    pnl = ((tp1 - entry_price) / entry_price) * 100 * 0.25
                    self.recorder.record_fill(signal_id, "TP1", tp1, 25.0, pnl)
                    logger.info(f"🎯 TP1 достигнут: Сигнал #{signal_id} @ {tp1} (P&L: {pnl:+.2f}%)")

                # Проверка TP2 (50% позиции)
                if current_price >= tp2 and not tp2_hit and tp1_hit:
                    pnl = ((tp2 - entry_price) / entry_price) * 100 * 0.50
                    self.recorder.record_fill(signal_id, "TP2", tp2, 50.0, pnl)
                    logger.info(f"🎯 TP2 достигнут: Сигнал #{signal_id} @ {tp2} (P&L: {pnl:+.2f}%)")

                # Проверка TP3 (25% позиции)
                if current_price >= tp3 and not tp3_hit and tp2_hit:
                    pnl = ((tp3 - entry_price) / entry_price) * 100 * 0.25
                    self.recorder.record_fill(signal_id, "TP3", tp3, 25.0, pnl)
                    logger.info(f"🎯 TP3 достигнут: Сигнал #{signal_id} @ {tp3} (P&L: {pnl:+.2f}%)")

            else:  # SHORT
                # Проверка SL
                if current_price >= sl and not sl_hit:
                    pnl = ((entry_price - current_price) / entry_price) * 100
                    self.recorder.record_fill(signal_id, "SL", current_price, 100.0, pnl)
                    logger.warning(f"🛑 SL достигнут: Сигнал #{signal_id} @ {current_price} (P&L: {pnl:+.2f}%)")
                    return

                # TP1
                if current_price <= tp1 and not tp1_hit:
                    pnl = ((entry_price - tp1) / entry_price) * 100 * 0.25
                    self.recorder.record_fill(signal_id, "TP1", tp1, 25.0, pnl)
                    logger.info(f"🎯 TP1 достигнут: Сигнал #{signal_id} @ {tp1} (P&L: {pnl:+.2f}%)")

                # TP2
                if current_price <= tp2 and not tp2_hit and tp1_hit:
                    pnl = ((entry_price - tp2) / entry_price) * 100 * 0.50
                    self.recorder.record_fill(signal_id, "TP2", tp2, 50.0, pnl)
                    logger.info(f"🎯 TP2 достигнут: Сигнал #{signal_id} @ {tp2} (P&L: {pnl:+.2f}%)")

                # TP3
                if current_price <= tp3 and not tp3_hit and tp2_hit:
                    pnl = ((entry_price - tp3) / entry_price) * 100 * 0.25
                    self.recorder.record_fill(signal_id, "TP3", tp3, 25.0, pnl)
                    logger.info(f"🎯 TP3 достигнут: Сигнал #{signal_id} @ {tp3} (P&L: {pnl:+.2f}%)")

        except Exception as e:
            logger.error(f"❌ Ошибка проверки уровней: {e}")

    def get_position_summary(self) -> Dict:
        """
        Получение сводки по активным позициям

        Возвращает:
            Словарь с количеством и статистикой позиций
        """
        try:
            active_signals = self.recorder.get_active_signals()

            summary = {
                "total_active": len(active_signals),
                "long_count": sum(1 for s in active_signals if s['side'] == 'LONG'),
                "short_count": sum(1 for s in active_signals if s['side'] == 'SHORT'),
                "total_unrealized_pnl": 0.0,
                "positions": []
            }

            for signal in active_signals:
                current_price = signal.get('price_current', signal['price_entry'])
                entry_price = signal['price_entry']

                if signal['side'] == 'LONG':
                    unrealized_pnl = ((current_price - entry_price) / entry_price) * 100
                else:
                    unrealized_pnl = ((entry_price - current_price) / entry_price) * 100

                summary["total_unrealized_pnl"] += unrealized_pnl

                summary["positions"].append({
                    "id": signal['id'],
                    "symbol": signal['symbol'],
                    "side": signal['side'],
                    "entry": entry_price,
                    "current": current_price,
                    "unrealized_pnl": round(unrealized_pnl, 2)
                })

            return summary

        except Exception as e:
            logger.error(f"❌ Ошибка получения position summary: {e}")
            return {"total_active": 0}


# Экспорт
__all__ = ['PositionTracker']
