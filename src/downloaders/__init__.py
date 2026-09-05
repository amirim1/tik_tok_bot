import logging
from typing import Optional

from src.downloaders.base import BaseDownloader
from src.downloaders.tiktok import TikTokDownloader
from src.downloaders.ytdlp import YtDlpDownloader
from src.utils import SERVICE_DOMAINS, match_service

logger = logging.getLogger(__name__)

_tiktok = TikTokDownloader()
_ytdlp = YtDlpDownloader()

_DOWNLOADERS: dict[str, BaseDownloader] = {
    "tiktok": _tiktok,
    "instagram": _ytdlp,
    "youtube": _ytdlp,
    "twitter": _ytdlp,
    "reddit": _ytdlp,
    "facebook": _ytdlp,
    "pinterest": _ytdlp,
    "vimeo": _ytdlp,
    "vk": _ytdlp,
}

SERVICE_DOWNLOADERS: list[tuple[str, BaseDownloader, list[str]]] = [
    (name, _DOWNLOADERS[name], domains) for name, domains in SERVICE_DOMAINS.items()
]


def detect_service(url: str) -> Optional[str]:
    return match_service(url)


def get_downloader(url: str):
    name = match_service(url)
    if name:
        logger.info(f"Matched: {name}")
        return _DOWNLOADERS[name], name
    return None, None


def close_all():
    _tiktok.close()
    _ytdlp.close()
