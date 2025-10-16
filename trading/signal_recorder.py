#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Signal Recorder - Сохранение и управление торговыми сигналами
"""

import sqlite3
from typing import List, Dict, Optional
from datetime import datetime
from config.settings import logger, DATABASE_PATH


class SignalRecorder:
    """Класс для записи и управления торговыми сигналами"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or DATABASE_PATH
        logger.info(f"✅ SignalRecorder инициализирован (DB: {self.db_path})")

    def record_signal(
        self,
        symbol: str,
        direction: str,
        entry_price: float,
        sl: float,
        tp1: float,
        tp2: float,
        tp3: float,
        scenario_id: str,
        status: str,
        quality_score: float,
        risk_reward: float,
        strategy: str = "unknown",
        market_regime: str = "neutral",
        confidence: str = "medium",
        phase: str = "unknown",
        risk_profile: str = "moderate",
        tactic_name: str = "default",
        validation_score: float = 0.0,
        trigger_score: float = 0.0,
    ) -> int:
        """Сохранение нового сигнала в БД"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO signals (
                    symbol, direction, entry_price,
                    sl, tp1, tp2, tp3,
                    scenario_id, status, quality_score, risk_reward,
                    strategy, market_regime, confidence,
                    phase, risk_profile, tactic_name,
                    validation_score, trigger_score,
                    timestamp
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            """,
                (
                    symbol,
                    direction,
                    entry_price,
                    sl,
                    tp1,
                    tp2,
                    tp3,
                    scenario_id,
                    status,
                    quality_score,
                    risk_reward,
                    strategy,
                    market_regime,
                    confidence,
                    phase,
                    risk_profile,
                    tactic_name,
                    validation_score,
                    trigger_score,
                ),
            )

            signal_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info(
                f"✅ Сигнал #{signal_id} сохранён: {symbol} {direction} ({strategy}/{market_regime})"
            )
            return signal_id

        except Exception as e:
            logger.error(f"❌ Ошибка record_signal: {e}")
            return 0

    # ========== НОВЫЕ МЕТОДЫ (ДОБАВИТЬ ЗДЕСЬ) ==========

    def get_active_signals(self) -> List[Dict]:
        """Получение всех активных сигналов"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    id, symbol, direction, entry_price,
                    sl, tp1, tp2, tp3,
                    scenario_id, status, quality_score, risk_reward,
                    COALESCE(tp1_hit, 0) as tp1_hit,
                    COALESCE(tp2_hit, 0) as tp2_hit,
                    COALESCE(tp3_hit, 0) as tp3_hit,
                    COALESCE(strategy, 'unknown') as strategy,
                    COALESCE(market_regime, 'neutral') as market_regime,
                    COALESCE(confidence, 'medium') as confidence
                FROM signals
                WHERE exit_price IS NULL
                    AND status IN ('active', 'deal', 'risky_entry')
                ORDER BY timestamp DESC
            """
            )

            rows = cursor.fetchall()
            conn.close()

            signals = []
            for row in rows:
                signals.append(
                    {
                        "id": row[0],
                        "symbol": row[1],
                        "direction": row[2],
                        "entry_price": row[3],
                        "sl": row[4],
                        "tp1": row[5],
                        "tp2": row[6],
                        "tp3": row[7],
                        "scenario_id": row[8],
                        "status": row[9],
                        "quality_score": row[10],
                        "risk_reward": row[11],
                        "tp1_hit": row[12],
                        "tp2_hit": row[13],
                        "tp3_hit": row[14],
                        "strategy": row[15],  # ← ДОБАВЛЕНО
                        "market_regime": row[16],  # ← ДОБАВЛЕНО
                        "confidence": row[17],  # ← ДОБАВЛЕНО
                    }
                )

            return signals

        except Exception as e:
            logger.error(f"❌ Ошибка get_active_signals: {e}")
            return []

    def update_signal_tp_reached(
        self, signal_id: int, tp_level: int, realized_roi: float
    ):
        """Обновление сигнала при достижении TP"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Проверяем существуют ли колонки tp1_hit, tp2_hit, tp3_hit
            cursor.execute("PRAGMA table_info(signals)")
            columns = [row[1] for row in cursor.fetchall()]

            tp_column = f"tp{tp_level}_hit"  # ← ИСПРАВЛЕНО!

            if tp_column not in columns:
                # Добавляем колонку если её нет
                cursor.execute(
                    f"ALTER TABLE signals ADD COLUMN {tp_column} INTEGER DEFAULT 0"
                )
                logger.info(f"✅ Добавлена колонка {tp_column}")

            cursor.execute(
                f"""
                UPDATE signals
                SET {tp_column} = 1,
                    realized_roi = ?,
                    updated_at = datetime('now')
                WHERE id = ?
            """,
                (realized_roi, signal_id),
            )

            conn.commit()
            conn.close()

            logger.info(
                f"✅ TP{tp_level} обновлён для сигнала #{signal_id} (ROI: {realized_roi:.2f}%)"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка update_signal_tp_reached: {e}")

    def close_signal(
        self, signal_id: int, exit_price: float, realized_roi: float, status: str
    ):
        """Закрытие сигнала"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE signals
                SET exit_price = ?,
                    profit_percent = ?,
                    status = ?,
                    updated_at = datetime('now')
                WHERE id = ?
            """,
                (exit_price, realized_roi, status, signal_id),
            )

            conn.commit()
            conn.close()

            logger.info(
                f"✅ Сигнал #{signal_id} закрыт ({status}, ROI: {realized_roi:.2f}%)"
            )

        except Exception as e:
            logger.error(f"❌ Ошибка close_signal: {e}")

    def get_signal_by_id(self, signal_id: int) -> Optional[Dict]:
        """Получение сигнала по ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT
                    id, symbol, direction, entry_price,
                    sl, tp1, tp2, tp3, exit_price,
                    profit_percent, scenario_id, status,
                    quality_score, risk_reward, timestamp,
                    COALESCE(strategy, 'unknown') as strategy,
                    COALESCE(market_regime, 'neutral') as market_regime,
                    COALESCE(confidence, 'medium') as confidence,
                    COALESCE(phase, 'unknown') as phase
                FROM signals
                WHERE id = ?
            """,
                (signal_id,),
            )

            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            return {
                "id": row[0],
                "symbol": row[1],
                "direction": row[2],
                "entry_price": row[3],
                "sl": row[4],
                "tp1": row[5],
                "tp2": row[6],
                "tp3": row[7],
                "exit_price": row[8],
                "profit_percent": row[9],
                "scenario_id": row[10],
                "status": row[11],
                "quality_score": row[12],
                "risk_reward": row[13],
                "timestamp": row[14],
                "strategy": row[15],  # ← ДОБАВЛЕНО
                "market_regime": row[16],  # ← ДОБАВЛЕНО
                "confidence": row[17],  # ← ДОБАВЛЕНО
                "phase": row[18],  # ← ДОБАВЛЕНО
            }

        except Exception as e:
            logger.error(f"❌ Ошибка get_signal_by_id: {e}")
            return None

    def get_signal_stats(self, days: int = 30) -> Dict:
        """Получение статистики сигналов"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                f"""
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN profit_percent > 0 THEN 1 ELSE 0 END) as winning,
                    SUM(CASE WHEN profit_percent < 0 THEN 1 ELSE 0 END) as losing,
                    AVG(profit_percent) as avg_profit,
                    MAX(profit_percent) as max_profit,
                    MIN(profit_percent) as max_loss
                FROM signals
                WHERE timestamp > datetime('now', '-{days} days')
                    AND exit_price IS NOT NULL
            """
            )

            row = cursor.fetchone()
            conn.close()

            if not row or row[0] == 0:
                return {
                    "total": 0,
                    "winning": 0,
                    "losing": 0,
                    "win_rate": 0.0,
                    "avg_profit": 0.0,
                    "max_profit": 0.0,
                    "max_loss": 0.0,
                }

            total, winning, losing, avg_profit, max_profit, max_loss = row

            return {
                "total": total,
                "winning": winning,
                "losing": losing,
                "win_rate": (winning / total * 100) if total > 0 else 0.0,
                "avg_profit": avg_profit or 0.0,
                "max_profit": max_profit or 0.0,
                "max_loss": max_loss or 0.0,
            }

        except Exception as e:
            logger.error(f"❌ Ошибка get_signal_stats: {e}")
            return {}


# Экспорт
__all__ = ["SignalRecorder"]
