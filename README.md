# Downloader Bot

Telegram бот для скачивания видео из TikTok, Instagram, YouTube, Twitter и других платформ.

![CI](https://github.com/amirim1/tik_tok_bot/actions/workflows/ci.yml/badge.svg)
![Version](https://img.shields.io/badge/version-0.4.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Возможности

| Возможность | Статус |
|-------------|--------|
| TikTok (через собственные API) | ✅ |
| Instagram (Reels, посты) | ✅ |
| YouTube / YouTube Shorts | ✅ |
| Twitter / X | ✅ |
| Reddit | ✅ |
| Facebook | ✅ |
| Pinterest | ✅ |
| Vimeo | ✅ |
| VK | ✅ |
| Whitelist и управление доступом из Telegram | ✅ |
| Rate limit с персистентностью и автоочисткой | ✅ |
| Проверка контента (MP4 magic bytes + схема URL) | ✅ |
| Команда `/help` | ✅ |
| Graceful shutdown (SIGTERM/SIGINT) | ✅ |
| Автоустановка одной командой | ✅ |
| Docker (non-root, .dockerignore) | ✅ |
| systemd автозапуск | ✅ |
| CI: ruff + pytest (Python 3.11/3.12) | ✅ |

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
docker run --init --env-file .env tik-tok-bot
```

Флаг `--init` гарантирует быстрое и корректное завершение процесса (бот обрабатывает SIGTERM).

## systemd (автозапуск на сервере)

В скрипте установки есть опция настройки systemd. Вручную:

```bash
sudo tee /etc/systemd/system/tik-tok-bot.service > /dev/null << EOF
[Unit]
Description=Downloader Bot
Wants=network-online.target
After=network-online.target

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$(pwd)
ExecStart=$(pwd)/venv/bin/python $(pwd)/main.py
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
| `ADMIN_USER_ID` | — | **Обязательно.** Telegram ID администратора (только в закрытом `.env`) |
| `ALLOWED_USERS` | (пусто) | Начальные ID whitelist для первого запуска |
| `ALLOWED_USERS_FILE` | `allowed_users.json` | Хранилище текущего whitelist, не попадает в Git |
| `DOWNLOAD_TIMEOUT` | `30` | Таймаут загрузки (сек) |

## Управление доступом

Только администратор может изменять whitelist прямо в личном чате с ботом:

```text
/access add 123456789
/access remove 123456789
/access list
```

В `/access list` бот выводит ID и `@username`, если Telegram предоставляет его для этого чата; иначе показывает имя или только ID.

## Разработка

```bash
pip install -r requirements-dev.txt
ruff check .   # линт
pytest         # тесты (62 шт.)
```

## История версий

См. [CHANGELOG.md](CHANGELOG.md).

### v0.4 — Whitelist и устойчивый TikTok
- Управление whitelist командой `/access`, вывод username в списке
- TikTok через yt-dlp с browser impersonation и CDN cookies

### v0.3 — Аудит и надёжность
- Исправлено видео без звука для yt-dlp (muxed-формат вместо split-DASH)
- URL-матчинг по hostname, проверка схемы `video_url`
- CI (ruff + pytest), dev-зависимости, .dockerignore, non-root Docker
- Graceful shutdown по SIGTERM, `/help`, автоочистка rate-limit

### v0.2 — Multi-service
- Поддержка Instagram, YouTube, Twitter/X, Reddit, Facebook, Pinterest, Vimeo, VK
- Универсальный скачиватель на `yt-dlp` (~1500 сайтов)
- Модульная архитектура `src/downloaders/`
- Валидация URL для всех поддерживаемых платформ

### v0.1 — Initial
- Скачивание TikTok через 3 API с fallback
- Rate limit, контроль доступа, Docker, systemd
- Автоустановка одной командой
