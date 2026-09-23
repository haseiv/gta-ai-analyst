from __future__ import annotations

from app.analysis.metrics.models import Metric, Score
from app.analysis.tracking.models import Track


def _metric(name: str, value: float | None, confidence: float, sample_size: int) -> Metric:
    if value is None or sample_size <= 0:
        return Metric(name=name, value=None, confidence=0.0, sample_size=sample_size, status="insufficient_data")
    return Metric(name=name, value=round(value, 3), confidence=confidence, sample_size=sample_size, status="ok")


def compute_metrics(
    tracks: dict[int, Track],
    frame_count: int,
    motion: dict | None = None,
) -> list[Metric]:
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
        activity_conf, activity_n = 0.6, len(speeds)
        consist_conf, consist_n = 0.55, len(speeds)
    else:
        movement_consistency = None
        activity_conf, activity_n = 0.0, 0
        consist_conf, consist_n = 0.0, 0

    if motion and movement_activity is None:
        movement_activity = float(motion["activity"])
        movement_consistency = float(motion["consistency"])
        activity_conf, activity_n = 0.7, int(motion["sample_size"])
        consist_conf, consist_n = 0.65, int(motion["sample_size"])

    direction_value = float(sum(changes)) if values else None
    direction_n = len(values)
    direction_conf = 0.7 if values else 0.0
    if motion and direction_value is None:
        direction_value = float(motion["spikes"])
        direction_n = int(motion["sample_size"])
        direction_conf = 0.6

    return [
        _metric("movement_activity", movement_activity, activity_conf, activity_n),
        _metric("movement_consistency", movement_consistency, consist_conf, consist_n),
        _metric("direction_changes", direction_value, direction_conf, direction_n),
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
        _metric(
            "screen_motion_spikes",
            float(motion["spikes"]) if motion else None,
            0.65 if motion else 0.0,
            int(motion["sample_size"]) if motion else 0,
        ),
        _metric(
            "still_moments",
            float(motion["stills"]) if motion else None,
            0.65 if motion else 0.0,
            int(motion["sample_size"]) if motion else 0,
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
        if activity.value <= 80:
            normalized_activity = min(activity.value / 18.0, 1.0)
        else:
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
