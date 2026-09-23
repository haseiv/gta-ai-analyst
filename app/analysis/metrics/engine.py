from __future__ import annotations

from app.analysis.metrics.models import Metric, Score
from app.analysis.tracking.models import Track


def _metric(name: str, value: float | None, confidence: float, sample_size: int) -> Metric:
    if value is None or sample_size <= 0:
        return Metric(name=name, value=None, confidence=0.0, sample_size=sample_size, status="insufficient_data")
    return Metric(name=name, value=round(value, 3), confidence=confidence, sample_size=sample_size, status="ok")


def compute_metrics(tracks: dict[int, Track], frame_count: int) -> list[Metric]:
    values = list(tracks.values())
    speeds = [track.average_screen_speed for track in values if len(track.history) >= 2]
    changes = [track.direction_changes for track in values]
    visibilities = [track.visibility_duration for track in values if track.visibility_duration > 0]
    confidences = [point.confidence for track in values for point in track.history]
    max_simultaneous = 0
    timeline: dict[float, int] = {}
    for track in values:
        for point in track.history:
            key = round(point.timestamp, 2)
            timeline[key] = timeline.get(key, 0) + 1
    if timeline:
        max_simultaneous = max(timeline.values())

    movement_activity = sum(speeds) / len(speeds) if speeds else None
    if speeds:
        mean = sum(speeds) / len(speeds)
        variance = sum((item - mean) ** 2 for item in speeds) / len(speeds)
        movement_consistency = 1.0 / (1.0 + variance / max(mean, 1.0))
    else:
        movement_consistency = None

    return [
        _metric("movement_activity", movement_activity, 0.6 if speeds else 0.0, len(speeds)),
        _metric("movement_consistency", movement_consistency, 0.55 if speeds else 0.0, len(speeds)),
        _metric("direction_changes", float(sum(changes)) if values else None, 0.7 if values else 0.0, len(values)),
        _metric("targets_detected", float(len(values)) if frame_count else None, 0.8 if values else 0.0, len(values)),
        _metric(
            "average_target_visibility",
            sum(visibilities) / len(visibilities) if visibilities else None,
            0.7 if visibilities else 0.0,
            len(visibilities),
        ),
        _metric(
            "simultaneous_targets",
            float(max_simultaneous) if timeline else None,
            0.75 if timeline else 0.0,
            len(timeline),
        ),
        _metric(
            "tracking_confidence",
            sum(confidences) / len(confidences) if confidences else None,
            0.8 if confidences else 0.0,
            len(confidences),
        ),
    ]


def _score(name: str, value: float | None, confidence: float, status: str | None = None) -> Score:
    if value is None:
        return Score(name=name, value=None, confidence=0.0, status="insufficient_data")
    return Score(name=name, value=round(min(10.0, max(0.0, value)), 1), confidence=confidence, status=status or "ok")


def compute_scores(metrics: list[Metric]) -> list[Score]:
    by_name = {metric.name: metric for metric in metrics}

    movement = None
    movement_conf = 0.0
    activity = by_name.get("movement_activity")
    consistency = by_name.get("movement_consistency")
    if activity and activity.value is not None and consistency and consistency.value is not None:
        # Screen-space heuristic only. Not world-space skill rating.
        normalized_activity = min(activity.value / 250.0, 1.0)
        movement = 10.0 * (0.45 * normalized_activity + 0.55 * consistency.value)
        movement_conf = min(activity.confidence, consistency.confidence)

    awareness = None
    awareness_conf = 0.0
    visibility = by_name.get("average_target_visibility")
    simultaneous = by_name.get("simultaneous_targets")
    targets = by_name.get("targets_detected")
    if (
        visibility
        and visibility.value is not None
        and simultaneous
        and simultaneous.value is not None
        and targets
        and targets.value
        and targets.value >= 2
    ):
        awareness = min(10.0, 4.0 + min(visibility.value, 6.0) + min(simultaneous.value, 4.0) * 0.6)
        awareness_conf = min(visibility.confidence, simultaneous.confidence)

    return [
        _score("Movement", movement, movement_conf),
        _score("Positioning", None, 0.0),
        _score("Awareness", awareness, awareness_conf),
        _score("Aim", None, 0.0),
        _score("Cover Usage", None, 0.0),
    ]
