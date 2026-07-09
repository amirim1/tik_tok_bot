import pytest
from src.utils import validate_tiktok_url, is_valid_mp4, check_access


class TestValidateTikTokUrl:
    def test_valid_www(self):
        assert validate_tiktok_url("https://www.tiktok.com/@user/video/1234567890123456789")

    def test_valid_vm(self):
        assert validate_tiktok_url("https://vm.tiktok.com/ZMJxw5p3D/")

    def test_valid_vt(self):
        assert validate_tiktok_url("https://vt.tiktok.com/ZSdjx4HkR/")

    def test_valid_mobile(self):
        assert validate_tiktok_url("https://m.tiktok.com/v/123456789")

    def test_valid_no_www(self):
        assert validate_tiktok_url("https://tiktok.com/@user/video/1234567890123456789")

    def test_invalid_youtube(self):
        assert not validate_tiktok_url("https://youtube.com/watch?v=123")

    def test_invalid_random(self):
        assert not validate_tiktok_url("not a url at all")

    def test_invalid_empty(self):
        assert not validate_tiktok_url("")


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
