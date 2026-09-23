from app.analysis.metrics.engine import compute_metrics, compute_scores
from app.analysis.tracking.models import Track, TrackPoint


def _track(track_id: int, points: list[tuple[float, float, float]]) -> Track:
    track = Track(track_id=track_id, class_name="person")
    for ts, x, y in points:
        track.history.append(TrackPoint(ts, x, y, (x, y, x + 10, y + 10), 0.9))
    return track


def test_metrics_insufficient_without_tracks():
    metrics = compute_metrics({}, frame_count=0)
    assert all(metric.status == "insufficient_data" for metric in metrics)


def test_metrics_from_screen_motion_without_tracks():
    motion = {"activity": 9.2, "consistency": 0.7, "spikes": 11, "stills": 4, "sample_size": 40}
    metrics = {item.name: item for item in compute_metrics({}, frame_count=40, motion=motion)}
    assert metrics["movement_activity"].value == 9.2
    assert metrics["direction_changes"].value == 11
    scores = {item.name: item for item in compute_scores(list(metrics.values()))}
    assert scores["Movement"].value is not None


def test_metrics_and_scores_from_tracks():
    tracks = {
        1: _track(1, [(0, 0, 0), (1, 80, 0), (2, 90, 10)]),
        2: _track(2, [(0.5, 10, 10), (1.5, 20, 40)]),
    }
    metrics = compute_metrics(tracks, frame_count=3)
    by_name = {item.name: item for item in metrics}
    assert by_name["targets_detected"].value == 2
    assert by_name["direction_changes"].status == "ok"
    scores = {item.name: item for item in compute_scores(metrics)}
    assert scores["Aim"].status == "insufficient_data"
    assert scores["Positioning"].value is None
    assert scores["Cover Usage"].status == "insufficient_data"
