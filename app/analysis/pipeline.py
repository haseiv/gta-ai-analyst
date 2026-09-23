from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from app.agents.orchestrator import AgentOrchestrator
from app.ai.base import AIProviderError, BaseAIProvider
from app.ai.schemas import PipelinePayload
from app.analysis.detection.base import BaseDetector
from app.analysis.detection.yolo import YOLODetector
from app.analysis.events.engine import EventEngine
from app.analysis.metrics.engine import compute_metrics, compute_scores
from app.analysis.tracking.tracker import TrackStore
from app.analysis.video.metadata import VideoMetadata
from app.config.settings import Settings
from app.learning.knowledge import CoachKnowledgeBase
from app.utils.logging import get_logger

logger = get_logger(__name__)

ProgressCallback = Callable[[float], None]
DetectorFactory = Callable[[Settings], BaseDetector]

LIMITATIONS = [
    "Standard YOLO is not a GTA/FiveM specialist model.",
    "Screen coordinates are pixels, not GTA world meters.",
    "Map geometry and cover are not detected.",
    "Crosshair, shots, damage, and kills are not detected.",
]


def default_detector_factory(settings: Settings) -> BaseDetector:
    return YOLODetector(settings.yolo_model_path)


class AnalysisPipeline:
    def __init__(
        self,
        settings: Settings,
        provider: BaseAIProvider,
        detector_factory: DetectorFactory | None = None,
        knowledge: CoachKnowledgeBase | None = None,
    ) -> None:
        self.settings = settings
        self.provider = provider
        self.detector_factory = detector_factory or default_detector_factory
        self.knowledge = knowledge or CoachKnowledgeBase(top_k=settings.human_examples_top_k)

    async def run(
        self,
        analysis_id: str,
        video_path: Path,
        metadata: VideoMetadata,
        on_progress: ProgressCallback | None = None,
    ) -> dict:
        from app.analysis.video.reader import iter_sampled_frames

        detector = self.detector_factory(self.settings)
        detector.reset()
        store = TrackStore()
        events = EventEngine()
        frame_count = 0
        last_logged = -10

        try:
            for timestamp, frame in iter_sampled_frames(
                video_path,
                self.settings.analysis_fps,
                source_fps=metadata.fps or None,
            ):
                detections = detector.track(frame)
                store.update(timestamp, detections)
                events.on_frame(timestamp, detections)
                frame_count += 1
                del frame
                if metadata.duration > 0:
                    progress = min(90.0, (timestamp / metadata.duration) * 90.0)
                    if on_progress:
                        on_progress(progress)
                    if progress - last_logged >= 10:
                        logger.info("progress milestone analysis_id=%s progress=%.0f", analysis_id, progress)
                        last_logged = progress
        finally:
            detector.reset()

        logger.info("CV completed analysis_id=%s frames=%s tracks=%s", analysis_id, frame_count, len(store.tracks))
        game_events = events.finalize(store.tracks)
        metrics = compute_metrics(store.tracks, frame_count)
        scores = compute_scores(metrics)
        payload = PipelinePayload(
            analysis_id=analysis_id,
            duration=metadata.duration,
            metadata={
                "width": metadata.width,
                "height": metadata.height,
                "fps": metadata.fps,
                "codec": metadata.codec,
                "analyzed_frames": frame_count,
            },
            metrics=[item.model_dump() for item in metrics],
            scores=[item.model_dump() for item in scores],
            events=[item.model_dump() for item in game_events],
            tracks=store.summaries(),
            limitations=LIMITATIONS,
        )
        if on_progress:
            on_progress(92.0)

        orchestrator = AgentOrchestrator(self.provider, self.knowledge)
        try:
            ai_result = await orchestrator.run(payload)
        except AIProviderError:
            logger.warning("AI coach unavailable analysis_id=%s; keeping CV result", analysis_id)
            ai_result = orchestrator.fallback(payload)

        if on_progress:
            on_progress(100.0)
        result = payload.model_dump()
        result.update(ai_result)
        return json.loads(json.dumps(result))
