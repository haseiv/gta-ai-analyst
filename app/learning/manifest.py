from __future__ import annotations

import json

from pydantic import BaseModel, Field, ValidationError, model_validator


class ManifestError(ValueError):
    pass


class TrainingManifestItem(BaseModel):
    source: str = ""
    analysis_id: str | None = None
    start: float | None = Field(default=None, ge=0)
    end: float | None = Field(default=None, ge=0)
    category: str = "General"
    human_analysis: str = Field(min_length=3, max_length=4000)
    recommendation: str = Field(default="", max_length=4000)

    @model_validator(mode="after")
    def validate_range(self) -> TrainingManifestItem:
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("end должен быть больше start")
        return self


def parse_training_manifest(payload: bytes, limit: int = 25) -> list[TrainingManifestItem]:
    if not payload:
        raise ManifestError("Файл манифеста пуст.")
    try:
        text = payload.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ManifestError("Манифест должен быть в UTF-8.") from exc

    try:
        if text.lstrip().startswith("["):
            raw_items = json.loads(text)
            if not isinstance(raw_items, list):
                raise ManifestError("JSON-манифест должен содержать массив примеров.")
        else:
            raw_items = [json.loads(line) for line in text.splitlines() if line.strip()]
        items = [TrainingManifestItem.model_validate(item) for item in raw_items]
    except (json.JSONDecodeError, ValidationError, TypeError) as exc:
        raise ManifestError(f"Некорректный манифест: {exc}") from exc

    if not items:
        raise ManifestError("В манифесте нет примеров.")
    if len(items) > limit:
        raise ManifestError(f"За один импорт разрешено не более {limit} примеров.")
    return items
