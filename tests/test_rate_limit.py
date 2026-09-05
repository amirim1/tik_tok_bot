import json
import time

import pytest

import src.utils as utils
from src.utils import rate_limit
import src.utils as utils


class FakeMessage:
    def __init__(self, user_id):
        self.from_user = type("U", (), {"id": user_id})()
        self.text = "https://tiktok.com/@u/video/1"


class FakeBot:
    def __init__(self):
        self.replies = []

    def reply_to(self, message, text):
        self.replies.append(text)


@pytest.fixture(autouse=True)
def clean_state(tmp_path, monkeypatch):
    monkeypatch.setattr(utils, "_user_requests", {})
    monkeypatch.setattr(utils, "RATE_LIMIT_FILE", str(tmp_path / "rl.json"))
    utils._user_requests.clear()
    yield
    utils._user_requests.clear()


@pytest.fixture
def limited_handler():
    bot = FakeBot()

    @rate_limit(bot, max_calls=3, time_window=60)
    def handler(message):
        return "handled"

    return bot, handler


def test_allows_within_limit(limited_handler):
    bot, handler = limited_handler
    msg = FakeMessage(1)
    for _ in range(3):
        assert handler(msg) == "handled"
    assert bot.replies == []


def test_blocks_over_limit(limited_handler):
    bot, handler = limited_handler
    msg = FakeMessage(1)
    for _ in range(3):
        handler(msg)
    assert handler(msg) is None
    assert len(bot.replies) == 1
    assert "лимит" in bot.replies[0]


def test_limits_are_per_user(limited_handler):
    bot, handler = limited_handler
    for _ in range(3):
        handler(FakeMessage(1))
    assert handler(FakeMessage(2)) == "handled"


def test_old_entries_expire(limited_handler):
    bot, handler = limited_handler
    msg = FakeMessage(1)
    for _ in range(3):
        handler(msg)
    # Сдвигаем время так, будто окно прошло
    utils._user_requests["1"] = [t - 120 for t in utils._user_requests["1"]]
    assert handler(msg) == "handled"
    assert bot.replies == []


def test_stale_users_pruned(limited_handler):
    bot, handler = limited_handler
    handler(FakeMessage(1))
    # Протухший пользователь из персистентности
    utils._user_requests["999"] = [time.time() - 3600]
    handler(FakeMessage(2))
    assert "999" not in utils._user_requests


def test_persists_to_file(limited_handler, tmp_path):
    bot, handler = limited_handler
    handler(FakeMessage(7))
    rl_file = tmp_path / "rl.json"
    data = json.loads(rl_file.read_text())
    assert "7" in data
    assert len(data["7"]) == 1
