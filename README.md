# TikTok Downloader Bot

Telegram бот для скачивания видео из TikTok.

## Быстрая установка (одной командой)

**Linux / macOS:**
```bash
bash <(curl -fsSL https://raw.githubusercontent.com/amirim1/tik_tok_bot/main/install.sh)
```

**Windows (PowerShell):**
```powershell
iex ((New-Object Net.WebClient).DownloadString('https://raw.githubusercontent.com/amirim1/tik_tok_bot/main/install.ps1'))
```

Скрипт сам установит Python, Git, создаст виртуальное окружение, установит зависимости и настроит `.env`.

## Ручная установка

```bash
git clone https://github.com/amirim1/tik_tok_bot.git
cd tik_tok_bot
cp .env.example .env
# Отредактируйте .env — укажите TELEGRAM_BOT_TOKEN
python3 -m venv venv
source venv/bin/activate  # Windows: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
python main.py
```

## Docker

```bash
docker build -t tik-tok-bot .
docker run --env-file .env tik-tok-bot
```

## systemd (автозапуск на сервере)

В скрипте установки есть опция настройки systemd. Вручную:

```bash
sudo tee /etc/systemd/system/tik-tok-bot.service > /dev/null << EOF
[Unit]
Description=TikTok Downloader Bot
After=network.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python main.py
Restart=always
RestartSec=10
EnvironmentFile=$(pwd)/.env

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now tik-tok-bot
```

## Конфигурация

Все опции в `.env` (см. `.env.example`):

| Параметр | По умолчанию | Описание |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | — | **Обязательно.** Токен бота |
| `LOG_LEVEL` | `INFO` | Уровень логирования |
| `MAX_FILE_SIZE_MB` | `50` | Максимальный размер видео |
| `RATE_LIMIT_CALLS` | `5` | Лимит запросов на пользователя |
| `RATE_LIMIT_WINDOW` | `60` | Окно лимита (сек) |
| `ALLOWED_USERS` | (пусто) | Ограничение доступа по ID |
| `DOWNLOAD_TIMEOUT` | `30` | Таймаут загрузки (сек) |
