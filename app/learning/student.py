from __future__ import annotations

import json
import math
from typing import Literal

from pydantic import BaseModel, Field

from app.ai.base import AIProviderError, BaseAIProvider
from app.database.models import DistilledExample, TrainingExample
from app.database.repository import AnalysisRepository, DistilledExampleRepository
from app.utils.time import utc_now


class TeacherLabel(BaseModel):
    category: str
    score: float = Field(ge=0, le=10)
    verdict: Literal["good", "mixed", "needs_work"]
    confidence: float = Field(ge=0, le=0.9)
    rationale: str
    recommendation: str = ""


def extract_features(result: dict) -> dict[str, float]:
    duration_minutes = max(float(result.get("duration") or 0) / 60.0, 0.1)
    metadata = result.get("metadata") or {}
    hud = metadata.get("hud_analysis") or {}
    events = result.get("events") or []
    metrics = {
        str(item.get("name")): float(item.get("value"))
        for item in result.get("metrics") or []
        if item.get("value") is not None and item.get("status") != "insufficient_data"
    }
    return {
        "rounds_per_min": min(float(hud.get("rounds_observed") or 0) / duration_minutes / 100.0, 3.0),
        "kills_per_min": min(float(hud.get("player_kills") or hud.get("kills_observed") or 0) / duration_minutes / 10.0, 3.0),
        "finish_score": float(hud.get("finish_score") or 0) / 10.0,
        "unconverted_per_min": min(len(hud.get("unconverted_bursts") or []) / duration_minutes / 5.0, 3.0),
        "rapid_per_min": min(
            sum(event.get("type") == "RAPID_MOVEMENT" for event in events) / duration_minutes / 20.0,
            3.0,
        ),
        "movement_activity": min(float(metrics.get("movement_activity", 0)) / 30.0, 3.0),
        "has_combat_hud": 1.0 if hud.get("available") else 0.0,
    }


class TrainingDistillationService:
    def __init__(
        self,
        provider: BaseAIProvider,
        analyses: AnalysisRepository | None = None,
        distilled: DistilledExampleRepository | None = None,
    ) -> None:
        self.provider = provider
        self.analyses = analyses or AnalysisRepository()
        self.distilled = distilled or DistilledExampleRepository()

    async def distill(self, example: TrainingExample) -> tuple[TeacherLabel, int]:
        if not example.human_analysis:
            raise ValueError("Для обучения локального ученика нужен ручной разбор.")
        analysis = self.analyses.get(example.analysis_id)
        if analysis is None or not analysis.result_json:
            raise ValueError("Исходный результат анализа не найден.")
        result = json.loads(analysis.result_json)
        features = extract_features(result)
        prompt = json.dumps(
            {
                "task": (
                    "Convert the HUMAN-APPROVED GTA coaching note into one conservative teacher label. "
                    "Do not infer anything not present in the human note or local numeric evidence."
                ),
                "category": example.category,
                "human_analysis": example.human_analysis,
                "human_recommendation": example.recommendation,
                "local_features": features,
                "required_json": {
                    "category": example.category,
                    "score": "0..10",
                    "verdict": "good|mixed|needs_work",
                    "confidence": "0..0.9",
                    "rationale": "short Russian explanation",
                    "recommendation": "short Russian recommendation",
                },
            },
            ensure_ascii=False,
        )
        label = await self.provider.generate_structured(
            prompt,
            TeacherLabel,
            system=(
                "You are a label normalizer for a small local student model. The human review is authoritative. "
                "Never use your own previous answer as ground truth and never claim to have watched video frames."
            ),
        )
        label.category = example.category
        row = DistilledExample(
            training_example_id=example.id,
            analysis_id=example.analysis_id,
            category=example.category,
            features_json=json.dumps(features, ensure_ascii=False),
            teacher_label_json=label.model_dump_json(),
            created_at=utc_now(),
        )
        self.distilled.create(row)
        return label, self.distilled.count(example.category)


class LocalStudent:
    def __init__(self, repo: DistilledExampleRepository | None = None, minimum_examples: int = 3) -> None:
        self.repo = repo or DistilledExampleRepository()
        self.minimum_examples = minimum_examples

    def predict(self, result: dict, category: str) -> dict | None:
        rows = self.repo.by_category(category)
        if len(rows) < self.minimum_examples:
            return None
        features = extract_features(result)
        neighbors = []
        for row in rows:
            saved = json.loads(row.features_json)
            label = TeacherLabel.model_validate_json(row.teacher_label_json)
            keys = sorted(set(features) | set(saved))
            distance = math.sqrt(sum((features.get(key, 0.0) - saved.get(key, 0.0)) ** 2 for key in keys))
            neighbors.append((distance, label))
        nearest = sorted(neighbors, key=lambda item: item[0])[:5]
        weights = [1.0 / (0.1 + distance) for distance, _ in nearest]
        score = sum(weight * label.score for weight, (_, label) in zip(weights, nearest)) / sum(weights)
        average_distance = sum(distance for distance, _ in nearest) / len(nearest)
        confidence = min(0.85, len(rows) / 20.0, 1.0 / (1.0 + average_distance))
        verdict = "good" if score >= 7 else "needs_work" if score < 5 else "mixed"
        return {
            "category": category,
            "score": round(score, 1),
            "verdict": verdict,
            "confidence": round(confidence, 2),
            "examples_used": len(nearest),
            "dataset_size": len(rows),
            "status": "local_student_knn",
        }

    def predict_all(self, result: dict) -> list[dict]:
        return [prediction for category in self.repo.categories() if (prediction := self.predict(result, category))]
