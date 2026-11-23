import logging
import os
import shutil
from pathlib import Path

from dotenv import load_dotenv

# Каталог проекта (рядом с main.py): файлы состояния больше не зависят от cwd запуска.
BASE_DIR = Path(__file__).resolve().parent.parent


def _state_path(env_name: str, default_name: str) -> Path:
    """Путь файла состояния. Переменная окружения приоритетна; относительный путь
    (в т.ч. из .env) считается от каталога проекта, абсолютный берётся как есть."""
    value = os.getenv(env_name)
    path = Path(value) if value else Path(default_name)
    return path if path.is_absolute() else BASE_DIR / path


load_dotenv(override=True)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = _state_path("LOG_FILE", "bot.log")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
# pyTelegramBotAPI вешает на свой логгер отдельный StreamHandler в stderr поверх
# нашего root-хендлера: каждая ошибка поллинга попадала в лог дважды (в Termux
# stdout и stderr перенаправлены в один файл). Оставляем только root-хендлеры.
for _handler in logging.getLogger("TeleBot").handlers[:]:
    logging.getLogger("TeleBot").removeHandler(_handler)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN or TOKEN == "your_bot_token_here":
    logger.error("TELEGRAM_BOT_TOKEN not set!")
    exit(1)

TEMP_DIR = _state_path("TEMP_DIR", "temp_videos")
TEMP_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

RATE_LIMIT_CALLS = int(os.getenv("RATE_LIMIT_CALLS", "5"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
RATE_LIMIT_FILE = _state_path("RATE_LIMIT_FILE", "rate_limit.json")

ALLOWED_USERS_RAW = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS = [int(x.strip()) for x in ALLOWED_USERS_RAW.split(",") if x.strip()] if ALLOWED_USERS_RAW else []

ADMIN_USER_ID_RAW = os.getenv("ADMIN_USER_ID", "").strip()
if not ADMIN_USER_ID_RAW.isdigit():
    logger.error("ADMIN_USER_ID must be set to a numeric Telegram user ID")
    exit(1)
ADMIN_USER_ID = int(ADMIN_USER_ID_RAW)

ALLOWED_USERS_FILE = _state_path("ALLOWED_USERS_FILE", "allowed_users.json")

DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "30"))
MAX_DOWNLOAD_RETRIES = int(os.getenv("MAX_DOWNLOAD_RETRIES", "2"))
def migrate_legacy_state() -> int:
    """До v0.4.3 файлы состояния лежали в cwd запуска, а не в каталоге проекта
    (на Termux - в $HOME). Копируем их в новое место, старые не трогаем.
    Только для путей по умолчанию: явная переменная окружения - выбор владельца."""
    migrated = 0
    for env_name, default_name in (
        ("RATE_LIMIT_FILE", "rate_limit.json"),
        ("ALLOWED_USERS_FILE", "allowed_users.json"),
    ):
        if os.getenv(env_name):
            continue
        new_path = BASE_DIR / default_name
        old_path = Path.cwd() / default_name
        if new_path == old_path or new_path.exists() or not old_path.is_file():
            continue
        try:
            shutil.copy2(old_path, new_path)
        except OSError as e:
            logger.error(f"Failed to migrate {old_path} to {new_path}: {e}")
            continue
        migrated += 1
        logger.info(f"State file migrated: {old_path} -> {new_path}")
    return migrated


migrate_legacy_state()
