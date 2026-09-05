from src.utils import (
    check_access,
    extract_hostname,
    is_safe_video_url,
    is_valid_mp4,
    match_service,
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
    def test_https(self):
        assert is_safe_video_url("https://cdn.example.com/video.mp4")

    def test_http(self):
        assert is_safe_video_url("http://cdn.example.com/video.mp4")

    def test_other_schemes_blocked(self):
        assert not is_safe_video_url("file:///etc/passwd")
        assert not is_safe_video_url("ftp://example.com/video.mp4")
        assert not is_safe_video_url("data:text/html,hi")

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


class TestCheckAccess:
    def test_no_restrictions(self, monkeypatch):
        monkeypatch.setattr("src.utils.ALLOWED_USERS", [])
        assert check_access(123)

    def test_allowed_user(self, monkeypatch):
        monkeypatch.setattr("src.utils.ALLOWED_USERS", [123, 456])
        assert check_access(123)

    def test_denied_user(self, monkeypatch):
        monkeypatch.setattr("src.utils.ALLOWED_USERS", [123, 456])
        assert not check_access(789)
