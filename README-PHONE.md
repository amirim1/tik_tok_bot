# Зеркало телефона: что где лежит

Эта папка - локальная копия репозитория `amirim1/tik_tok_bot` для проекта, который
**физически выполняется на телефоне ruby** (Redmi Note 12 Pro 5G, LineageOS 21, Termux).

## Полная карта телефона (Termux, $HOME)

| Путь | Что это |
|---|---|
| `~/bot/bot.py` | дом-пульт бот (v6.4) - репа на ноуте: `Desktop\phone-home-bot` |
| `~/bot/devices.json` | реестр устройств пульта (создаётся ботом, в git не входит) |
| `~/bot/token.txt` | токен пульта (секрет, в git не входит) |
| `~/bot/down_key` | ssh-ключ для /down /scr /cmd /lock на основной ПК (секрет) |
| `~/bot/bot.py.v*.bak` | бэкапы версий пульта |
| `~/tik_tok_bot/` | этот репозиторий + локальные `.env`, `allowed_users.json` |
| `~/watchdog.sh` (v3) | охранник обоих ботов: `pgrep -f` по каждому, рестарт через 30 с |
| `~/.termux/boot/` | автостарт watchdog при перезагрузке телефона (Termux:Boot) |
| `~/llm/` | модели Qwen 1.7B/4B (нейронка выключена, файлы оставлены) |
| `~/bot.log`, `~/tiktok.log`, `~/watchdog.log` | логи обоих ботов и охранника |

## Деплой-специфика телефона

- Python 3.14 (Termux). Зависимости: `pyTelegramBotAPI`, `beautifulsoup4`, `yt-dlp`,
  `requests`, `python-dotenv` (pip) + `python-lxml`, `ffmpeg` (pkg). 
- **curl-cffi НЕ установлен** - в коде он не импортируется; TikTok работает через
  собственный API-даунлоадер (requests). Если какой-то сайт потребует имперсонацию
  браузера через yt-dlp - это единственный сценарий, когда он понадобится.
- Происхождение: нода `amirim.space` (systemd `tik-tok-bot.service`) - сервис там
  **остановлен и отключён от автостарта**. Откат:
  `ssh root@amirim.space "systemctl enable --now tik-tok-bot"`.
- Доступ ноутбука к телефону: `adb connect 192.168.1.231:<порт>` (порт плавает -
  смотреть в «Отладка по Wi-Fi» на телефоне), сопряжение уже выполнено.

## Как обновить код бота на телефоне

```bash
# 1) на ноутбуке: внести правки в эту репу и запушить
# 2) упаковать без секретов и мусора
tar czf ttb.tar.gz --exclude='.git' --exclude='venv' --exclude='__pycache__' \
    --exclude='bot.log' --exclude='.env' --exclude='allowed_users.json' tik_tok_bot
# 3) на телефон (adb, MSYS_NO_PATHCONV=1 в Git Bash)
adb push ttb.tar.gz /data/local/tmp/
adb shell run-as com.termux tar -C /data/data/com.termux/files/home \
    -xzf /data/local/tmp/ttb.tar.gz
# 4) рестарт (watchdog поднимет за 30 с)
adb shell run-as com.termux pgrep -f tik_tok_bot/main.py   # получить PID
adb shell run-as com.termux kill -9 <PID>
```

`.env`, `allowed_users.json`, `rate_limit.json` на телефоне не перезаписываются -
они один раз завезены с ноды и живут своей жизнью.
