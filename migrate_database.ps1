# migrate_database.ps1
# Скрипт миграции базы данных GIO Crypto Bot для Windows

Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  🔧 GIO CRYPTO BOT - DATABASE MIGRATION TOOL (PowerShell)" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""

# Переменные
$ProjectRoot = $PSScriptRoot
$DatabaseDir = Join-Path $ProjectRoot "database"
$DataDir = Join-Path $ProjectRoot "data"
$SchemaFile = Join-Path $DatabaseDir "schema.py"
$DatabaseFile = Join-Path $DataDir "gio_bot.db"
$BackupFile = Join-Path $DataDir "gio_bot.db.backup_$(Get-Date -Format 'yyyyMMdd_HHmmss')"

# Проверка наличия Python
Write-Host "1️⃣ Проверка Python..." -ForegroundColor Yellow
try {
    $pythonVersion = python --version 2>&1
    Write-Host "   ✅ $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "   ❌ Python не найден! Установите Python 3.8+" -ForegroundColor Red
    exit 1
}

# Создание папки database если её нет
Write-Host ""
Write-Host "2️⃣ Проверка структуры папок..." -ForegroundColor Yellow
if (-Not (Test-Path $DatabaseDir)) {
    New-Item -ItemType Directory -Path $DatabaseDir -Force | Out-Null
    Write-Host "   ✅ Создана папка: database\" -ForegroundColor Green
} else {
    Write-Host "   ✅ Папка database\ существует" -ForegroundColor Green
}

if (-Not (Test-Path $DataDir)) {
    New-Item -ItemType Directory -Path $DataDir -Force | Out-Null
    Write-Host "   ✅ Создана папка: data\" -ForegroundColor Green
} else {
    Write-Host "   ✅ Папка data\ существует" -ForegroundColor Green
}

# Проверка наличия schema.py
Write-Host ""
Write-Host "3️⃣ Проверка schema.py..." -ForegroundColor Yellow
if (-Not (Test-Path $SchemaFile)) {
    Write-Host "   ❌ Файл database\schema.py не найден!" -ForegroundColor Red
    Write-Host "   📝 Создайте файл database\schema.py с кодом миграции" -ForegroundColor Yellow
    exit 1
} else {
    Write-Host "   ✅ Файл schema.py найден" -ForegroundColor Green
}

# Создание backup БД (если БД существует)
Write-Host ""
Write-Host "4️⃣ Создание backup базы данных..." -ForegroundColor Yellow
if (Test-Path $DatabaseFile) {
    try {
        Copy-Item -Path $DatabaseFile -Destination $BackupFile -Force
        Write-Host "   ✅ Backup создан: $BackupFile" -ForegroundColor Green
    } catch {
        Write-Host "   ⚠️ Не удалось создать backup: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "   ℹ️ База данных ещё не существует (будет создана)" -ForegroundColor Cyan
}

# Запуск миграции
Write-Host ""
Write-Host "5️⃣ Запуск миграции базы данных..." -ForegroundColor Yellow
Write-Host ""
Write-Host "   Выполняется: python database\schema.py" -ForegroundColor Cyan
Write-Host "   -------------------------------------------------------------------" -ForegroundColor Gray

try {
    # Запускаем Python скрипт миграции
    $output = python (Join-Path $DatabaseDir "schema.py") 2>&1

    # Выводим результат
    $output | ForEach-Object {
        if ($_ -match "✅") {
            Write-Host "   $_" -ForegroundColor Green
        } elseif ($_ -match "⚠️|⏭️") {
            Write-Host "   $_" -ForegroundColor Yellow
        } elseif ($_ -match "❌") {
            Write-Host "   $_" -ForegroundColor Red
        } elseif ($_ -match "🔧|📊") {
            Write-Host "   $_" -ForegroundColor Cyan
        } else {
            Write-Host "   $_" -ForegroundColor White
        }
    }

    Write-Host "   -------------------------------------------------------------------" -ForegroundColor Gray

} catch {
    Write-Host "   ❌ Ошибка выполнения миграции: $_" -ForegroundColor Red
    exit 1
}

# Проверка результата
Write-Host ""
Write-Host "6️⃣ Проверка результата..." -ForegroundColor Yellow
if (Test-Path $DatabaseFile) {
    $dbSize = (Get-Item $DatabaseFile).Length
    Write-Host "   ✅ База данных существует: $DatabaseFile" -ForegroundColor Green
    Write-Host "   📊 Размер: $([math]::Round($dbSize/1KB, 2)) KB" -ForegroundColor Cyan
} else {
    Write-Host "   ❌ База данных не найдена!" -ForegroundColor Red
    exit 1
}

# Итог
Write-Host ""
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host "  ✅ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!" -ForegroundColor Green
Write-Host "================================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📋 Что дальше:" -ForegroundColor Yellow
Write-Host "   1. Проверьте лог выше на наличие ошибок" -ForegroundColor White
Write-Host "   2. Запустите бота: python main.py" -ForegroundColor White
Write-Host "   3. Backup БД сохранён в: data\" -ForegroundColor White
Write-Host ""

# Пауза перед закрытием
Write-Host "Нажмите любую клавишу для выхода..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
