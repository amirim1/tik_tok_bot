import logging
from typing import Optional, Dict

import yt_dlp

from src.config import MAX_FILE_SIZE
from src.downloaders.base import BaseDownloader

logger = logging.getLogger(__name__)


class YtDlpDownloader(BaseDownloader):
    def __init__(self):
        self._opts = {
            'format': (
                f'bestvideo[filesize<{MAX_FILE_SIZE}]+bestaudio/'
                f'best[filesize<{MAX_FILE_SIZE}]/best'
            ),
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'no_color': True,
        }

    def get_video(self, url: str) -> Optional[Dict]:
        try:
            with yt_dlp.YoutubeDL(self._opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                logger.warning(f"yt-dlp returned no info for: {url}")
                return None

            if info.get('url'):
                video_url = info['url']
            elif info.get('requested_formats'):
                video_url = info['requested_formats'][0].get('url', info.get('url'))
            elif info.get('formats'):
                best = sorted(
                    [f for f in info['formats'] if f.get('url') and f.get('ext') in ('mp4', 'mov', 'webm')],
                    key=lambda f: -(f.get('filesize') or f.get('filesize_approx') or 0)
                )
                if best:
                    video_url = best[0]['url']
                else:
                    video_url = info['formats'][0]['url']
            else:
                logger.warning(f"No downloadable URL found for: {url}")
                return None

            return {
                "video_url": video_url,
                "author": info.get('uploader') or info.get('channel') or info.get('creator') or "Unknown",
                "description": info.get('description') or info.get('title') or "",
            }

        except yt_dlp.utils.DownloadError as e:
            logger.warning(f"yt-dlp error for {url}: {e}")
        except Exception as e:
            logger.error(f"yt-dlp unexpected error: {e}", exc_info=True)
        return None

    def close(self):
        pass
