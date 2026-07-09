import os
from pathlib import Path


class TestConfigDefaults:
    def test_env_example_exists(self):
        assert Path(".env.example").exists()

    def test_requirements_exist(self):
        assert Path("requirements.txt").exists()

    def test_dockerfile_exists(self):
        assert Path("Dockerfile").exists()

    def test_env_example_has_token(self):
        content = Path(".env.example").read_text()
        assert "TELEGRAM_BOT_TOKEN" in content
