import json
from pathlib import Path


class HistoryManager:
    def __init__(self, path: Path, limit: int = 20) -> None:
        self.path = path
        self.limit = limit
        self.items = []
        self._load()

    def _load(self) -> None:
        if not self.path.exists():
            self.items = []
            return
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, list):
                self.items = [str(item) for item in data][: self.limit]
            else:
                self.items = []
        except Exception:
            self.items = []

    def _save(self) -> None:
        try:
            with self.path.open("w", encoding="utf-8") as handle:
                json.dump(self.items, handle, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def add(self, term: str) -> None:
        term = term.strip()
        if not term:
            return
        if term in self.items:
            self.items.remove(term)
        self.items.insert(0, term)
        self.items = self.items[: self.limit]
        self._save()
