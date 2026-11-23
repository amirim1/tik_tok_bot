import time

import pytest

import src.downloaders.tiktok as tiktok_module
import src.downloaders.ytdlp as ytdlp_module
from src.downloaders import SERVICE_DOWNLOADERS, detect_service, get_downloader
from src.downloaders.base import MIN_ATTEMPT_SECONDS, BaseDownloader, remaining_seconds
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

    def test_no_substring_false_positive(self):
        assert detect_service("https://evil.com/?u=https://vk.com/video-1_2") is None
        assert detect_service("https://myvimeo.com.evil.example/123") is None


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
        for name, downloader, _patterns in SERVICE_DOWNLOADERS:
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

    def test_format_is_single_muxed_stream(self):
        # Регрессия: split-формат (bestvideo+bestaudio) давал видео без звука,
        # т.к. бот скачивает один прямой URL.
        d = YtDlpDownloader()
        assert "+" not in d._opts["format"]
        assert "bestvideo" not in d._opts["format"]

    def test_format_respects_max_file_size(self):
        d = YtDlpDownloader()
        assert "filesize<" in d._opts["format"]

    def test_network_options_are_bounded(self):
        d = YtDlpDownloader()
        assert d._opts["socket_timeout"] > 0
        assert 0 <= d._opts["retries"] <= 5
        assert 0 <= d._opts["extractor_retries"] <= 5
        assert d._opts["merge_output_format"] == "mp4"


class TestGetVideoDeadline:
    def test_no_deadline(self):
        assert remaining_seconds(None) is None

    def test_remaining(self):
        now = time.monotonic()
        assert remaining_seconds(now + 60) <= 60

    def test_too_late_raises(self):
        with pytest.raises(TimeoutError):
            remaining_seconds(time.monotonic() + MIN_ATTEMPT_SECONDS - 2)

    def test_ytdlp_clips_socket_timeout_to_remaining(self, monkeypatch):
        seen = {}

        class FakeYDL:
            def __init__(self, opts):
                seen["opts"] = opts

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def extract_info(self, url, download=False):
                return None

        monkeypatch.setattr(ytdlp_module.yt_dlp, "YoutubeDL", FakeYDL)
        before = time.monotonic()
        assert YtDlpDownloader().get_video("https://x", deadline=before + 20) is None
        assert 0 < seen["opts"]["socket_timeout"] <= 20

    def test_ytdlp_does_not_start_when_deadline_passed(self, monkeypatch):
        def fail(*args, **kwargs):
            raise AssertionError("extract_info must not start")

        monkeypatch.setattr(ytdlp_module.yt_dlp, "YoutubeDL", fail)
        with pytest.raises(TimeoutError):
            YtDlpDownloader().get_video("https://x", deadline=time.monotonic() + 1)
        assert ytdlp_module.yt_dlp.YoutubeDL is fail

    def test_tiktok_passes_remaining_to_each_attempt(self, monkeypatch):
        d = TikTokDownloader()
        timeouts = []
        monkeypatch.setattr(d._ytdlp, "get_video", lambda url, deadline=None: None)
        monkeypatch.setattr(d, "apis", [lambda url, timeout=None: timeouts.append(timeout) and None])
        monkeypatch.setattr(d, "max_retries", 1)
        monkeypatch.setattr(tiktok_module.time, "sleep", lambda seconds: None)

        before = time.monotonic()
        assert d.get_video("https://x", deadline=before + 120) is None
        assert len(timeouts) == 1
        assert 0 < timeouts[0] <= 120

    def test_tiktok_does_not_start_attempt_when_deadline_passed(self, monkeypatch):
        d = TikTokDownloader()
        timeouts = []
        monkeypatch.setattr(d._ytdlp, "get_video", lambda url, deadline=None: None)
        monkeypatch.setattr(d, "apis", [lambda url, timeout=None: timeouts.append(timeout) and None])
        monkeypatch.setattr(tiktok_module.time, "sleep", lambda seconds: None)

        with pytest.raises(TimeoutError):
            d.get_video("https://x", deadline=time.monotonic() + 1)
        assert timeouts == []
