from __future__ import annotations

from app.analysis.detection.base import Detection
from app.analysis.events.models import EventType, GameEvent
from app.analysis.tracking.models import Track


class EventEngine:
    def __init__(self, long_visibility_seconds: float = 3.0, rapid_speed: float = 400.0) -> None:
        self.long_visibility_seconds = long_visibility_seconds
        self.rapid_speed = rapid_speed
        self._seen: set[int] = set()
        self._events: list[GameEvent] = []
        self._counter = 0

    def on_frame(self, timestamp: float, detections: list[Detection]) -> None:
        current_ids = {d.track_id for d in detections if d.track_id is not None}
        appeared = current_ids - self._seen
        disappeared = self._seen - current_ids
        for track_id in appeared:
            detection = next(d for d in detections if d.track_id == track_id)
            self._add(
                EventType.OBJECT_APPEARED,
                timestamp,
                detection.confidence,
                {"track_id": track_id, "class_name": detection.class_name},
            )
        for track_id in disappeared:
            self._add(
                EventType.OBJECT_DISAPPEARED,
                timestamp,
                0.7,
                {"track_id": track_id},
            )
        if len(current_ids) >= 3:
            self._add(
                EventType.MULTIPLE_TARGETS_VISIBLE,
                timestamp,
                0.8,
                {"count": len(current_ids)},
            )
        self._seen = current_ids

    def finalize(self, tracks: dict[int, Track]) -> list[GameEvent]:
        for track in tracks.values():
            if track.visibility_duration >= self.long_visibility_seconds:
                self._add(
                    EventType.LONG_TARGET_VISIBILITY,
                    track.history[-1].timestamp if track.history else 0.0,
                    0.75,
                    {
                        "track_id": track.track_id,
                        "class_name": track.class_name,
                        "visibility_duration": round(track.visibility_duration, 2),
                    },
                )
            if track.average_screen_speed >= self.rapid_speed:
                self._add(
                    EventType.RAPID_MOVEMENT,
                    track.history[-1].timestamp if track.history else 0.0,
                    0.7,
                    {
                        "track_id": track.track_id,
                        "average_screen_speed": round(track.average_screen_speed, 2),
                        "unit": "screen_px_per_sec",
                    },
                )
            if track.direction_changes >= 3:
                self._add(
                    EventType.DIRECTION_CHANGE,
                    track.history[-1].timestamp if track.history else 0.0,
                    0.65,
                    {
                        "track_id": track.track_id,
                        "direction_changes": track.direction_changes,
                    },
                )
        return self._events

    def _add(self, event_type: EventType, timestamp: float, confidence: float, metadata: dict) -> None:
        self._counter += 1
        self._events.append(
            GameEvent(
                id=f"E{self._counter:04d}",
                type=event_type,
                timestamp=timestamp,
                confidence=confidence,
                metadata=metadata,
            )
        )
