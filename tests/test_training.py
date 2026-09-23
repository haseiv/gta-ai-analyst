from app.database.repository import TrainingRepository
from app.learning.knowledge import CoachKnowledgeBase
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
