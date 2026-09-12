import json
import logging
import threading
import time
from functools import wraps
from pathlib import Path
from urllib.parse import urlparse

from src.config import (
    ADMIN_USER_ID,
    ALLOWED_USERS,
    ALLOWED_USERS_FILE,
    RATE_LIMIT_CALLS,
    RATE_LIMIT_FILE,
    RATE_LIMIT_WINDOW,
    TEMP_DIR,
)

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_user_requests = {}
_access_lock = threading.Lock()


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


def _default_allowed_users() -> set[int]:
    """Начальный whitelist: администратор и ID из переменной окружения."""
    return {ADMIN_USER_ID, *ALLOWED_USERS}


def _load_allowed_users() -> set[int]:
    path = Path(ALLOWED_USERS_FILE)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _default_allowed_users()
    except (OSError, json.JSONDecodeError) as e:
        logger.error(f"Failed to load access whitelist: {e}")
        return _default_allowed_users()

    if not isinstance(data, list):
        logger.error("Access whitelist must contain a JSON list of Telegram user IDs")
        return _default_allowed_users()

    users = {item for item in data if isinstance(item, int) and not isinstance(item, bool)}
    return users | {ADMIN_USER_ID}


def _save_allowed_users(users: set[int]) -> None:
    path = Path(ALLOWED_USERS_FILE)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path.write_text(json.dumps(sorted(users), indent=2), encoding="utf-8")
        temp_path.replace(path)
    except OSError as e:
        logger.error(f"Failed to save access whitelist: {e}")
        temp_path.unlink(missing_ok=True)
        raise


_allowed_user_ids = _load_allowed_users()


def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_USER_ID


def list_allowed_users() -> list[int]:
    with _access_lock:
        return sorted(_allowed_user_ids)


def grant_access(user_id: int) -> bool:
    """Добавляет пользователя в whitelist. Возвращает False, если он уже есть."""
    with _access_lock:
        if user_id in _allowed_user_ids:
            return False
        _allowed_user_ids.add(user_id)
        _save_allowed_users(_allowed_user_ids)
        return True


def revoke_access(user_id: int) -> bool:
    """Удаляет пользователя из whitelist, но никогда не удаляет администратора."""
    if is_admin(user_id):
        return False
    with _access_lock:
        if user_id not in _allowed_user_ids:
            return False
        _allowed_user_ids.remove(user_id)
        _save_allowed_users(_allowed_user_ids)
        return True


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
    with _access_lock:
        return user_id in _allowed_user_ids


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
