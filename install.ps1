<#
.SYNOPSIS
    TikTok Downloader Bot — установка на Windows
.DESCRIPTION
    Автоматическая установка: проверяет Python, клонирует репозиторий,
    создаёт виртуальное окружение, устанавливает зависимости.
.PARAMETER Token
    Telegram Bot Token (опционально)
.PARAMETER RepoOwner
    Владелец репозитория на GitHub (по умолчанию пусто)
.EXAMPLE
    .\install.ps1 -Token "123456:ABC-DEF1234ghIkl"
#>

param(
    [string]$Token = "",
    [string]$RepoOwner = "amirim1"
)

$ErrorActionPreference = "Stop"
$RepoName = "tik_tok_bot"
$Branch = "main"
$RepoDir = $RepoName

function Write-Step($msg) { Write-Host ">> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "[!] $msg" -ForegroundColor Yellow }
function Write-Err($msg)  { Write-Host "[X] $msg" -ForegroundColor Red }

Clear-Host
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host "  TikTok Downloader Bot - Installer" -ForegroundColor Cyan
Write-Host "=======================================" -ForegroundColor Cyan
Write-Host ""

# Проверка Python
Write-Step "Проверка Python..."
$python = $null
foreach ($cmd in @("python3", "python")) {
    try {
        $v = & $cmd --version 2>&1
        if ($v -match "Python (\d+)\.(\d+)") {
            if ([int]$Matches[1] -ge 3 -and [int]$Matches[2] -ge 8) {
                $python = $cmd
                Write-OK "Найден $($v.Trim())"
                break
            }
        }
    } catch {}
}
if (-not $python) {
    Write-Warn "Python 3.8+ не найден."
    Write-Warn "Скачайте: https://www.python.org/downloads/"
    Write-Warn "При установке отметьте 'Add Python to PATH'"
    $response = Read-Host "Нажмите Enter после установки Python, или 'q' для выхода"
    if ($response -eq 'q') { exit 1 }
    # Повторная проверка
    foreach ($cmd in @("python3", "python")) {
        try { $v = & $cmd --version 2>&1; if ($v -match "Python 3") { $python = $cmd; break } } catch {}
    }
    if (-not $python) { Write-Err "Python не обнаружен"; exit 1 }
    Write-OK "Найден $($v.Trim())"
}

# Проверка git
Write-Step "Проверка Git..."
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Warn "Git не найден. Установите: https://git-scm.com/download/win"
    $response = Read-Host "Нажмите Enter после установки Git, или 'q' для выхода"
    if ($response -eq 'q') { exit 1 }
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
        Write-Err "Git не обнаружен"; exit 1
    }
}
Write-OK "Git найден"

# Клонирование
Write-Step "Загрузка репозитория..."
$repoUrl = "https://github.com/$RepoOwner/$RepoName.git"

if (Test-Path $RepoDir) {
    Write-Warn "Директория $RepoDir уже существует. Обновляю..."
    Push-Location $RepoDir
    try {
        & git pull origin $Branch
        if ($LASTEXITCODE -ne 0) {
            Write-Warn "Не удалось обновить репозиторий (нет сети или есть локальные правки). Продолжаю с текущей версией."
        }
    } finally {
        Pop-Location
    }
} else {
    & git clone --depth 1 -b $Branch $repoUrl
    if ($LASTEXITCODE -ne 0) { Write-Err "Ошибка клонирования"; exit 1 }
}
Write-OK "Репозиторий загружен"

# Виртуальное окружение
Push-Location $RepoDir
try {
    Write-Step "Создание виртуального окружения..."
    & $python -m venv venv
    if ($LASTEXITCODE -ne 0) { Write-Err "Не удалось создать виртуальное окружение"; exit 1 }

    # Работаем через venv\Scripts\python.exe напрямую: активация Activate.ps1
    # может быть запрещена политикой выполнения (Restricted).
    $venvPython = Join-Path (Get-Location) "venv\Scripts\python.exe"
    Write-Step "Установка зависимостей..."
    & $venvPython -m pip install -q -r requirements.txt
    if ($LASTEXITCODE -ne 0) { Write-Err "Не удалось установить зависимости"; exit 1 }
    Write-OK "Зависимости установлены"

    # .env
    if (-not (Test-Path ".env")) {
        Copy-Item ".env.example" ".env"
        Write-OK ".env создан из .env.example"

        # Читаем/пишем UTF-8 без BOM явно: PS 5.1 по умолчанию использует ANSI,
        # что портит кириллические комментарии из .env.example.
        $envPath = Join-Path (Get-Location) ".env"
        $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
        if ($Token) {
            $content = [System.IO.File]::ReadAllText($envPath, [System.Text.Encoding]::UTF8)
            [System.IO.File]::WriteAllText($envPath, $content.Replace("your_bot_token_here", $Token), $utf8NoBom)
            Write-OK "Токен установлен из параметра"
        } else {
            $inputToken = Read-Host "Введите Telegram Bot Token (Enter чтобы пропустить)"
            if ($inputToken) {
                $content = [System.IO.File]::ReadAllText($envPath, [System.Text.Encoding]::UTF8)
                [System.IO.File]::WriteAllText($envPath, $content.Replace("your_bot_token_here", $inputToken), $utf8NoBom)
                Write-OK "Токен сохранён"
            } else {
                Write-Warn "Токен не указан. Отредактируйте .env вручную."
            }
        }
    } else {
        Write-Warn ".env уже существует"
    }
} finally {
    Pop-Location
}

# Запуск
Write-Host ""
Write-Host "=======================================" -ForegroundColor Green
Write-Host "  Установка завершена!" -ForegroundColor Green
Write-Host "=======================================" -ForegroundColor Green
Write-Host ""
$currentDir = (Get-Location).Path
Write-Host "  Запуск (без активации venv):"
Write-Host "    cd $currentDir"
Write-Host "    .\venv\Scripts\python.exe main.py"
Write-Host ""
Write-Host "  Или с активацией venv (если разрешена политика выполнения):"
Write-Host "    .\venv\Scripts\Activate.ps1"
Write-Host "    python main.py"
Write-Host ""
