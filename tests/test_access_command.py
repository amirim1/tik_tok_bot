from types import SimpleNamespace

import main


def test_format_whitelist_user_prefers_username(monkeypatch):
    monkeypatch.setattr(
        main.bot,
        "get_chat",
        lambda _user_id: SimpleNamespace(username="amirka", first_name="Амир", last_name=""),
    )

    assert main.format_whitelist_user(123) == "123 — @amirka"


def test_format_whitelist_user_uses_display_name(monkeypatch):
    monkeypatch.setattr(
        main.bot,
        "get_chat",
        lambda _user_id: SimpleNamespace(username=None, first_name="Амир", last_name="Иванов"),
    )

    assert main.format_whitelist_user(123) == "123 — Амир Иванов"


def test_format_whitelist_user_falls_back_to_id(monkeypatch):
    def raise_error(_user_id):
        raise RuntimeError("chat unavailable")

    monkeypatch.setattr(main.bot, "get_chat", raise_error)

    assert main.format_whitelist_user(123) == "123"
