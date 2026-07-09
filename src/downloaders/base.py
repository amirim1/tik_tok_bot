from abc import ABC, abstractmethod
from typing import Optional, Dict


class BaseDownloader(ABC):
    @abstractmethod
    def get_video(self, url: str) -> Optional[Dict]:
        ...

    def close(self):
        pass
