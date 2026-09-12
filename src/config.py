import logging
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(override=True)

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_FILE = os.getenv("LOG_FILE", "bot.log")

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TOKEN or TOKEN == "your_bot_token_here":
    logger.error("TELEGRAM_BOT_TOKEN not set!")
    exit(1)

TEMP_DIR = Path(os.getenv("TEMP_DIR", "temp_videos"))
TEMP_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

RATE_LIMIT_CALLS = int(os.getenv("RATE_LIMIT_CALLS", "5"))
RATE_LIMIT_WINDOW = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
RATE_LIMIT_FILE = os.getenv("RATE_LIMIT_FILE", "rate_limit.json")

ALLOWED_USERS_RAW = os.getenv("ALLOWED_USERS", "")
ALLOWED_USERS = [int(x.strip()) for x in ALLOWED_USERS_RAW.split(",") if x.strip()] if ALLOWED_USERS_RAW else []

ADMIN_USER_ID_RAW = os.getenv("ADMIN_USER_ID", "").strip()
if not ADMIN_USER_ID_RAW.isdigit():
    logger.error("ADMIN_USER_ID must be set to a numeric Telegram user ID")
    exit(1)
ADMIN_USER_ID = int(ADMIN_USER_ID_RAW)

ALLOWED_USERS_FILE = os.getenv("ALLOWED_USERS_FILE", "allowed_users.json")

DOWNLOAD_TIMEOUT = int(os.getenv("DOWNLOAD_TIMEOUT", "30"))
MAX_DOWNLOAD_RETRIES = int(os.getenv("MAX_DOWNLOAD_RETRIES", "2"))
