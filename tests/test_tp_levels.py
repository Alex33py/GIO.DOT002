#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тестовый скрипт для диагностики и исправления TP levels в БД
tests/test_tp_levels.py
"""

import asyncio
import aiosqlite
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))


async def diagnose_and_fix_tp_levels():
    """Диагностика и исправление TP levels"""

    root_path = Path(__file__).parent.parent
    db_path = root_path / "data" / "gio_crypto_bot.db"

    if not db_path.exists():
        print(f"❌ База данных не найдена: {db_path}")
        return

    print("=" * 80)
    print("🔍 ДИАГНОСТИКА TP LEVELS В БД")
    print("=" * 80)
    print(f"📁 База данных: {db_path}")
    print(f"📊 Размер файла: {db_path.stat().st_size:,} байт")
    print(f"⏰ Последнее изменение: {datetime.fromtimestamp(db_path.stat().st_mtime)}")
    print()

    try:
        async with aiosqlite.connect(db_path) as db:
            # Получить общую статистику
            cursor = await db.execute("SELECT COUNT(*) FROM signals")
            total_signals = (await cursor.fetchone())[0]

            cursor = await db.execute(
                """
                SELECT COUNT(*) FROM signals WHERE status = 'active'
            """
            )
            active_signals = (await cursor.fetchone())[0]

            print(f"📊 Статистика БД:")
            print(f"   • Всего сигналов: {total_signals}")
            print(f"   • Активных: {active_signals}")
            print()

            if active_signals == 0:
                print("⚠️  Активных сигналов нет!")
                return

            # Получить топ-10 прибыльных активных сигналов
            query = """
                SELECT id, symbol, direction, entry_price, current_price,
                       tp1, tp2, tp3, stop_loss,
                       COALESCE(roi, 0) as roi,
                       COALESCE(tp1_hit, 0) as tp1_hit,
                       COALESCE(tp2_hit, 0) as tp2_hit,
                       COALESCE(tp3_hit, 0) as tp3_hit,
                       COALESCE(sl_hit, 0) as sl_hit,
                       status
                FROM signals
                WHERE status = 'active'
                ORDER BY roi DESC
                LIMIT 10
            """

            cursor = await db.execute(query)
            signals = await cursor.fetchall()

            print(f"✅ Найдено {len(signals)} топовых активных сигналов")
            print()

            issues_found = 0
            fixed_count = 0
            current_price_missing = 0

            for idx, row in enumerate(signals, 1):
                (
                    sig_id,
                    symbol,
                    direction,
                    entry,
                    current_price,
                    tp1,
                    tp2,
                    tp3,
                    sl,
                    roi,
                    tp1_hit,
                    tp2_hit,
                    tp3_hit,
                    sl_hit,
                    status,
                ) = row

                print(f"{'='*80}")
                print(f"#{idx}. 📊 {symbol} (ID: {sig_id})")
                print(f"{'='*80}")
                print(f"   Direction:     {direction}")
                print(f"   Entry:         ${entry:.4f}")

                # Проверка current_price
                if current_price is None or current_price <= 0:
                    print(f"   Current Price: ❌ НЕ УСТАНОВЛЕНА (None)")
                    print(f"   Current ROI:   {roi:+.2f}%")
                    print()
                    print(f"   ⚠️ ПРОБЛЕМА: current_price не обновляется в БД!")
                    print(f"      Это означает что Price Updater НЕ РАБОТАЕТ")
                    current_price_missing += 1

                    # Рассчитать из ROI
                    if direction.upper() == "SHORT":
                        current_price = entry * (1 - roi / 100)
                    else:
                        current_price = entry * (1 + roi / 100)

                    print(f"   📈 Расчётная цена: ${current_price:.4f}")
                else:
                    print(f"   Current Price: ${current_price:.4f}")
                    print(f"   Current ROI:   {roi:+.2f}%")

                print()
                print(
                    f"   TP1:           ${tp1:.4f} (hit: {'✅' if tp1_hit else '❌'})"
                )
                print(
                    f"   TP2:           ${tp2:.4f} (hit: {'✅' if tp2_hit else '❌'})"
                )
                print(
                    f"   TP3:           ${tp3:.4f} (hit: {'✅' if tp3_hit else '❌'})"
                )
                print(f"   SL:            ${sl:.4f} (hit: {'✅' if sl_hit else '❌'})")
                print()

                # === ДИАГНОСТИКА ===

                # Проверка 1: TP = 0
                if tp1 <= 0 or tp2 <= 0 or tp3 <= 0:
                    print(f"   ❌ ПРОБЛЕМА: TP не установлены")
                    issues_found += 1

                    if direction.upper() == "LONG":
                        new_tp1, new_tp2, new_tp3 = (
                            entry * 1.01,
                            entry * 1.02,
                            entry * 1.03,
                        )
                        new_sl = entry * 0.98
                    else:
                        new_tp1, new_tp2, new_tp3 = (
                            entry * 0.99,
                            entry * 0.98,
                            entry * 0.97,
                        )
                        new_sl = entry * 1.02

                    await db.execute(
                        """
                        UPDATE signals
                        SET tp1 = ?, tp2 = ?, tp3 = ?, stop_loss = ?
                        WHERE id = ?
                    """,
                        (new_tp1, new_tp2, new_tp3, new_sl, sig_id),
                    )

                    print(f"   ✅ ИСПРАВЛЕНО:")
                    print(
                        f"      TP1: ${new_tp1:.4f} | TP2: ${new_tp2:.4f} | TP3: ${new_tp3:.4f}"
                    )
                    fixed_count += 1
                    print()
                    continue

                # Проверка 2: Логика TP для SHORT
                if direction.upper() == "SHORT":
                    # Для SHORT: TP ниже entry
                    should_tp1 = current_price <= tp1
                    should_tp2 = current_price <= tp2
                    should_tp3 = current_price <= tp3

                    print(f"   🎯 Анализ TP (SHORT):")
                    print(f"      Текущая цена: ${current_price:.4f}")
                    print(
                        f"      TP1 @ ${tp1:.4f}: {'✅ ДА' if should_tp1 else '❌ НЕТ'} (цена {'≤' if should_tp1 else '>'} TP1)"
                    )
                    print(
                        f"      TP2 @ ${tp2:.4f}: {'✅ ДА' if should_tp2 else '❌ НЕТ'} (цена {'≤' if should_tp2 else '>'} TP2)"
                    )
                    print(
                        f"      TP3 @ ${tp3:.4f}: {'✅ ДА' if should_tp3 else '❌ НЕТ'} (цена {'≤' if should_tp3 else '>'} TP3)"
                    )
                    print()

                    if should_tp1 and not tp1_hit:
                        print(f"   ⚠️ TP1 должен быть достигнут!")
                        print(f"      ${current_price:.4f} <= ${tp1:.4f} = TRUE")
                        issues_found += 1

                    if should_tp2 and not tp2_hit:
                        print(f"   ⚠️ TP2 должен быть достигнут!")
                        issues_found += 1

                    if should_tp3 and not tp3_hit:
                        print(f"   ⚠️ TP3 должен быть достигнут!")
                        issues_found += 1

                # Проверка 3: Логика TP для LONG
                elif direction.upper() == "LONG":
                    # Для LONG: TP выше entry
                    should_tp1 = current_price >= tp1
                    should_tp2 = current_price >= tp2
                    should_tp3 = current_price >= tp3

                    print(f"   🎯 Анализ TP (LONG):")
                    print(f"      Текущая цена: ${current_price:.4f}")
                    print(
                        f"      TP1 @ ${tp1:.4f}: {'✅ ДА' if should_tp1 else '❌ НЕТ'} (цена {'≥' if should_tp1 else '<'} TP1)"
                    )
                    print(
                        f"      TP2 @ ${tp2:.4f}: {'✅ ДА' if should_tp2 else '❌ НЕТ'} (цена {'≥' if should_tp2 else '<'} TP2)"
                    )
                    print(
                        f"      TP3 @ ${tp3:.4f}: {'✅ ДА' if should_tp3 else '❌ НЕТ'} (цена {'≥' if should_tp3 else '<'} TP3)"
                    )
                    print()

                    if should_tp1 and not tp1_hit:
                        print(f"   ⚠️ TP1 должен быть достигнут!")
                        issues_found += 1

                    if should_tp2 and not tp2_hit:
                        print(f"   ⚠️ TP2 должен быть достигнут!")
                        issues_found += 1

                    if should_tp3 and not tp3_hit:
                        print(f"   ⚠️ TP3 должен быть достигнут!")
                        issues_found += 1

                print()

            # Сохранить изменения
            await db.commit()

            print("=" * 80)
            print(f"📊 РЕЗУЛЬТАТ ДИАГНОСТИКИ:")
            print("=" * 80)
            print(f"   ✅ Проверено сигналов: {len(signals)}")
            print(f"   ⚠️  Найдено проблем:    {issues_found}")
            print(f"   🔧 Исправлено:         {fixed_count}")
            print(f"   ❌ current_price = None: {current_price_missing}")
            print("=" * 80)

            # Рекомендации
            if current_price_missing > 0 or issues_found > fixed_count:
                print()
                print("🔴 КРИТИЧЕСКАЯ ПРОБЛЕМА ОБНАРУЖЕНА!")
                print("=" * 80)
                print()
                print(
                    f"❌ У {current_price_missing} из {len(signals)} сигналов current_price = None"
                )
                print()
                print("💡 ЭТО ОЗНАЧАЕТ:")
                print("   • Price Updater НЕ РАБОТАЕТ или НЕ ЗАПУЩЕН")
                print("   • ROI Tracker НЕ может обновлять TP, т.к. нет текущей цены")
                print("   • Мониторинг работает вхолостую")
                print()
                print("🔧 РЕШЕНИЕ:")
                print("   1. Проверьте логи бота:")
                print("      Должно быть: '🔄 Price updater started'")
                print("      Должно быть: '💰 Prices updated for X/Y symbols'")
                print()
                print("   2. Проверьте что ROI Tracker инициализирован:")
                print("      Должно быть: '✅ ROI Tracker started with price caching'")
                print()
                print("   3. Перезапустите бота: python main.py")
                print()
                print("=" * 80)

    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}")
        import traceback

        traceback.print_exc()


def main():
    print()
    print("🔧 GIO Crypto Bot v3.0 - TP Levels Diagnostic Tool")
    print()

    try:
        asyncio.run(diagnose_and_fix_tp_levels())
    except KeyboardInterrupt:
        print("\n⚠️  Прервано")
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")


if __name__ == "__main__":
    main()
