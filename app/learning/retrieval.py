from __future__ import annotations

from app.database.models import TrainingExample
from app.database.repository import TrainingRepository


class CategoryRetriever:
    def __init__(self, repo: TrainingRepository | None = None, top_k: int = 5) -> None:
        self.repo = repo or TrainingRepository()
        self.top_k = top_k

    def retrieve(self, category: str) -> list[TrainingExample]:
        return self.repo.by_category(category, self.top_k)
