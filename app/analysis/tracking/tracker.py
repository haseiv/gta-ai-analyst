from __future__ import annotations

from app.analysis.detection.base import Detection
from app.analysis.tracking.models import Track, TrackPoint


class TrackStore:
    def __init__(self) -> None:
        self.tracks: dict[int, Track] = {}
        self._synthetic_id = 10_000

    def update(self, timestamp: float, detections: list[Detection]) -> list[Detection]:
        assigned: list[Detection] = []
        for detection in detections:
            track_id = detection.track_id
            if track_id is None:
                self._synthetic_id += 1
                track_id = self._synthetic_id
                detection.track_id = track_id
            track = self.tracks.get(track_id)
            if track is None:
                track = Track(track_id=track_id, class_name=detection.class_name)
                self.tracks[track_id] = track
            track.history.append(
                TrackPoint(
                    timestamp=timestamp,
                    center_x=detection.center_x,
                    center_y=detection.center_y,
                    bbox=(detection.x1, detection.y1, detection.x2, detection.y2),
                    confidence=detection.confidence,
                )
            )
            assigned.append(detection)
        return assigned

    def summaries(self) -> list[dict]:
        return [track.summary() for track in self.tracks.values()]
