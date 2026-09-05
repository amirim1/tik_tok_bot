# Changelog

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
