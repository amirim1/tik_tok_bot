import time
from abc import ABC, abstractmethod

# Попытку не начинаем, если до дедлайна осталось меньше: запрос всё равно не успеет.
MIN_ATTEMPT_SECONDS = 5


def remaining_seconds(deadline: float | None) -> float | None:
    """Остаток до дедлайна (time.monotonic) или None, если дедлайн не задан.
    TimeoutError - начинать попытку уже поздно."""
    if deadline is None:
        return None
    remaining = deadline - time.monotonic()
    if remaining < MIN_ATTEMPT_SECONDS:
        raise TimeoutError("get_video deadline exceeded")
    return remaining


class BaseDownloader(ABC):
    @abstractmethod
    def get_video(self, url: str, deadline: float | None = None) -> dict | None:
        """deadline - общий дедлайн (time.monotonic) на все попытки; TimeoutError, если время вышло."""
        ...

    def close(self):  # noqa: B027 - опциональный метод
        pass
