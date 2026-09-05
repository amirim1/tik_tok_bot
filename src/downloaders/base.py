from abc import ABC, abstractmethod


class BaseDownloader(ABC):
    @abstractmethod
    def get_video(self, url: str) -> dict | None:
        ...

    def close(self):  # noqa: B027 - опциональный метод
        pass
