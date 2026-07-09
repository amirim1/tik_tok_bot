import pytest
from src.downloader import TikTokDownloader


class TestTikTokDownloader:
    def test_init(self):
        d = TikTokDownloader(max_retries=3)
        assert d.max_retries == 3
        assert len(d.apis) == 3
        d.close()

    @pytest.mark.slow
    def test_tiklydown_live(self):
        d = TikTokDownloader()
        result = d._api_tiklydown("https://www.tiktok.com/@user/video/1234567890123456789")
        assert result is None or "video_url" in result
        d.close()
