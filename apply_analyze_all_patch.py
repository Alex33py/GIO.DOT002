# -*- coding: utf-8 -*-
"""
Скрипт применения патча для /analyze_batching ALL
Запустите ОДИН РАЗ для модификации бота
"""

import sys
import os

# Добавление пути к модулям
sys.path.insert(0, os.path.dirname(__file__))

def main():
    """Основная функция"""
    print("🚀 Применение патча для /analyze_batching ALL")
    print("=" * 60)

    # Поиск main.py
    main_files = ['main.py', 'bot.py', 'gio_bot.py']
    main_file = None

    for filename in main_files:
        if os.path.exists(filename):
            main_file = filename
            break

    if not main_file:
        print("❌ Главный файл бота не найден!")
        print("Укажите путь к файлу вручную:")
        main_file = input("Путь к main.py: ").strip()

        if not os.path.exists(main_file):
            print("❌ Файл не существует!")
            return False

    print(f"📁 Найден файл: {main_file}")

    # Чтение содержимого
    with open(main_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Проверка, не применён ли уже патч
    if 'apply_analyze_batching_all_patch' in content:
        print("✅ Патч уже применён!")
        return True

    # Создание резервной копии
    backup_file = main_file + '.backup_analyze_all'
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"💾 Создана резервная копия: {backup_file}")

    # Добавление импорта
    import_line = "\nfrom patches.analyze_batching_all_patch import apply_analyze_batching_all_patch\n"

    # Поиск места для вставки (после других импортов)
    import re
    import_pattern = r'(^import\s+\w+|^from\s+\w+)'
    matches = list(re.finditer(import_pattern, content, re.MULTILINE))

    if matches:
        last_import_end = matches[-1].end()
        newline_pos = content.find('\n', last_import_end)
        if newline_pos != -1:
            content = content[:newline_pos+1] + import_line + content[newline_pos+1:]
    else:
        content = import_line + content

    # Поиск места для применения патча (после инициализации telegram_bot_handler)
    patch_code = '''
        # ========== ПАТЧ: /analyze_batching ALL ==========
        apply_analyze_batching_all_patch(self)
        # ==================================================
'''

    # Поиск строки с telegram_bot_handler
    pattern = r'(self\.telegram_bot_handler\s*=.*?\n)'
    match = re.search(pattern, content)

    if match:
        insert_pos = match.end()
        content = content[:insert_pos] + patch_code + content[insert_pos:]

        # Сохранение модифицированного файла
        with open(main_file, 'w', encoding='utf-8') as f:
            f.write(content)

        print(f"✅ Файл {main_file} модифицирован!")
        print(f"💾 Резервная копия: {backup_file}")
        print("\n✅ ПАТЧ ПРИМЕНЁН УСПЕШНО!")
        print("\n📋 Теперь доступно:")
        print("   /analyze_batching          - анализ BTCUSDT")
        print("   /analyze_batching ETHUSDT  - анализ ETHUSDT")
        print("   /analyze_batching ALL      - анализ ВСЕХ пар!")
        print("\n🔄 Перезапустите бота для применения изменений")
        return True
    else:
        print("⚠️ Не найдено место для автоматической вставки")
        print("📝 Добавьте вручную в __init__ метод после инициализации telegram_bot_handler:")
        print(patch_code)
        return False


if __name__ == "__main__":
    main()
