# Downloader Bot

Telegram бот для скачивания видео из TikTok, Instagram, YouTube, Twitter и других платформ.

![CI](https://github.com/amirim1/tik_tok_bot/actions/workflows/ci.yml/badge.svg)
![Version](https://img.shields.io/badge/version-0.4.3-blue)
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
| Общий дедлайн на получение ссылки, ссылка с подписью из TikTok | ✅ |
| Проверка контента (контейнер по содержимому: mp4/webm/mkv; SSRF-фильтр `video_url` с DNS) | ✅ |
| Команда `/help` | ✅ |
| Graceful shutdown (SIGTERM/SIGINT: до 10 с на завершение загрузок) | ✅ |
| Автоустановка одной командой | ✅ |
| Docker (non-root, .dockerignore) | ✅ |
| systemd автозапуск | ✅ |
| CI: ruff + pytest (Python 3.11-3.13, 3.14 - экспериментально) | ✅ |

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

**Termux / телефон:** на телефоне `curl-cffi` не установлен и не нужен (TikTok работает через собственный API-даунлоадер), поэтому устанавливайте облегчённый набор зависимостей:

```bash
pip install -r requirements-phone.txt
```

Зависимости закреплены точными версиями (`==`) - это то, что проверено на телефоне. `yt-dlp` обновляйте только осознанно (он ломается от изменений сайтов, а не от багов): правка `requirements.txt` и `requirements-phone.txt` + запись в `CHANGELOG.md`. `curl-cffi` в `requirements.txt` остаётся диапазоном (на телефоне не ставится).

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
| `DOWNLOAD_TIMEOUT` | `30` | Таймаут загрузки и сетевой таймаут yt-dlp (сек) |
| `GET_VIDEO_DEADLINE` | `120` | Общий дедлайн на получение прямой ссылки (сек); затем пользователь получает «Превышено время получения ссылки» |
| `LOG_FILE` | `bot.log` | Файл лога (root-хендлеры пишут и в файл, и в stdout/stderr) |

`LOG_FILE`, `TEMP_DIR`, `RATE_LIMIT_FILE`, `ALLOWED_USERS_FILE` считаются от каталога проекта (каталог `main.py`), а не от текущего каталога запуска: бот можно запускать из любого места. Абсолютный путь из переменной берётся как есть. При первом старте после v0.4.2 файлы `rate_limit.json` и `allowed_users.json` из каталога запуска копируются в каталог проекта (старые не удаляются).

## Управление доступом

Только администратор может изменять whitelist прямо в личном чате с ботом:

```text
/access add 123456789
/access remove 123456789
/access list
```

В `/access list` бот выводит ID и `@username`, если Telegram предоставляет его для этого чата; иначе показывает имя или только ID.

## Безопасность скачивания

Если DNS отвечает адресами только из `198.18.0.0/15` (FakeIP - так домашний роутер с прозрачным прокси резолвит имена вместо настоящих адресов), ответ считается допустимым: роутер сам соединяется по имени хоста. Смешанный ответ (FakeIP плюс любой другой адрес) и IP-литерал из этого диапазона прямо в URL по-прежнему запрещены.

`video_url`, полученный от сторонних API и yt-dlp, проверяется перед запросом и на каждом редиректе: только http(s), хост не `localhost`, и ни один IP из DNS-ответа не приватный, loopback или link-local (IPv4 и IPv6, включая IPv4-mapped). Неразрешающийся хост отклоняется.

Остаточный риск: соединение идёт по имени хоста, а не закреплено за проверенным IP, поэтому атакующий DNS с коротким TTL может отдать публичный адрес на проверку и приватный на запрос (DNS rebinding). Риск ограничен сторонними API, из которых приходит `video_url`.

## Разработка

```bash
pip install -r requirements-dev.txt
ruff check .   # линт
pytest         # тесты (122 шт.; сеть в тестах запрещена)
```

## История версий

См. [CHANGELOG.md](CHANGELOG.md).

### v0.4.3 - Аудит 2026-11-23
- Файлы состояния хранятся в каталоге проекта, старые переносятся при старте
- `rate_limit.json` пишется атомарно; ошибки TeleBot не дублируются в логе
- Общий дедлайн на получение ссылки (`GET_VIDEO_DEADLINE`, 120 с) и сетевые таймауты yt-dlp
- SSRF-фильтр проверяет DNS-ответ хоста (остаточный риск DNS rebinding - см. выше)
- webm/mkv от yt-dlp отправляются с расширением по содержимому
- Ссылка с подписью («🎵 оригинальный звук - …») обрабатывается
- SIGTERM: новые запросы не принимаются, загрузки получают до 10 с на завершение
- Зависимости закреплены версиями, GitHub Actions - по SHA, базовый образ Docker - по digest

### v0.4.2 — Безопасность
- SSRF-фильтр `video_url`: приватные/loopback-адреса, компактные IPv4-формы и `localhost` отклоняются; редиректы скачивания проверяются вручную
- Ответ о rate-limit уходит вне глобального лока; остаток секунд до сброса в сообщении
- Скрытый ввод токена в install.sh (без токена в argv)

### v0.4.1 — Исправление CI
- Исправлен формат тестового Telegram-токена для новых версий `pyTelegramBotAPI`

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
