import json

from app.ai.base import BaseAIProvider
from app.database.repository import AnalysisRepository, DistilledExampleRepository
from app.database.repository import TrainingRepository
from app.learning.knowledge import CoachKnowledgeBase
from app.learning.student import LocalStudent, TeacherLabel, TrainingDistillationService, extract_features
from app.learning.training_examples import TrainingService


def test_training_example_creation_and_retrieval(isolated_db):
    service = TrainingService()
    example = service.add(
        analysis_id="A184",
        created_by=99,
        category="Movement",
        ai_analysis="Too many direction changes",
        human_analysis="Player strafed without purpose",
        recommendation="Hold an angle longer",
        timestamp_start=90,
        timestamp_end=105,
    )
    assert example.id is not None
    repo = TrainingRepository()
    stats = repo.stats()
    assert stats["total"] == 1
    assert stats["Movement"] == 1
    knowledge = CoachKnowledgeBase(top_k=5, repo=repo)
    items = knowledge.retrieve("Movement")
    assert items[0]["human_analysis"] == "Player strafed without purpose"
    assert repo.delete(example.id) is True
    assert repo.stats()["total"] == 0


class FakeTeacher(BaseAIProvider):
    async def analyze(self, prompt: str, system: str | None = None) -> str:
        return ""

    async def generate_structured(self, prompt: str, schema, system: str | None = None):
        assert "human_analysis" in prompt
        return schema.model_validate(
            {
                "category": "Aim",
                "score": 8.0,
                "verdict": "good",
                "confidence": 0.8,
                "rationale": "Человек отметил хорошее сопровождение цели.",
                "recommendation": "Сохранять плавность.",
            }
        )


async def test_qwen_teacher_distills_human_reviews_for_local_student(isolated_db):
    analyses = AnalysisRepository()
    training = TrainingService()
    distilled = DistilledExampleRepository()
    service = TrainingDistillationService(FakeTeacher(), analyses=analyses, distilled=distilled)
    result = {
        "duration": 60,
        "metadata": {
            "hud_analysis": {
                "available": True,
                "rounds_observed": 80,
                "player_kills": 8,
                "finish_score": 8.0,
                "unconverted_bursts": [],
            }
        },
        "metrics": [],
        "events": [],
    }

    for index in range(3):
        analysis_id = f"A{index}"
        analyses.create(analysis_id, 99, 1, "clip.mp4", status="COMPLETED")
        analyses.update(analysis_id, result_json=json.dumps(result))
        example = training.add(
            analysis_id=analysis_id,
            created_by=99,
            category="Aim",
            ai_analysis="",
            human_analysis="Хороший трекинг и плавное сопровождение цели.",
            recommendation="Продолжать так же.",
        )
        label, count = await service.distill(example)
        assert isinstance(label, TeacherLabel)
        if index < 2:
            assert LocalStudent(distilled).predict(result, "Aim") is None

    prediction = LocalStudent(distilled).predict(result, "Aim")
    assert count == 3
    assert prediction is not None
    assert prediction["score"] == 8.0
    assert prediction["dataset_size"] == 3
    assert prediction["status"] == "local_student_knn"
    assert TrainingRepository().delete(1) is True
    assert distilled.count("Aim") == 2


def test_segment_features_only_use_events_inside_review_window():
    result = {
        "duration": 120,
        "metadata": {
            "hud_analysis": {
                "available": True,
                "rounds_observed": 200,
                "player_kills": 20,
                "finish_score": 9.0,
                "unconverted_bursts": [{"timestamp": 90, "rounds": 30}],
            }
        },
        "metrics": [{"name": "movement_activity", "value": 25}],
        "events": [
            {"type": "KILL", "timestamp": 12, "metadata": {"rounds_in_previous_4s": 6}},
            {"type": "BURST_NO_KILL", "timestamp": 70, "metadata": {"rounds_observed": 20}},
            {"type": "RAPID_MOVEMENT", "timestamp": 75, "metadata": {}},
        ],
    }

    features = extract_features(result, 10, 20)

    assert features["segment_scope"] == 1.0
    assert features["kills_per_min"] == 0.6
    assert features["rounds_per_min"] == 0.36
    assert features["unconverted_per_min"] == 0.0
    assert features["rapid_per_min"] == 0.0
    assert features["finish_score"] == 0.0
    assert features["movement_activity"] == 0.0
