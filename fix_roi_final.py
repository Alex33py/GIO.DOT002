# fix_roi_final.py
from pathlib import Path

ROI_TRACKER_PATH = Path("D:/GIO.BOT.02/telegram_bot/roi_tracker.py")


def fix_roi_final():
    """Финальное исправление _update_signal_in_db"""

    with open(ROI_TRACKER_PATH, "r", encoding="utf-8") as f:
        content = f.read()

    # Находим функцию _update_signal_in_db и заменяем её ПОЛНОСТЬЮ
    old_function = '''    async def _update_signal_in_db(self, metrics: ROIMetrics, final: bool = False):
        """Обновление сигнала в БД"""
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                if final:
                    await db.execute(
                        """
                        UPDATE signals
                        SET status = ?, roi = ?, close_time = ?
                        WHERE id = (SELECT id FROM signals WHERE symbol = ? AND timestamp = ? LIMIT 1)


                    """,
                        (
                            metrics.status,
                            metrics.current_roi,
                            metrics.close_time,
                            metrics.signal_id,
                        ),
                    )
                else:
                    await db.execute(
                        """
                        UPDATE signals
                        SET roi = ?, tp1_hit = ?, tp2_hit = ?, tp3_hit = ?, sl_hit = ?
                        WHERE signal_id = ?
                    """,
                        (
                            metrics.current_roi,
                            metrics.tp1_hit,
                            metrics.tp2_hit,
                            metrics.tp3_hit,
                            metrics.sl_hit,
                            metrics.signal_id,
                        ),
                    )
                await db.commit()
        except Exception as e:
            logger.error(f"❌ Ошибка обновления сигнала в БД: {e}")'''

    new_function = '''    async def _update_signal_in_db(self, metrics: ROIMetrics, final: bool = False):
        """Обновление сигнала в БД"""
        try:
            async with aiosqlite.connect(DATABASE_PATH) as db:
                if final:
                    await db.execute(
                        """
                        UPDATE signals
                        SET status = ?, roi = ?, close_time = ?
                        WHERE symbol = ? AND timestamp = ?
                    """,
                        (
                            metrics.status,
                            metrics.current_roi,
                            metrics.close_time,
                            metrics.symbol,
                            metrics.entry_time,
                        ),
                    )
                else:
                    await db.execute(
                        """
                        UPDATE signals
                        SET roi = ?, tp1_hit = ?, tp2_hit = ?, tp3_hit = ?, sl_hit = ?
                        WHERE symbol = ? AND timestamp = ?
                    """,
                        (
                            metrics.current_roi,
                            metrics.tp1_hit,
                            metrics.tp2_hit,
                            metrics.tp3_hit,
                            metrics.sl_hit,
                            metrics.symbol,
                            metrics.entry_time,
                        ),
                    )
                await db.commit()
        except Exception as e:
            logger.error(f"❌ Ошибка обновления сигнала в БД: {e}")'''

    content = content.replace(old_function, new_function)

    with open(ROI_TRACKER_PATH, "w", encoding="utf-8") as f:
        f.write(content)

    print("✅ Файл roi_tracker.py окончательно исправлен!")
    print("✅ WHERE signal_id = ? → WHERE symbol = ? AND timestamp = ?")
    print("✅ Параметры обновлены: metrics.symbol, metrics.entry_time")


if __name__ == "__main__":
    fix_roi_final()
