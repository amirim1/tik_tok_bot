import pytest
from src.downloaders import get_downloader, detect_service, SERVICE_DOWNLOADERS
from src.downloaders.base import BaseDownloader
from src.downloaders.tiktok import TikTokDownloader
from src.downloaders.ytdlp import YtDlpDownloader


class TestDetectService:
    def test_tiktok(self):
        assert detect_service("https://www.tiktok.com/@u/video/123") == "tiktok"
        assert detect_service("https://vm.tiktok.com/abc") == "tiktok"

    def test_instagram(self):
        assert detect_service("https://www.instagram.com/p/ABC/") == "instagram"

    def test_youtube(self):
        assert detect_service("https://youtube.com/watch?v=abc") == "youtube"

    def test_twitter(self):
        assert detect_service("https://twitter.com/u/status/123") == "twitter"

    def test_reddit(self):
        assert detect_service("https://reddit.com/r/videos/comments/abc/") == "reddit"

    def test_facebook(self):
        assert detect_service("https://fb.watch/abc/") == "facebook"

    def test_pinterest(self):
        assert detect_service("https://pin.it/abc") == "pinterest"

    def test_vimeo(self):
        assert detect_service("https://vimeo.com/123") == "vimeo"

    def test_vk(self):
        assert detect_service("https://vk.com/video-123_456") == "vk"

    def test_unknown(self):
        assert detect_service("https://example.com/video") is None


class TestGetDownloader:
    def test_tiktok(self):
        d, name = get_downloader("https://www.tiktok.com/@u/video/123")
        assert name == "tiktok"
        assert isinstance(d, TikTokDownloader)

    def test_instagram(self):
        d, name = get_downloader("https://www.instagram.com/p/ABC/")
        assert name == "instagram"
        assert isinstance(d, YtDlpDownloader)

    def test_youtube(self):
        d, name = get_downloader("https://youtube.com/watch?v=abc")
        assert name == "youtube"
        assert isinstance(d, YtDlpDownloader)

    def test_unsupported(self):
        d, name = get_downloader("https://example.com")
        assert d is None
        assert name is None


class TestDownloaderBase:
    def test_all_are_base(self):
        for name, downloader, patterns in SERVICE_DOWNLOADERS:
            assert isinstance(downloader, BaseDownloader), f"{name} is not BaseDownloader"

    def test_tiktok_has_apis(self):
        d = TikTokDownloader()
        assert len(d.apis) >= 2
        assert callable(d.apis[0])

    def test_close_all(self):
        from src.downloaders import close_all
        close_all()


class TestYtDlpDownloader:
    def test_init(self):
        d = YtDlpDownloader()
        assert d._opts is not None
