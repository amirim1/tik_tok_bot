import logging
from typing import Optional

from src.downloaders.base import BaseDownloader
from src.downloaders.tiktok import TikTokDownloader
from src.downloaders.ytdlp import YtDlpDownloader

logger = logging.getLogger(__name__)

_tiktok = TikTokDownloader()
_ytdlp = YtDlpDownloader()

SERVICE_DOWNLOADERS: list[tuple[str, BaseDownloader, list[str]]] = [
    ("tiktok", _tiktok, ["tiktok.com/", "vm.tiktok.com/", "vt.tiktok.com/"]),
    ("instagram", _ytdlp, ["instagram.com/", "instagr.am/"]),
    ("youtube", _ytdlp, ["youtube.com/", "youtu.be/"]),
    ("twitter", _ytdlp, ["twitter.com/", "x.com/"]),
    ("reddit", _ytdlp, ["reddit.com/", "redd.it/"]),
    ("facebook", _ytdlp, ["facebook.com/", "fb.watch/", "fb.com/"]),
    ("pinterest", _ytdlp, ["pinterest.com/", "pin.it/"]),
    ("vimeo", _ytdlp, ["vimeo.com/"]),
    ("vk", _ytdlp, ["vk.com/video"]),
]


def detect_service(url: str) -> Optional[str]:
    for name, _, patterns in SERVICE_DOWNLOADERS:
        for p in patterns:
            if p in url:
                return name
    return None


def get_downloader(url: str):
    for name, downloader, patterns in SERVICE_DOWNLOADERS:
        for p in patterns:
            if p in url:
                logger.info(f"Matched: {name}")
                return downloader, name
    return None, None


def close_all():
    _tiktok.close()
    _ytdlp.close()
