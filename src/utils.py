import time
import json
import re
import logging
import threading
from functools import wraps
from pathlib import Path

from src.config import (
    RATE_LIMIT_CALLS, RATE_LIMIT_WINDOW, RATE_LIMIT_FILE,
    TEMP_DIR, ALLOWED_USERS
)

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_user_requests = {}


def _load_requests() -> dict:
    try:
        with open(RATE_LIMIT_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_requests(data: dict):
    try:
        with open(RATE_LIMIT_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save rate limit data: {e}")


_user_requests.update(_load_requests())


def rate_limit(bot_instance, max_calls=None, time_window=None):
    if max_calls is None:
        max_calls = RATE_LIMIT_CALLS
    if time_window is None:
        time_window = RATE_LIMIT_WINDOW

    def decorator(func):
        @wraps(func)
        def wrapper(message, *args, **kwargs):
            user_id = str(message.from_user.id)
            now = time.time()

            with _lock:
                if user_id not in _user_requests:
                    _user_requests[user_id] = []
                _user_requests[user_id] = [
                    t for t in _user_requests[user_id] if now - t < time_window
                ]

                if len(_user_requests[user_id]) >= max_calls:
                    bot_instance.reply_to(
                        message,
                        f"Превышен лимит запросов. Попробуйте через {time_window} сек."
                    )
                    return

                _user_requests[user_id].append(now)
                _save_requests(_user_requests)

            return func(message, *args, **kwargs)
        return wrapper
    return decorator


URL_PATTERNS = {
    "tiktok": [
        r'https?://(?:www\.)?tiktok\.com/@[\w.-]+/video/\d+',
        r'https?://(?:vm|vt)\.tiktok\.com/[\w-]+',
        r'https?://(?:m\.)?tiktok\.com/v/\d+',
    ],
}

YTDLP_DOMAINS = [
    "instagram.com", "instagr.am",
    "youtube.com", "youtu.be",
    "twitter.com", "x.com",
    "reddit.com", "redd.it",
    "facebook.com", "fb.watch", "fb.com",
    "pinterest.com", "pin.it",
    "vimeo.com",
    "vk.com",
]


def validate_url(url: str) -> bool:
    for patterns in URL_PATTERNS.values():
        if any(re.match(p, url) for p in patterns):
            return True
    for domain in YTDLP_DOMAINS:
        if domain in url:
            return True
    return False


def check_access(user_id: int) -> bool:
    if not ALLOWED_USERS:
        return True
    return user_id in ALLOWED_USERS


def is_valid_mp4(file_path) -> bool:
    try:
        with open(file_path, 'rb') as f:
            header = f.read(12)
        return len(header) >= 12 and header[4:8] == b'ftyp'
    except Exception:
        return False


def cleanup_old_files(max_age_minutes: int = 5):
    try:
        now = time.time()
        cutoff = now - max_age_minutes * 60
        deleted = 0
        for fp in Path(TEMP_DIR).glob("video_*.mp4"):
            try:
                if fp.stat().st_mtime < cutoff:
                    fp.unlink()
                    deleted += 1
            except Exception as e:
                logger.error(f"Error deleting {fp}: {e}")
        if deleted:
            logger.info(f"Cleaned {deleted} old files")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")
