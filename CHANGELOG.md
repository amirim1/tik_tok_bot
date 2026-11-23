# Changelog

## v0.4.3 — Аудит (2026-11-23)

### Исправления
- **Файлы состояния в каталоге проекта.** `rate_limit.json`, `allowed_users.json`, `temp_videos`, `bot.log` считались от cwd запуска; на Termux (запуск из `$HOME`) состояние оказывалось в `~/`. Теперь пути - от каталога `main.py`; переменная окружения приоритетна, относительное значение тоже считается от каталога проекта. При старте старые `rate_limit.json`/`allowed_users.json` копируются в новое место (без удаления), старый `temp_videos` в cwd подчищается.
- `rate_limit.json` пишется атомарно (tmp + `os.replace`) - обрыв записи не оставлял битый JSON.
- Ошибки `TeleBot` не дублируются в логе: убран собственный StreamHandler библиотеки (в Termux stdout и stderr идут в один файл).
- **Общий дедлайн на получение ссылки** (`GET_VIDEO_DEADLINE`, по умолчанию 120 с): каждая попытка yt-dlp и legacy-API TikTok получает остаток времени и не начинается, если осталось меньше 5 с; пользователю отвечает «Превышено время получения ссылки». В yt-dlp заданы `socket_timeout`, `retries`, `extractor_retries`.
- **SSRF:** `is_safe_video_url` резолвит хост и отклоняет ссылку, если хотя бы один IP закрытый (IPv4, IPv6, IPv4-mapped IPv6, reserved/multicast); неразрешающийся хост отклоняется. Соединение не закреплено за проверенным IP - остаточный риск DNS rebinding описан в README.
- **SSRF и FakeIP:** для сети за прозрачным прокси с FakeIP-DNS - `SSRF_ALLOW_FAKEIP=1` (по умолчанию выключено): DNS-ответ целиком из `198.18.0.0/15` допустим, смешанный ответ и литерал в URL - нет.
- **webm/mkv от yt-dlp** больше не отбрасываются: контейнер определяется по содержимому (`detect_video_container`), расширение файла ставится по факту; в yt-dlp задан `merge_output_format=mp4`.
- **Ссылка с подписью:** из сообщения берётся первый http(s)-URL (TikTok присылает «ссылка 🎵 оригинальный звук - …»), вся строка больше не трактуется как URL.
- **Graceful shutdown:** после SIGTERM новые запросы отклоняются, активная загрузка останавливается, рабочие потоки получают до 10 с на завершение (ранее процесс обрывал их сразу).

### Сборка и зависимости
- Зависимости закреплены версиями, проверенными в работе: pyTelegramBotAPI 4.37.1, requests 2.34.2, beautifulsoup4 4.15.0, lxml 6.1.3, python-dotenv 1.2.4, yt-dlp 2026.10.26 (`requirements.txt`, `requirements-phone.txt`).
- GitHub Actions закреплены по SHA: `actions/checkout` v4, `actions/setup-python` v5.
- `Dockerfile`: `python:3.12-slim` закреплён по digest (обновлять осознанно вместе с зависимостями).

### Тесты
- 127 тестов (было 69): пути и миграция состояния, атомарная запись, DNS-фильтр SSRF, контейнеры, извлечение URL, дедлайн, graceful shutdown.
- В `conftest.py` тестам запрещена сеть: `main.py` создаёт `TeleBot` при импорте, и обработчик без подмены бота уходил бы к Telegram API.

## v0.4.2 — Безопасность (2026-11-11)

### Исправления
- `is_safe_video_url` отклоняет приватные, loopback- и link-local адреса в `video_url` (SSRF): литеральные IP, компактные IPv4-формы (`127.1`, hex/decimal), `localhost` и `*.localhost`; DNS-имена по-прежнему не резолвятся.
- Скачивание проходит редиректы вручную (до 2 переходов): каждый URL проверяется тем же фильтром — редирект больше не уводит загрузку на внутренний адрес.
- `rate_limit`: ответ о превышении лимита отправляется после выхода из глобального лока — деградация сети больше не блокирует остальные обработчики.
- Отсутствующий `author` в метаданных видео больше не роняет отправку (`main.py`).
- `install.sh`: токен бота вводится скрыто (`read -s`) и подставляется в `.env` без попадания в argv процесса (`sed` заменён на python, читающий `os.environ`).

## v0.4.1 — Исправление CI (2026-09-13)

### Исправления
- Тестовый Telegram-токен приведён к валидному формату для проверки `pyTelegramBotAPI` при импортировании `main.py`.

## v0.4 — Whitelist и устойчивый TikTok (2026-09-13)

### Новое
- Постоянный whitelist пользователей с закрытым `ADMIN_USER_ID` в `.env` и командами администратора: `/access add`, `/access remove`, `/access list`.
- В `/access list` выводятся Telegram ID и `@username`; при отсутствии username — имя или ID.

### Исправления
- TikTok: `yt-dlp` стал основным обработчиком; добавлены browser impersonation (`curl-cffi`) и cookies/headers для доступа к CDN.
- Прямое скачивание использует настроенный `DOWNLOAD_TIMEOUT`.

## v0.3 — Аудит и надёжность (2026-09-05)

### Исправления
- **yt-dlp: видео без звука.** Старый формат `bestvideo+bestaudio` давал split-DASH потоки, из которых бот скачивал только видео. Теперь используется одиночный muxed-формат (`b` + `format_sort`).
- **URL-матчинг по hostname** вместо поиска подстроки: `notvk.com/video` больше не принимается за VK, `evil.com/?url=tiktok.com` — за TikTok. Единый реестр доменов `SERVICE_DOMAINS` в `src/utils.py`.
- Ссылки без схемы (`tiktok.com/...`) нормализуются к `https://`.
- `video_url` от сторонних API проверяется на схему http/https (`is_safe_video_url`).
- Сообщения без текста (фото, стикеры) больше не роняют обработчик.
- Статус-сообщения редактируются через `safe_edit` — удалённое/устаревшее сообщение не вызывает исключение.
- `install.sh`: фиксы macOS (`OS_ID` unbound), зависимости переустанавливаются при обновлении, ошибки `git pull` показываются, защита `read` от EOF.
- `install.ps1`: проверка кодов выхода git/venv/pip, UTF-8 без BOM для `.env`, работа без `Activate.ps1` (Restricted policy), `Pop-Location` в `finally`.

### Новое
- GitHub Actions CI: ruff + pytest на Python 3.11/3.12.
- Ruff-линт всей кодовой базы (E, F, W, I, UP, B), конфиг в `pyproject.toml`.
- Dev-зависимости вынесены в `requirements-dev.txt`.
- Чистка протухших rate-limit записей — `rate_limit.json` больше не растёт бесконечно.
- Команда `/help`.
- Graceful shutdown по SIGTERM (`docker stop` завершается штатно).
- Docker: `.dockerignore` (токен больше не попадает в образ), non-root пользователь, `PYTHONUNBUFFERED=1`.
- `.gitattributes` (LF/CRLF по типам файлов), LICENSE (MIT), `__version__` в `src/__init__.py`.

### Удалено
- Легаси-монолит `tiktok_bot_advanced.py` (дублировал `src/` с версии v0.2).

## v0.2 — Multi-service
- Поддержка Instagram, YouTube, Twitter/X, Reddit, Facebook, Pinterest, Vimeo, VK
- Универсальный скачиватель на `yt-dlp` (~1500 сайтов)
- Модульная архитектура `src/downloaders/`
- Валидация URL для всех поддерживаемых платформ

## v0.1 — Initial
- Скачивание TikTok через 3 API с fallback
- Rate limit, контроль доступа, Docker, systemd
- Автоустановка одной командой
