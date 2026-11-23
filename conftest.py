import os
import socket

import pytest

# pyTelegramBotAPI validates the token shape during TeleBot construction.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST_TOKEN_FOR_PYTEST")
os.environ.setdefault("ADMIN_USER_ID", "1")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """Тесты не ходят в сеть. main.py создаёт TeleBot при импорте, и обработчик,
    вызванный без подмены бота, отправил бы запрос к Telegram API с тестовым токеном.
    """
    def blocked_connect(self, address, *args, **kwargs):
        raise OSError(f"network access is blocked in tests: {address}")

    monkeypatch.setattr(socket.socket, "connect", blocked_connect)
