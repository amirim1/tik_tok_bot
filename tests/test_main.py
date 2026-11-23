import os
import queue
import threading
import time
from types import SimpleNamespace

import main
import src.utils as utils


class FakeDownloader:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.calls = []

    def get_video(self, url, deadline=None):
        self.calls.append((url, deadline))
        if self.error:
            raise self.error
        return self.result


def make_message(text, user_id=1, message_id=5):
    chat = SimpleNamespace(id=100)
    return SimpleNamespace(
        text=text, chat=chat, message_id=message_id, from_user=SimpleNamespace(id=user_id),
    )


class FakeBot:
    def __init__(self):
        self.replies = []
        self.edits = []
        self.sent = []
        self.status_id = 900

    def reply_to(self, message, text):
        self.replies.append(text)
        self.status_id += 1
        return SimpleNamespace(message_id=self.status_id)

    def edit_message_text(self, text, chat_id, message_id, **kwargs):
        self.edits.append(text)

    def send_video(self, chat_id, vf, **kwargs):
        self.sent.append(os.path.basename(vf.name))


def setup_handler(monkeypatch, tmp_path, downloader):
    """Собирает цепочку декораторов вокруг настоящего обработчика на фиктивном боте:
    декораторы модуля захватывают реальный bot при импорте, подмена main.bot
    на них не действует - и тест ушёл бы в сеть к Telegram."""
    fake_bot = FakeBot()
    # тело обработчика и safe_edit обращаются к глобальному bot модуля main
    monkeypatch.setattr(main, "bot", fake_bot)
    monkeypatch.setattr(main, "check_access", lambda user_id: True)
    monkeypatch.setattr(utils, "_user_requests", {})
    monkeypatch.setattr(utils, "RATE_LIMIT_FILE", str(tmp_path / "rl.json"))
    monkeypatch.setattr(main, "get_downloader", lambda url: (downloader, "tiktok") if "tiktok.com" in url else (None, None))
    monkeypatch.setattr(main, "is_safe_video_url", lambda url: True)
    monkeypatch.setattr(main, "TEMP_DIR", tmp_path)
    monkeypatch.setattr(main, "cleanup_old_files", lambda *args, **kwargs: None)
    main._shutting_down.clear()
    # снимаем оба декоратора (require_access, rate_limit) до исходной функции
    target = main.handle_video_request
    while hasattr(target, "__wrapped__"):
        target = target.__wrapped__
    handler = main.require_access(fake_bot)(utils.rate_limit(fake_bot)(target))
    return fake_bot, handler


class TestUrlExtraction:
    def test_url_with_caption(self, monkeypatch, tmp_path):
        downloader = FakeDownloader(result=None)
        bot, handler = setup_handler(monkeypatch, tmp_path, downloader)
        text = "https://www.tiktok.com/@user/video/123?is_from_webapp=1 🎵 оригинальный звук - author"

        handler(make_message(text))

        assert downloader.calls[0][0] == "https://www.tiktok.com/@user/video/123?is_from_webapp=1"
        assert bot.edits and "Не удалось получить видео" in bot.edits[0]

    def test_plain_url_still_works(self, monkeypatch, tmp_path):
        downloader = FakeDownloader(result=None)
        _, handler = setup_handler(monkeypatch, tmp_path, downloader)

        handler(make_message("https://vt.tiktok.com/ZSdjx4HkR/"))

        assert downloader.calls[0][0] == "https://vt.tiktok.com/ZSdjx4HkR/"

    def test_schemeless_url_still_works(self, monkeypatch, tmp_path):
        downloader = FakeDownloader(result=None)
        _, handler = setup_handler(monkeypatch, tmp_path, downloader)

        handler(make_message("tiktok.com/@user/video/123"))

        assert downloader.calls[0][0] == "tiktok.com/@user/video/123"

    def test_plain_text_asks_for_link(self, monkeypatch, tmp_path):
        downloader = FakeDownloader(result=None)
        bot, handler = setup_handler(monkeypatch, tmp_path, downloader)

        handler(make_message("привет"))

        assert downloader.calls == []
        assert "Пришли ссылку" in bot.replies[0]


class TestGetVideoDeadline:
    def test_deadline_is_passed_to_downloader(self, monkeypatch, tmp_path):
        downloader = FakeDownloader(result=None)
        _, handler = setup_handler(monkeypatch, tmp_path, downloader)
        before = time.monotonic()

        handler(make_message("https://vt.tiktok.com/ZSdjx4HkR/"))

        deadline = downloader.calls[0][1]
        assert before + main.GET_VIDEO_DEADLINE <= deadline <= time.monotonic() + main.GET_VIDEO_DEADLINE

    def test_timeout_message(self, monkeypatch, tmp_path):
        downloader = FakeDownloader(error=TimeoutError("get_video deadline exceeded"))
        bot, handler = setup_handler(monkeypatch, tmp_path, downloader)

        handler(make_message("https://vt.tiktok.com/ZSdjx4HkR/"))

        assert len(bot.edits) == 1
        assert "Превышено время" in bot.edits[0]


class TestVideoContainer:
    def _run_download(self, monkeypatch, tmp_path, content):
        downloader = FakeDownloader(result={
            "video_url": "https://cdn.example.com/x", "author": "a", "description": "d",
        })
        bot, handler = setup_handler(monkeypatch, tmp_path, downloader)

        class FakeResponse:
            status_code = 200
            headers = {}

            def iter_content(self, chunk_size):
                yield content

            def raise_for_status(self):
                pass

            def close(self):
                pass

        monkeypatch.setattr(main.requests, "get", lambda *args, **kwargs: FakeResponse())
        handler(make_message("https://vt.tiktok.com/ZSdjx4HkR/"))
        return bot, tmp_path

    def test_webm_is_sent_with_real_extension(self, monkeypatch, tmp_path):
        bot, directory = self._run_download(
            monkeypatch, tmp_path,
            b'\x1aE\xdf\xa3\x00\x00\x00\x1fB\x86\x81\x01B\xf7\x81\x01B\xf2\x81\x04B\xf3\x81\x08B\x82webm',
        )
        assert len(bot.sent) == 1
        assert bot.sent[0].endswith(".webm")
        # временный файл убран
        assert list(directory.glob("*.webm")) == []

    def test_mp4_keeps_extension(self, monkeypatch, tmp_path):
        bot, _ = self._run_download(monkeypatch, tmp_path, b'\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00')
        assert len(bot.sent) == 1
        assert bot.sent[0].endswith(".mp4")

    def test_garbage_is_rejected(self, monkeypatch, tmp_path):
        bot, directory = self._run_download(monkeypatch, tmp_path, b"<html>blocked</html>")
        assert bot.sent == []
        assert "некорректный файл" in bot.edits[-1]
        assert list(directory.glob("*.mp4")) == []


class TestGracefulShutdown:
    def test_new_requests_rejected_without_spending_limit(self, monkeypatch, tmp_path):
        downloader = FakeDownloader()
        bot, handler = setup_handler(monkeypatch, tmp_path, downloader)
        main._shutting_down.set()

        handler(make_message("https://vt.tiktok.com/ZSdjx4HkR/"))

        assert downloader.calls == []
        assert "перезапускается" in bot.replies[0]
        assert utils._user_requests == {}

    @staticmethod
    def _fake_pool(busy_worker=False, queued=0):
        worker = SimpleNamespace(
            received_task_event=threading.Event(), done_event=threading.Event(),
        )
        worker.received_task_event.set()
        if not busy_worker:
            worker.done_event.set()
        tasks = queue.Queue()
        for _ in range(queued):
            tasks.put(object())
        return SimpleNamespace(workers=[worker], tasks=tasks)

    def test_idle_pool_is_not_busy(self):
        assert main._workers_busy(self._fake_pool(busy_worker=False, queued=0)) is False

    def test_running_worker_is_busy(self):
        assert main._workers_busy(self._fake_pool(busy_worker=True)) is True

    def test_queued_task_is_busy(self):
        assert main._workers_busy(self._fake_pool(busy_worker=False, queued=1)) is True

    def test_wait_returns_at_once_when_idle(self):
        pool = self._fake_pool()
        saved = main.bot
        try:
            main.bot = SimpleNamespace(worker_pool=pool)
            started = time.monotonic()
            assert main._wait_workers(5) is True
            assert time.monotonic() - started < 1
        finally:
            main.bot = saved

    def test_wait_times_out_on_busy_worker(self):
        pool = self._fake_pool(busy_worker=True)
        saved = main.bot
        try:
            main.bot = SimpleNamespace(worker_pool=pool)
            started = time.monotonic()
            assert main._wait_workers(0.3) is False
            assert time.monotonic() - started >= 0.3
        finally:
            main.bot = saved

    def test_wait_returns_when_worker_finishes(self):
        pool = self._fake_pool(busy_worker=True)
        threading.Timer(0.3, pool.workers[0].done_event.set).start()
        saved = main.bot
        try:
            main.bot = SimpleNamespace(worker_pool=pool)
            assert main._wait_workers(5) is True
        finally:
            main.bot = saved
