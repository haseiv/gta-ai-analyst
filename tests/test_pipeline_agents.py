from pathlib import Path
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from app.agents.aim import AimAgent
from app.ai.base import AIProviderError, BaseAIProvider
from app.ai.schemas import AgentResult, CoachReport, CriticResult, PipelinePayload
from app.analysis.detection.base import BaseDetector, Detection
from app.analysis.detection.yolo import YOLODetector
from app.analysis.pipeline import AnalysisPipeline
from app.analysis.video.metadata import VideoMetadata
from app.config.settings import Settings


class FakeDetector(BaseDetector):
    def detect(self, frame):
        return [
            Detection(0, "person", 0.9, 1, 1, 20, 20, 10, 10, track_id=1),
        ]


class GenericDetector(FakeDetector):
    def __init__(self) -> None:
        self.calls = 0

    @property
    def gameplay_capable(self) -> bool:
        return False

    @property
    def profile(self) -> str:
        return "generic_coco"

    def detect(self, frame):
        self.calls += 1
        return super().detect(frame)


def test_yolo_recognizes_generic_coco_profile():
    detector = YOLODetector.__new__(YOLODetector)
    detector.model = SimpleNamespace(
        names={
            **{index: f"class-{index}" for index in range(75)},
            75: "person",
            76: "car",
            77: "truck",
            78: "traffic light",
            79: "toothbrush",
        }
    )
    assert detector.gameplay_capable is False
    assert detector.profile == "generic_coco"


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
    assert result["coach"]["summary"]


@pytest.mark.asyncio
async def test_pipeline_runs_cv_outside_event_loop_thread(monkeypatch, tmp_path: Path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"0")
    event_loop_thread = threading.get_ident()
    detector_threads: list[int] = []

    def fake_frames(_path, _fps, source_fps=None):
        yield 0.0, np.zeros((32, 32, 3), dtype=np.uint8)

    class ThreadRecordingDetector(FakeDetector):
        def detect(self, frame):
            detector_threads.append(threading.get_ident())
            return super().detect(frame)

    monkeypatch.setattr("app.analysis.video.reader.iter_sampled_frames", fake_frames)
    pipeline = AnalysisPipeline(
        Settings(),
        FakeProvider(),
        detector_factory=lambda _settings: ThreadRecordingDetector(),
    )

    await pipeline.run(
        "A10",
        video,
        VideoMetadata(1.0, 32, 32, 5.0, "h264"),
    )

    assert detector_threads
    assert detector_threads[0] != event_loop_thread


@pytest.mark.asyncio
async def test_generic_coco_detector_cannot_produce_gameplay_claims(monkeypatch, tmp_path: Path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"0")
    detector = GenericDetector()

    def fake_frames(_path, _fps, source_fps=None):
        for index in range(4):
            yield index * 0.2, np.full((32, 32, 3), index * 10, dtype=np.uint8)

    monkeypatch.setattr("app.analysis.video.reader.iter_sampled_frames", fake_frames)
    pipeline = AnalysisPipeline(
        Settings(),
        FakeProvider(),
        detector_factory=lambda _settings: detector,
    )

    result = await pipeline.run(
        "A11",
        video,
        VideoMetadata(1.0, 32, 32, 5.0, "h264"),
    )

    assert detector.calls == 0
    assert result["metadata"]["gameplay_analysis_available"] is False
    assert all(score["value"] is None for score in result["scores"])
    assert result["tracks"] == []
    assert "игровой разбор отключён" in result["coach"]["summary"]
