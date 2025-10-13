#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Патч для добавления команды /analyze_batching ALL с использованием UnifiedAutoScanner
"""

from config.settings import logger, TRACKED_SYMBOLS
from telegram import Update
from telegram.ext import ContextTypes


def apply_analyze_batching_all_patch(bot_instance):
    """
    Применить патч для команды /analyze_batching ALL

    Использует UnifiedAutoScanner для полного MTF анализа
    """
    try:
        logger.info("🔧 Патч apply_analyze_batching_all_patch...")

        # ===================================================================
        # МЕТОД СКАНИРОВАНИЯ С ИСПОЛЬЗОВАНИЕМ UnifiedAutoScanner
        # ===================================================================
        async def scan_market(self):
            """
            Сканирование рынка через UnifiedAutoScanner с MTF Alignment
            """
            logger.info(f"🔍 Начало сканирования рынка ({len(TRACKED_SYMBOLS)} символов)")

            try:
                # ✅ Используем UnifiedAutoScanner!
                signal_ids = await self.auto_scanner.scan_multiple_symbols(TRACKED_SYMBOLS)

                if signal_ids:
                    logger.info(f"✅ Сканирование завершено: найдено {len(signal_ids)} сигналов")
                    return signal_ids
                else:
                    logger.info(f"ℹ️ Подходящих сигналов не найдено")
                    return []

            except Exception as e:
                logger.error(f"❌ Ошибка сканирования: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return []

        # Добавляем метод в bot_instance
        import types
        bot_instance.scan_market = types.MethodType(scan_market, bot_instance)

        logger.info("✅ Патч OK! scan_market теперь использует UnifiedAutoScanner")

        return True

    except Exception as e:
        logger.error(f"❌ Ошибка применения патча: {e}")
        return False
