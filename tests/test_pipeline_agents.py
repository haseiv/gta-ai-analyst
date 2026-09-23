from pathlib import Path

import numpy as np
import pytest

from app.agents.aim import AimAgent
from app.ai.base import AIProviderError, BaseAIProvider
from app.ai.schemas import AgentResult, CoachReport, CriticResult, PipelinePayload
from app.analysis.detection.base import BaseDetector, Detection
from app.analysis.pipeline import AnalysisPipeline
from app.analysis.video.metadata import VideoMetadata
from app.config.settings import Settings


class FakeDetector(BaseDetector):
    def detect(self, frame):
        return [
            Detection(0, "person", 0.9, 1, 1, 20, 20, 10, 10, track_id=1),
        ]


class FakeProvider(BaseAIProvider):
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    async def analyze(self, prompt: str, system: str | None = None) -> str:
        return "{}"

    async def generate_structured(self, prompt, schema, system=None):
        self.calls += 1
        if self.fail:
            raise AIProviderError("down")
        if schema is AgentResult:
            return AgentResult(category="Movement", findings=[], notes="ok")
        if schema is CoachReport:
            return CoachReport(summary="Merged findings only", recommendations=["Stay calm"])
        return CriticResult(approved=True)


@pytest.mark.asyncio
async def test_aim_agent_is_insufficient():
    result = await AimAgent(FakeProvider()).run(PipelinePayload(analysis_id="A1", duration=1))
    assert result.status == "insufficient_data"


@pytest.mark.asyncio
async def test_pipeline_keeps_cv_when_ai_down(monkeypatch, tmp_path: Path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"0")

    def fake_frames(_path, _fps, source_fps=None):
        yield 0.0, np.zeros((32, 32, 3), dtype=np.uint8)
        yield 0.4, np.zeros((32, 32, 3), dtype=np.uint8)

    monkeypatch.setattr("app.analysis.video.reader.iter_sampled_frames", fake_frames)
    pipeline = AnalysisPipeline(
        Settings(),
        FakeProvider(fail=True),
        detector_factory=lambda _settings: FakeDetector(),
    )
    result = await pipeline.run(
        "A9",
        video,
        VideoMetadata(1.0, 32, 32, 5.0, "h264"),
    )
    assert result["ai_available"] is False
    assert result["metrics"]
    assert "Computer Vision" in result["coach"]["summary"]
