#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Менеджер для работы с unified_signals
"""

import sqlite3
import os
from datetime import datetime
from typing import Dict, Optional
from config.settings import DATA_DIR, logger  # ✅ ИСПРАВЛЕНО

DB_PATH = os.path.join(DATA_DIR, "gio_bot.db")


def save_signal(signal_data: Dict) -> bool:
    """
    Сохраняет сигнал в unified_signals (из словаря)

    Args:
        signal_data: Словарь с данными сигнала

    Returns:
        bool: True если успешно сохранено
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            INSERT_SQL = """
            INSERT OR REPLACE INTO unified_signals (
                signal_id, symbol, direction, entry_price,
                scenario_id, scenario_score, confidence,
                tp1_price, tp2_price, tp3_price, sl_price,
                status, timestamp, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            cursor.execute(
                INSERT_SQL,
                (
                    signal_data.get("signal_id"),
                    signal_data.get("symbol"),
                    signal_data.get("direction"),
                    signal_data.get("entry_price"),
                    signal_data.get("scenario_id"),
                    signal_data.get("scenario_score"),
                    signal_data.get("confidence"),
                    signal_data.get("tp1_price"),
                    signal_data.get("tp2_price"),
                    signal_data.get("tp3_price"),
                    signal_data.get("sl_price"),
                    signal_data.get("status", "ACTIVE"),
                    datetime.now().isoformat(),
                    datetime.now().isoformat(),
                ),
            )

            conn.commit()
            logger.info(f"✅ Signal saved: {signal_data['signal_id']}")
            return True

    except Exception as e:
        logger.error(f"❌ Error saving signal: {e}")
        return False


def save_signal_to_unified(signal) -> bool:
    """
    Сохраняет EnhancedTradingSignal в unified_signals

    Args:
        signal: Объект EnhancedTradingSignal

    Returns:
        bool: True если успешно сохранено
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Генерируем signal_id
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            scenario_id_short = signal.scenario_id[:8] if len(signal.scenario_id) > 8 else signal.scenario_id
            signal_id = f"{signal.symbol}_{signal.side}_{timestamp}_{scenario_id_short}"

            # Конвертируем SELL → SHORT, BUY → LONG
            direction = "LONG" if signal.side == "BUY" else "SHORT"

            INSERT_SQL = """
            INSERT OR REPLACE INTO unified_signals (
                signal_id, symbol, direction, entry_price,
                scenario_id, scenario_score, confidence,
                tp1_price, tp2_price, tp3_price, sl_price,
                status, timestamp, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """

            cursor.execute(INSERT_SQL, (
                signal_id,
                signal.symbol,
                direction,
                signal.price_entry,
                signal.scenario_id,
                signal.confidence_score * 100,  # Конвертируем 0-1 → 0-100
                signal.confidence_score * 100,
                signal.tp1,
                signal.tp2,
                signal.tp3,
                signal.sl,
                "ACTIVE",
                datetime.now().isoformat(),
                datetime.now().isoformat()
            ))

            conn.commit()
            logger.info(f"✅ Signal saved to unified_signals: {signal_id}")
            return True

    except Exception as e:
        logger.error(f"❌ Error saving signal to unified_signals: {e}")
        return False


def update_signal_roi(signal_id: str, current_price: float) -> Optional[Dict]:
    """
    Обновляет ROI и статус сигнала

    Args:
        signal_id: ID сигнала
        current_price: Текущая цена

    Returns:
        Dict с обновлёнными данными или None
    """
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()

            # Получаем данные сигнала
            cursor.execute(
                """
                SELECT symbol, direction, entry_price,
                       tp1_price, tp2_price, tp3_price, sl_price,
                       tp1_hit, tp2_hit, tp3_hit, sl_hit
                FROM unified_signals
                WHERE signal_id = ? AND status = 'ACTIVE'
            """,
                (signal_id,),
            )

            row = cursor.fetchone()
            if not row:
                return None

            (
                symbol,
                direction,
                entry,
                tp1,
                tp2,
                tp3,
                sl,
                tp1_hit,
                tp2_hit,
                tp3_hit,
                sl_hit,
            ) = row

            # Рассчитай ROI
            if direction == "LONG":
                roi = ((current_price - entry) / entry) * 100
            else:  # SHORT
                roi = ((entry - current_price) / entry) * 100

            # Проверь TP/SL
            updates = {"current_roi": roi}

            if direction == "LONG":
                if current_price >= tp1 and not tp1_hit:
                    updates["tp1_hit"] = 1
                if current_price >= tp2 and not tp2_hit:
                    updates["tp2_hit"] = 1
                if current_price >= tp3 and not tp3_hit:
                    updates["tp3_hit"] = 1
                    updates["status"] = "CLOSED"
                if current_price <= sl and not sl_hit:
                    updates["sl_hit"] = 1
                    updates["status"] = "CLOSED"
            else:  # SHORT
                if current_price <= tp1 and not tp1_hit:
                    updates["tp1_hit"] = 1
                if current_price <= tp2 and not tp2_hit:
                    updates["tp2_hit"] = 1
                if current_price <= tp3 and not tp3_hit:
                    updates["tp3_hit"] = 1
                    updates["status"] = "CLOSED"
                if current_price >= sl and not sl_hit:
                    updates["sl_hit"] = 1
                    updates["status"] = "CLOSED"

            # Обнови БД
            update_fields = ", ".join([f"{k} = ?" for k in updates.keys()])
            update_values = list(updates.values()) + [
                datetime.now().isoformat(),
                signal_id,
            ]

            cursor.execute(
                f"""
                UPDATE unified_signals
                SET {update_fields}, updated_at = ?
                WHERE signal_id = ?
            """,
                update_values,
            )

            conn.commit()

            logger.debug(f"✅ Signal updated: {signal_id} | ROI: {roi:.2f}%")
            return updates

    except Exception as e:
        logger.error(f"❌ Error updating signal: {e}")
        return None


def get_active_signals():
    """Получает все активные сигналы"""
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT * FROM unified_signals
                WHERE status = 'ACTIVE'
                ORDER BY scenario_score DESC
            """
            )

            return [dict(row) for row in cursor.fetchall()]

    except Exception as e:
        logger.error(f"❌ Error fetching active signals: {e}")
        return []
