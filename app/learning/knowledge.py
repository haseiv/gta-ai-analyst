from __future__ import annotations

from app.database.repository import TrainingRepository
from app.learning.retrieval import CategoryRetriever
from app.utils.time import format_timestamp


class CoachKnowledgeBase:
    """Developer-selected examples only. The bot never auto-learns from its own output."""

    def __init__(self, top_k: int = 5, repo: TrainingRepository | None = None) -> None:
        self.retriever = CategoryRetriever(repo=repo, top_k=top_k)

    def retrieve(self, category: str) -> list[dict]:
        try:
            examples = self.retriever.retrieve(category)
        except Exception:
            return []
        payload = []
        for item in examples:
            payload.append(
                {
                    "analysis_id": item.analysis_id,
                    "category": item.category,
                    "moment": f"{format_timestamp(item.timestamp_start)}-{format_timestamp(item.timestamp_end)}",
                    "human_analysis": item.human_analysis or item.ai_analysis,
                    "recommendation": item.recommendation,
                }
            )
        return payload
