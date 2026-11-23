import logging
from pathlib import Path

import src.config as config


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


class TestStatePaths:
    def test_base_dir_is_project_root(self):
        assert config.BASE_DIR == Path(config.__file__).resolve().parent.parent

    def test_default_is_relative_to_project(self, monkeypatch, tmp_path):
        monkeypatch.delenv("RATE_LIMIT_FILE", raising=False)
        monkeypatch.chdir(tmp_path)
        assert config._state_path("RATE_LIMIT_FILE", "rate_limit.json") == config.BASE_DIR / "rate_limit.json"

    def test_relative_env_is_relative_to_project(self, monkeypatch, tmp_path):
        monkeypatch.setenv("RATE_LIMIT_FILE", "state/rl.json")
        monkeypatch.chdir(tmp_path)
        assert config._state_path("RATE_LIMIT_FILE", "rate_limit.json") == config.BASE_DIR / "state" / "rl.json"

    def test_absolute_env_wins(self, tmp_path, monkeypatch):
        custom = tmp_path / "rl.json"
        monkeypatch.setenv("RATE_LIMIT_FILE", str(custom))
        assert config._state_path("RATE_LIMIT_FILE", "rate_limit.json") == custom

    def test_state_files_do_not_depend_on_cwd(self, monkeypatch, tmp_path):
        for name in ("LOG_FILE", "TEMP_DIR", "RATE_LIMIT_FILE", "ALLOWED_USERS_FILE"):
            monkeypatch.delenv(name, raising=False)
        monkeypatch.chdir(tmp_path)
        paths = [config._state_path("LOG_FILE", "bot.log"), config._state_path("TEMP_DIR", "temp_videos"),
                 config._state_path("RATE_LIMIT_FILE", "rate_limit.json"),
                 config._state_path("ALLOWED_USERS_FILE", "allowed_users.json")]
        assert all(p.is_absolute() and p.is_relative_to(config.BASE_DIR) for p in paths)


class TestMigrateLegacyState:
    def test_copies_files_from_cwd(self, monkeypatch, tmp_path):
        project, home = tmp_path / "proj", tmp_path / "home"
        project.mkdir()
        home.mkdir()
        (home / "rate_limit.json").write_text('{"1": [1]}', encoding="utf-8")
        (home / "allowed_users.json").write_text("[1]", encoding="utf-8")
        monkeypatch.setattr(config, "BASE_DIR", project)
        monkeypatch.chdir(home)
        monkeypatch.delenv("RATE_LIMIT_FILE", raising=False)
        monkeypatch.delenv("ALLOWED_USERS_FILE", raising=False)

        assert config.migrate_legacy_state() == 2
        assert (project / "rate_limit.json").read_text(encoding="utf-8") == '{"1": [1]}'
        assert (project / "allowed_users.json").read_text(encoding="utf-8") == "[1]"
        # старый файл остаётся на месте
        assert (home / "rate_limit.json").exists()

    def test_nothing_to_do_twice(self, monkeypatch, tmp_path):
        project, home = tmp_path / "proj", tmp_path / "home"
        project.mkdir()
        home.mkdir()
        (home / "rate_limit.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(config, "BASE_DIR", project)
        monkeypatch.chdir(home)
        monkeypatch.delenv("RATE_LIMIT_FILE", raising=False)
        monkeypatch.delenv("ALLOWED_USERS_FILE", raising=False)

        assert config.migrate_legacy_state() == 1
        assert config.migrate_legacy_state() == 0

    def test_existing_file_not_overwritten(self, monkeypatch, tmp_path):
        project, home = tmp_path / "proj", tmp_path / "home"
        project.mkdir()
        home.mkdir()
        (home / "rate_limit.json").write_text('{"1": [1]}', encoding="utf-8")
        (project / "rate_limit.json").write_text('{"2": [2]}', encoding="utf-8")
        monkeypatch.setattr(config, "BASE_DIR", project)
        monkeypatch.chdir(home)
        monkeypatch.delenv("RATE_LIMIT_FILE", raising=False)
        monkeypatch.delenv("ALLOWED_USERS_FILE", raising=False)

        assert config.migrate_legacy_state() == 0
        assert (project / "rate_limit.json").read_text(encoding="utf-8") == '{"2": [2]}'

    def test_env_value_from_env_example_is_migrated(self, monkeypatch, tmp_path):
        # .env с RATE_LIMIT_FILE=rate_limit.json (как в .env.example) не должен
        # отключать перенос: значение относительное и ведёт в каталог проекта.
        project, home = tmp_path / "proj", tmp_path / "home"
        project.mkdir()
        home.mkdir()
        (home / "rate_limit.json").write_text('{"1": [1]}', encoding="utf-8")
        monkeypatch.setattr(config, "BASE_DIR", project)
        monkeypatch.chdir(home)
        monkeypatch.setenv("RATE_LIMIT_FILE", "rate_limit.json")
        monkeypatch.delenv("ALLOWED_USERS_FILE", raising=False)

        assert config.migrate_legacy_state() == 1
        assert (project / "rate_limit.json").read_text(encoding="utf-8") == '{"1": [1]}'

    def test_custom_env_path_is_not_migrated(self, monkeypatch, tmp_path):
        project, home = tmp_path / "proj", tmp_path / "home"
        project.mkdir()
        home.mkdir()
        (home / "rate_limit.json").write_text("{}", encoding="utf-8")
        monkeypatch.setattr(config, "BASE_DIR", project)
        monkeypatch.chdir(home)
        monkeypatch.setenv("RATE_LIMIT_FILE", str(tmp_path / "custom.json"))
        monkeypatch.delenv("ALLOWED_USERS_FILE", raising=False)

        assert config.migrate_legacy_state() == 0
        assert not (project / "rate_limit.json").exists()
        assert not (tmp_path / "custom.json").exists()


class TestLogging:
    def test_telebot_has_no_own_handler(self):
        # Свой StreamHandler pyTelegramBotAPI дублировал записи root-хендлеров.
        assert logging.getLogger("TeleBot").handlers == []
