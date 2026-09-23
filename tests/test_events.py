from app.analysis.detection.base import Detection
from app.analysis.events.engine import EventEngine
from app.analysis.events.models import EventType
from app.analysis.tracking.models import Track, TrackPoint


def _det(track_id: int, name: str = "person") -> Detection:
    return Detection(0, name, 0.9, 1, 1, 10, 10, 5, 5, track_id)


def test_appear_disappear_and_multiple_targets():
    engine = EventEngine()
    engine.on_frame(0.0, [_det(1), _det(2), _det(3)])
    engine.on_frame(1.0, [_det(1)])
    tracks = {
        1: Track(
            1,
            "person",
            [
                TrackPoint(0, 0, 0, (0, 0, 1, 1), 0.9),
                TrackPoint(4, 500, 0, (0, 0, 1, 1), 0.9),
            ],
        )
    }
    events = engine.finalize(tracks)
    types = {event.type for event in events}
    assert EventType.OBJECT_APPEARED in types
    assert EventType.OBJECT_DISAPPEARED in types
    assert EventType.MULTIPLE_TARGETS_VISIBLE in types
    assert EventType.LONG_TARGET_VISIBILITY in types
    assert EventType.PLAYER_DEATH not in types
    assert EventType.KILL not in types
