from app.agents.local_coach import build_local_coach_report
from app.ai.schemas import PipelinePayload


def test_local_coach_explains_empty_detection():
    result = build_local_coach_report(PipelinePayload(analysis_id="A1", duration=90, metadata={"analyzed_frames": 40}))
    assert "YOLO" in result["coach"]["summary"]
    assert result["coach"]["recommendations"]
    assert result["ai_available"] is False
