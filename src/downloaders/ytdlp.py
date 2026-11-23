import logging

import yt_dlp

from src.config import DOWNLOAD_TIMEOUT, MAX_DOWNLOAD_RETRIES, MAX_FILE_SIZE
from src.downloaders.base import BaseDownloader, remaining_seconds

logger = logging.getLogger(__name__)


class YtDlpDownloader(BaseDownloader):
    def __init__(self):
        # Только одиночные (muxed) форматы: бот скачивает один прямой URL,
        # поэтому split-форматы (bestvideo+bestaudio) дали бы видео без звука.
        self._opts = {
            'format': f'b[filesize<{MAX_FILE_SIZE}]/b',
            'format_sort': ['proto:https', 'ext:mp4:m4a'],
            # Ограничиваем сетевые ожидания: без этого yt-dlp повторяет запрос
            # по умолчанию (10 retries, extractor_retries=3) без общего таймаута.
            'socket_timeout': DOWNLOAD_TIMEOUT,
            'retries': MAX_DOWNLOAD_RETRIES,
            'extractor_retries': MAX_DOWNLOAD_RETRIES,
            # Если yt-dlp пришлось склеивать потоки, результат - mp4, а не webm/mkv.
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'no_color': True,
        }

    def get_video(self, url: str, deadline: float | None = None) -> dict | None:
        # Сокет-таймаут не длиннее остатка до дедлайна: последняя попытка не
        # уходит за общий лимит. Общего таймаута на extract_info в yt-dlp нет.
        # Остаток считаем до try: TimeoutError не должен гаситься как ошибка yt-dlp.
        remaining = remaining_seconds(deadline)
        opts = dict(self._opts)
        if remaining is not None:
            opts['socket_timeout'] = min(DOWNLOAD_TIMEOUT, remaining)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)

            if not info:
                logger.warning(f"yt-dlp returned no info for: {url}")
                return None

            if info.get('url'):
                video_url = info['url']
            elif info.get('formats'):
                best = sorted(
                    [f for f in info['formats'] if f.get('url') and f.get('ext') in ('mp4', 'mov', 'webm', 'mkv')],
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
                # Some CDNs (notably TikTok) require the cookies and browser
                # headers collected during extraction to authorize the media URL.
                "http_headers": info.get('http_headers') or {},
                "cookies": {cookie.name: cookie.value for cookie in ydl.cookiejar},
            }

        except yt_dlp.utils.DownloadError as e:
            logger.warning(f"yt-dlp error for {url}: {e}")
        except Exception as e:
            logger.error(f"yt-dlp unexpected error: {e}", exc_info=True)
        return None

    def close(self):
        pass
