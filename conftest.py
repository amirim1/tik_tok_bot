import os

# pyTelegramBotAPI validates the token shape during TeleBot construction.
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST_TOKEN_FOR_PYTEST")
os.environ.setdefault("ADMIN_USER_ID", "1")
