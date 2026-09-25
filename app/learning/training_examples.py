from __future__ import annotations

from app.database.models import TrainingExample
from app.database.repository import TrainingRepository
from app.utils.time import utc_now

CATEGORY_ALIASES = {
    "aim": "Aim",
    "прицел": "Aim",
    "tracking": "Aim",
    "трекинг": "Aim",
    "movement": "Movement",
    "движение": "Movement",
    "positioning": "Positioning",
    "позиционирование": "Positioning",
    "awareness": "Awareness",
    "осведомлённость": "Awareness",
    "combat": "Combat",
    "бой": "Combat",
    "general": "General",
    "общее": "General",
}


def normalize_category(value: str) -> str:
    stripped = value.strip()
    return CATEGORY_ALIASES.get(stripped.casefold(), stripped or "General")


class TrainingService:
    def __init__(self, repo: TrainingRepository | None = None) -> None:
        self.repo = repo or TrainingRepository()

    def add(
        self,
        analysis_id: str,
        created_by: int,
        category: str,
        ai_analysis: str,
        human_analysis: str | None = None,
        recommendation: str | None = None,
        timestamp_start: float | None = None,
        timestamp_end: float | None = None,
        dataset_version: str = "v1",
    ) -> TrainingExample:
        example = TrainingExample(
            analysis_id=analysis_id,
            timestamp_start=timestamp_start,
            timestamp_end=timestamp_end,
            category=normalize_category(category),
            ai_analysis=ai_analysis,
            human_analysis=human_analysis,
            recommendation=recommendation,
            dataset_version=dataset_version,
            created_by=created_by,
            created_at=utc_now(),
        )
        return self.repo.create(example)
