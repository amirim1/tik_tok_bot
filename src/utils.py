import json
import logging
import threading
import time
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from src.config import ALLOWED_USERS, RATE_LIMIT_CALLS, RATE_LIMIT_FILE, RATE_LIMIT_WINDOW, TEMP_DIR

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_user_requests = {}


def _load_requests() -> dict:
    try:
        with open(RATE_LIMIT_FILE) as f:
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


def _prune_stale(now: float, window: int):
    """Удаляет протухшие записи всех пользователей, чтобы файл персистентности не рос бесконечно."""
    for uid in list(_user_requests):
        fresh = [t for t in _user_requests[uid] if now - t < window]
        if fresh:
            _user_requests[uid] = fresh
        else:
            del _user_requests[uid]


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
                _prune_stale(now, time_window)

                if len(_user_requests.get(user_id, [])) >= max_calls:
                    bot_instance.reply_to(
                        message,
                        f"Превышен лимит запросов. Попробуйте через {time_window} сек."
                    )
                    return

                _user_requests.setdefault(user_id, []).append(now)
                _save_requests(_user_requests)

            return func(message, *args, **kwargs)
        return wrapper
    return decorator


# Единый реестр поддерживаемых доменов. Совпадение проверяется по hostname:
# hostname == domain или hostname.endswith("." + domain) — точечное совпадение
# вместо поиска подстроки, чтобы "notvk.com/video" не считался vk-ссылкой.
SERVICE_DOMAINS: dict[str, list[str]] = {
    "tiktok": ["tiktok.com"],
    "instagram": ["instagram.com", "instagr.am"],
    "youtube": ["youtube.com", "youtu.be"],
    "twitter": ["twitter.com", "x.com"],
    "reddit": ["reddit.com", "redd.it"],
    "facebook": ["facebook.com", "fb.watch", "fb.com"],
    "pinterest": ["pinterest.com", "pin.it"],
    "vimeo": ["vimeo.com"],
    "vk": ["vk.com"],
}


def extract_hostname(url) -> str | None:
    """Hostname ссылки; ссылкам без схемы подставляется https://."""
    if not url or not isinstance(url, str):
        return None
    candidate = url.strip()
    if "://" not in candidate:
        candidate = "https://" + candidate
    try:
        hostname = urlparse(candidate).hostname
    except ValueError:
        return None
    return hostname.lower() if hostname else None


def match_service(url) -> str | None:
    """Имя сервиса по ссылке или None, если домен не поддерживается."""
    hostname = extract_hostname(url)
    if not hostname:
        return None
    for name, domains in SERVICE_DOMAINS.items():
        for d in domains:
            if hostname == d or hostname.endswith("." + d):
                return name
    return None


def validate_url(url: str) -> bool:
    return match_service(url) is not None


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


def is_safe_video_url(url) -> bool:
    """video_url приходит из сторонних API — разрешаем только прямые http(s)-ссылки."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


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
