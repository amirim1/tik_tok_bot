import socket

import pytest

import src.utils as utils
from src.utils import (
    check_access,
    detect_video_container,
    extract_hostname,
    extract_url,
    grant_access,
    is_admin,
    is_safe_video_url,
    is_valid_mp4,
    list_allowed_users,
    match_service,
    revoke_access,
    validate_url,
)


class TestValidateUrl:
    def test_valid_tiktok_www(self):
        assert validate_url("https://www.tiktok.com/@user/video/1234567890123456789")

    def test_valid_tiktok_vm(self):
        assert validate_url("https://vm.tiktok.com/ZMJxw5p3D/")

    def test_valid_tiktok_vt(self):
        assert validate_url("https://vt.tiktok.com/ZSdjx4HkR/")

    def test_valid_tiktok_mobile(self):
        assert validate_url("https://m.tiktok.com/v/123456789")

    def test_valid_tiktok_no_www(self):
        assert validate_url("https://tiktok.com/@user/video/1234567890123456789")

    def test_valid_instagram(self):
        assert validate_url("https://www.instagram.com/p/ABC123/")
        assert validate_url("https://instagram.com/reel/XYZ789/")
        assert validate_url("https://instagr.am/p/DEF456/")

    def test_valid_youtube(self):
        assert validate_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert validate_url("https://youtu.be/dQw4w9WgXcQ")
        assert validate_url("https://youtube.com/shorts/abc123")

    def test_valid_twitter(self):
        assert validate_url("https://twitter.com/user/status/123456789")
        assert validate_url("https://x.com/user/status/123456789")

    def test_valid_reddit(self):
        assert validate_url("https://www.reddit.com/r/videos/comments/abc123/")
        assert validate_url("https://redd.it/abc123")

    def test_valid_facebook(self):
        assert validate_url("https://www.facebook.com/user/videos/123456789/")
        assert validate_url("https://fb.watch/abc123/")

    def test_valid_pinterest(self):
        assert validate_url("https://www.pinterest.com/pin/123456789/")
        assert validate_url("https://pin.it/abc123")

    def test_valid_vimeo(self):
        assert validate_url("https://vimeo.com/123456789")

    def test_valid_vk(self):
        assert validate_url("https://vk.com/video-123456_789")

    def test_invalid_youtube(self):
        assert not validate_url("youtube")

    def test_invalid_random(self):
        assert not validate_url("not a url at all")

    def test_invalid_empty(self):
        assert not validate_url("")

    def test_no_substring_false_positive(self):
        # Домен должен совпадать по hostname, а не по подстроке в URL
        assert not validate_url("https://evil.com/?url=https://tiktok.com/@a/video/1")
        assert not validate_url("https://notvk.com/video123")
        assert not validate_url("https://tiktok.com.evil.com/video")

    def test_schemeless_url(self):
        assert validate_url("tiktok.com/@user/video/1234567890123456789")
        assert validate_url("youtu.be/dQw4w9WgXcQ")

    def test_hostname_must_be_str(self):
        assert not validate_url(None)
        assert not validate_url("")

    def test_match_service_names(self):
        assert match_service("https://www.tiktok.com/@u/video/1") == "tiktok"
        assert match_service("https://x.com/u/status/1") == "twitter"
        assert match_service("https://fb.watch/abc") == "facebook"
        assert match_service("https://example.com") is None

    def test_extract_hostname(self):
        assert extract_hostname("https://WWW.TikTok.com/@u/video/1") == "www.tiktok.com"
        assert extract_hostname("tiktok.com/@u/video/1") == "tiktok.com"
        assert extract_hostname("https://") is None
        assert extract_hostname(None) is None


class TestIsSafeVideoUrl:
    @pytest.fixture(autouse=True)
    def stub_resolver(self, monkeypatch):
        # Тесты не зависят от DNS: по умолчанию имя резолвится в публичный адрес.
        self.resolved = ["93.184.216.34"]
        monkeypatch.setattr(utils, "_resolve_host", lambda host: list(self.resolved))

    def test_https(self):
        assert is_safe_video_url("https://cdn.example.com/video.mp4")

    def test_http(self):
        assert is_safe_video_url("http://cdn.example.com/video.mp4")

    def test_other_schemes_blocked(self):
        assert not is_safe_video_url("file:///etc/passwd")
        assert not is_safe_video_url("ftp://example.com/video.mp4")
        assert not is_safe_video_url("data:text/html,hi")

    def test_private_addresses_blocked(self):
        assert not is_safe_video_url("http://192.168.1.1/x.mp4")
        assert not is_safe_video_url("http://127.0.0.1/x.mp4")
        assert not is_safe_video_url("http://169.254.1.1/x.mp4")

    def test_public_domain_allowed(self):
        assert is_safe_video_url("https://cdn.example.com/x.mp4")

    def test_localhost_blocked(self):
        assert not is_safe_video_url("http://localhost/x.mp4")
        assert not is_safe_video_url("http://LocalHost/x.mp4")

    def test_compact_ipv4_and_trailing_dot_blocked(self):
        assert not is_safe_video_url("http://127.1/x.mp4")
        assert not is_safe_video_url("http://2130706433/x.mp4")
        assert not is_safe_video_url("http://0x7f000001/x.mp4")
        assert not is_safe_video_url("http://192.168.1.1./x.mp4")

    def test_domain_resolving_to_private_address_blocked(self):
        self.resolved = ["93.184.216.34", "10.0.0.5"]
        assert not is_safe_video_url("https://cdn.example.com/video.mp4")

    def test_domain_resolving_to_link_local_ipv6_blocked(self):
        self.resolved = ["2606:2800:220:1:248:1893:25c8:1946", "fe80::1"]
        assert not is_safe_video_url("https://cdn.example.com/video.mp4")

    def test_unresolvable_host_blocked(self, monkeypatch):
        def fail(host):
            raise socket.gaierror(11001, "getaddrinfo failed")

        monkeypatch.setattr(utils, "_resolve_host", fail)
        assert not is_safe_video_url("https://no-such-host.invalid/video.mp4")

    def test_domain_without_addresses_blocked(self):
        self.resolved = []
        assert not is_safe_video_url("https://cdn.example.com/video.mp4")

    def test_ipv6_literals_blocked(self):
        assert not is_safe_video_url("http://[::1]/x.mp4")
        assert not is_safe_video_url("http://[fe80::1]/x.mp4")
        assert not is_safe_video_url("http://[fc00::1]/x.mp4")

    def test_ipv4_mapped_ipv6_blocked(self):
        assert not is_safe_video_url("http://[::ffff:127.0.0.1]/x.mp4")
        assert not is_safe_video_url("http://[::ffff:192.168.1.1]/x.mp4")
        assert is_safe_video_url("http://[::ffff:8.8.8.8]/x.mp4")

    def test_reserved_and_multicast_blocked(self):
        assert not is_safe_video_url("http://0.0.0.0/x.mp4")
        assert not is_safe_video_url("http://224.0.0.1/x.mp4")
        assert not is_safe_video_url("http://240.0.0.1/x.mp4")

    def test_invalid_values(self):
        assert not is_safe_video_url(None)
        assert not is_safe_video_url("")
        assert not is_safe_video_url("https://")
        assert not is_safe_video_url(12345)


class TestIsValidMp4:
    def test_valid_mp4_header(self, tmp_path):
        f = tmp_path / "test.mp4"
        f.write_bytes(b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00')
        assert is_valid_mp4(f)

    def test_invalid_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("not a video")
        assert not is_valid_mp4(f)

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.mp4"
        f.write_bytes(b'')
        assert not is_valid_mp4(f)


class TestDetectVideoContainer:
    def test_mp4(self, tmp_path):
        f = tmp_path / "a.mp4"
        f.write_bytes(b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00')
        assert detect_video_container(f) == "mp4"
        assert is_valid_mp4(f)

    def test_webm(self, tmp_path):
        f = tmp_path / "a.webm"
        f.write_bytes(b'\x1aE\xdf\xa3\x00\x00\x00\x1fB\x86\x81\x01B\xf7\x81\x01B\xf2\x81\x04B\xf3\x81\x08B\x82webm')
        assert detect_video_container(f) == "webm"
        assert not is_valid_mp4(f)

    def test_mkv(self, tmp_path):
        f = tmp_path / "a.mkv"
        f.write_bytes(b'\x1aE\xdf\xa3\x00\x00\x00\x1fB\x86\x81\x01B\xf7\x81\x01B\xf2\x81\x04B\xf3\x81\x08B\x82matroska')
        assert detect_video_container(f) == "mkv"

    def test_not_video(self, tmp_path):
        f = tmp_path / "a.mp4"
        f.write_text("<html>blocked</html>")
        assert detect_video_container(f) is None


class TestExtractUrl:
    def test_url_with_caption(self):
        text = "https://www.tiktok.com/@user/video/123?is_from_webapp=1 🎵 оригинальный звук - author"
        assert extract_url(text) == "https://www.tiktok.com/@user/video/123?is_from_webapp=1"

    def test_caption_before_url(self):
        text = "Смотри: https://vt.tiktok.com/ZSdjx4HkR/"
        assert extract_url(text) == "https://vt.tiktok.com/ZSdjx4HkR/"

    def test_first_url_wins(self):
        text = "https://www.tiktok.com/@a/video/1 https://youtu.be/x"
        assert extract_url(text) == "https://www.tiktok.com/@a/video/1"

    def test_angle_brackets_and_trailing_punctuation(self):
        assert extract_url("<https://youtu.be/abc>.") == "https://youtu.be/abc"

    def test_bare_url(self):
        assert extract_url("  https://x.com/u/status/1\n") == "https://x.com/u/status/1"

    def test_no_url(self):
        assert extract_url("привет") is None
        assert extract_url("tiktok.com/@u/video/1") is None
        assert extract_url("") is None
        assert extract_url(None) is None


class TestCheckAccess:
    def test_admin_is_allowed(self, monkeypatch):
        monkeypatch.setattr("src.utils.ADMIN_USER_ID", 999)
        monkeypatch.setattr("src.utils._allowed_user_ids", {999})
        assert is_admin(999)
        assert check_access(999)

    def test_denies_user_not_on_whitelist(self, monkeypatch):
        monkeypatch.setattr("src.utils._allowed_user_ids", {999})
        assert not check_access(123)

    def test_grant_and_revoke_access(self, tmp_path, monkeypatch):
        monkeypatch.setattr("src.utils.ADMIN_USER_ID", 999)
        monkeypatch.setattr("src.utils.ALLOWED_USERS_FILE", str(tmp_path / "allowed_users.json"))
        monkeypatch.setattr("src.utils._allowed_user_ids", {999})

        assert grant_access(123)
        assert check_access(123)
        assert not grant_access(123)
        assert list_allowed_users() == [123, 999]
        assert revoke_access(123)
        assert not check_access(123)
        assert not revoke_access(999)
        assert check_access(999)
