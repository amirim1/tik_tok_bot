#!/usr/bin/env bash
#
# TikTok Downloader Bot — автоматическая установка
#
# Использование:
#   bash <(curl -fsSL https://raw.githubusercontent.com/amirim1/tik_tok_bot/main/install.sh)
#   INSTALL_DIR=/srv/tiktok-bot bash <(curl -fsSL ...)  # кастомный путь
#   # или локально из репозитория:
#   bash install.sh
#
set -euo pipefail

REPO_OWNER="${REPO_OWNER:-amirim1}"
REPO_NAME="tik_tok_bot"
REPO_BRANCH="main"
INSTALL_DIR="${INSTALL_DIR:-/opt/tik_tok_bot}"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log()   { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
err()   { echo -e "${RED}[✗]${NC} $1"; }
info()  { echo -e "${CYAN}[i]${NC} $1"; }
header(){ echo -e "\n${CYAN}━━━ $1 ━━━${NC}"; }

cleanup() { exit 1; }
trap cleanup INT TERM

PM=""
DETECTED_DIR=""
if [ -f "main.py" ] && [ -f "requirements.txt" ]; then
    DETECTED_DIR="$(pwd)"
fi

detect_os() {
    case "$(uname -s)" in
        Linux*) OS="linux";;
        Darwin*) OS="macos";;
        *) err "OS $(uname -s) не поддерживается"; exit 1;;
    esac
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_ID="$ID"; OS_VERSION="$VERSION_ID"
    fi
    if command -v dnf &>/dev/null; then
        PM="dnf"
    elif command -v yum &>/dev/null; then
        PM="yum"
    fi
}

install_system_deps() {
    case "$OS_ID" in
        ubuntu|debian)
            sudo apt-get update -qq
            sudo apt-get install -y -qq python3 python3-pip python3-venv git curl
            ;;
        centos|rhel|fedora|almalinux|rocky)
            sudo $PM install -y python3 python3-pip python3-venv git curl
            ;;
        *)
            warn "Неизвестный дистрибутив. Предполагаю, что Python уже установлен."
            ;;
    esac
}

check_python() {
    if ! command -v python3 &>/dev/null; then
        info "Python3 не найден. Устанавливаю..."
        install_system_deps
    fi
    PY=$(command -v python3)
    VER=$($PY --version 2>&1 | cut -d' ' -f2)
    info "Python $VER"
    local maj=$(echo "$VER" | cut -d. -f1)
    local min=$(echo "$VER" | cut -d. -f2)
    if [ "$maj" -lt 3 ] || { [ "$maj" -eq 3 ] && [ "$min" -lt 8 ]; }; then
        err "Требуется Python 3.8+, найден $VER"; exit 1
    fi

    install_venv_if_needed
}

install_venv_if_needed() {
    local testdir="/tmp/.tik_venv_test_$$"
    $PY -m venv "$testdir" &>/dev/null && { rm -rf "$testdir"; return 0; }
    rm -rf "$testdir"

    case "$OS_ID" in
        ubuntu|debian)
            warn "python3-venv не установлен. Устанавливаю..."
            sudo apt-get install -y -qq python3-venv 2>/dev/null || \
            sudo apt-get install -y -qq python3.12-venv 2>/dev/null || \
            sudo apt-get install -y -qq python3.11-venv 2>/dev/null || true
            ;;
        centos|rhel|fedora|almalinux|rocky)
            warn "python3-venv не установлен. Устанавливаю..."
            sudo $PM install -y python3-venv 2>/dev/null || true
            ;;
    esac

    $PY -m venv "$testdir" &>/dev/null || {
        rm -rf "$testdir"
        err "Не удалось создать виртуальное окружение."
        err "Установите python3-venv вручную: sudo apt install python3-venv"
        exit 1
    }
    rm -rf "$testdir"
    log "python3-venv установлен"
}

prepare_dir() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        sudo mkdir -p "$dir"
        sudo chown "$(whoami):$(whoami)" "$dir"
        log "Создана директория $dir"
    fi
}

clone_repo() {
    local url="https://github.com/$REPO_OWNER/$REPO_NAME.git"
    if [ -d "$INSTALL_DIR/.git" ]; then
        warn "Репозиторий уже существует. Обновляю..."
        cd "$INSTALL_DIR"
        git pull origin "$REPO_BRANCH" 2>/dev/null || true
    else
        info "Клонирую репозиторий в $INSTALL_DIR ..."
        git clone --depth 1 -b "$REPO_BRANCH" "$url" "$INSTALL_DIR"
        cd "$INSTALL_DIR"
    fi
}

setup_venv() {
    if [ -f "venv/bin/python3" ]; then
        info "Виртуальное окружение уже существует. Пропускаю."
        source venv/bin/activate
        return
    fi
    if [ -d "venv" ]; then
        warn "Обнаружено повреждённое venv. Удаляю и создаю заново..."
        rm -rf venv
    fi
    info "Создаю виртуальное окружение..."
    $PY -m venv venv
    source venv/bin/activate
    info "Устанавливаю зависимости..."
    pip install -q -r requirements.txt
}

setup_env() {
    [ -f ".env" ] && { warn ".env уже существует. Пропускаю."; return; }
    cp .env.example .env
    log ".env создан из .env.example"

    if [ -n "${TELEGRAM_BOT_TOKEN:-}" ]; then
        sed -i "s/your_bot_token_here/$TELEGRAM_BOT_TOKEN/" .env
        log "TELEGRAM_BOT_TOKEN установлен из переменной окружения"
        return
    fi

    echo ""
    read -p "Введите Telegram Bot Token (оставьте пустым, чтобы указать позже): " TOKEN_INPUT
    if [ -n "$TOKEN_INPUT" ]; then
        if [[ "$(uname -s)" == "Darwin" ]]; then
            sed -i '' "s/your_bot_token_here/$TOKEN_INPUT/" .env
        else
            sed -i "s/your_bot_token_here/$TOKEN_INPUT/" .env
        fi
        log "Токен сохранён в .env"
    else
        warn "Токен не указан. Отредактируйте .env вручную."
    fi
}

setup_systemd() {
    command -v systemctl &>/dev/null || return
    echo ""
    read -p "Настроить автозапуск через systemd? (y/N): " ANS
    [[ ! "$ANS" =~ ^[Yy]$ ]] && return

    local svc="tik-tok-bot"
    local dir="$INSTALL_DIR"
    local usr="${SUDO_USER:-$(whoami)}"

    sudo tee /etc/systemd/system/$svc.service > /dev/null << EOF
[Unit]
Description=TikTok Downloader Bot
After=network.target

[Service]
Type=simple
User=$usr
WorkingDirectory=$dir
ExecStart=$dir/venv/bin/python main.py
Restart=always
RestartSec=10
EnvironmentFile=$dir/.env

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable --now "$svc"
    log "Сервис $svc установлен и запущен"
    info "Статус: sudo systemctl status $svc"
    info "Логи: sudo journalctl -u $svc -f"
}

summary() {
    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║     Установка завершена!                 ║"
    echo "╚══════════════════════════════════════════╝"
    echo ""
    if grep -q "your_bot_token_here" .env 2>/dev/null; then
        warn "Не забудьте указать TELEGRAM_BOT_TOKEN в .env"
    fi
    echo "  Директория: $INSTALL_DIR"
    echo ""
    echo "  Запуск:"
    echo "    cd $INSTALL_DIR"
    echo "    source venv/bin/activate"
    echo "    python main.py"
    echo ""
    echo "  systemd (если настроен):"
    echo "    sudo systemctl start tik-tok-bot"
    echo "    sudo journalctl -u tik-tok-bot -f"
    echo ""
    echo "  Docker:"
    echo "    cd $INSTALL_DIR"
    echo "    docker build -t tik-tok-bot ."
    echo "    docker run --env-file .env tik-tok-bot"
    echo ""
}

main() {
    echo ""
    echo "╔══════════════════════════════════════════╗"
    echo "║   TikTok Downloader Bot — Installer      ║"
    echo "╚══════════════════════════════════════════╝"

    detect_os
    info "ОС: $OS_ID $OS_VERSION"
    check_python

    if [ -n "$DETECTED_DIR" ]; then
        info "Установка из локальной директории: $DETECTED_DIR"
        cd "$DETECTED_DIR"
    else
        header "Подготовка $INSTALL_DIR"
        prepare_dir "$INSTALL_DIR"
        clone_repo
    fi

    header "Настройка окружения"
    setup_venv
    setup_env

    header "Автозапуск (опционально)"
    setup_systemd

    summary
}

main
