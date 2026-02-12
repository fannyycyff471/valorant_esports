from abc import ABC, abstractmethod

class MatchSourceAdapter(ABC):
    @abstractmethod
    def fetch_matches(self, days: int) -> list[dict]:
        ...

    @abstractmethod
    def normalize_match(self, raw: dict) -> dict:
        ...
