import logging
import time

import requests
from bs4 import BeautifulSoup

from src.config import DOWNLOAD_TIMEOUT, MAX_DOWNLOAD_RETRIES
from src.downloaders.base import BaseDownloader
from src.downloaders.ytdlp import YtDlpDownloader

logger = logging.getLogger(__name__)


class TikTokDownloader(BaseDownloader):
    def __init__(self, max_retries: int = None):
        self.max_retries = MAX_DOWNLOAD_RETRIES if max_retries is None else max_retries
        self.apis = [
            self._api_tiklydown,
            self._api_tikwm,
            self._api_snaptik,
        ]
        self._ytdlp = YtDlpDownloader()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )
        })

    def _api_tiklydown(self, url: str) -> dict | None:
        try:
            r = self.session.get(
                "https://api.tiklydown.eu.org/api/download",
                params={"url": url},
                timeout=DOWNLOAD_TIMEOUT
            )
            r.raise_for_status()
            data = r.json()
            if data.get("videoUrl"):
                return {
                    "video_url": data["videoUrl"],
                    "author": data.get("author", {}).get("nickname", "Unknown"),
                    "description": data.get("desc", ""),
                }
        except Exception as e:
            logger.warning(f"tiklydown failed: {e}")
        return None

    def _api_tikwm(self, url: str) -> dict | None:
        try:
            r = self.session.get(
                "https://www.tikwm.com/api/",
                params={"url": url, "hd": 1},
                timeout=DOWNLOAD_TIMEOUT
            )
            r.raise_for_status()
            data = r.json()
            d = data.get("data", {})
            if d.get("play"):
                return {
                    "video_url": d["play"],
                    "author": d.get("author", {}).get("unique_id", "Unknown"),
                    "description": d.get("title", ""),
                }
        except Exception as e:
            logger.warning(f"tikwm failed: {e}")
        return None

    def _api_snaptik(self, url: str) -> dict | None:
        try:
            r = self.session.post(
                "https://snaptik.app/abc2.php",
                data={"url": url},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=DOWNLOAD_TIMEOUT
            )
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'lxml')
            selectors = [
                'a[href*="snaptik.app/dle-"]',
                '.download-link a',
                'a.btn-success',
                'a[download]',
                'a.btn-primary',
            ]
            link = None
            for sel in selectors:
                link = soup.select_one(sel)
                if link and link.get('href'):
                    break
            if link and link.get('href'):
                author_el = soup.select_one('.video-author, .author-name, .username')
                desc_el = soup.select_one('.video-description, .description, .caption')
                return {
                    "video_url": link['href'],
                    "author": author_el.get_text(strip=True) if author_el else "Unknown",
                    "description": desc_el.get_text(strip=True) if desc_el else "",
                }
        except Exception as e:
            logger.warning(f"snaptik failed: {e}")
        return None

    def get_video(self, url: str) -> dict | None:
        # TikTok's web/API endpoints change frequently. yt-dlp is the primary
        # path because it follows the redirect and handles the current browser
        # challenge when curl-cffi is installed.
        result = self._ytdlp.get_video(url)
        if result:
            logger.info("TikTok success via yt-dlp")
            return result

        logger.warning("yt-dlp failed, trying legacy TikTok APIs for: %s", url)
        for api_method in self.apis:
            for attempt in range(self.max_retries):
                try:
                    result = api_method(url)
                    if result:
                        logger.info(f"Success via {api_method.__name__}")
                        return result
                except Exception as e:
                    logger.error(f"{api_method.__name__} attempt {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(1)
            time.sleep(0.5)
        logger.warning(f"TikTok download failed via yt-dlp and legacy APIs: {url}")
        return None

    def close(self):
        self.session.close()
        self._ytdlp.close()
