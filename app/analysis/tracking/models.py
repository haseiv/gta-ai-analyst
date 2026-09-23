from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class TrackPoint:
    timestamp: float
    center_x: float
    center_y: float
    bbox: tuple[float, float, float, float]
    confidence: float


@dataclass(slots=True)
class Track:
    track_id: int
    class_name: str
    history: list[TrackPoint] = field(default_factory=list)

    @property
    def track_duration(self) -> float:
        if len(self.history) < 2:
            return 0.0
        return self.history[-1].timestamp - self.history[0].timestamp

    @property
    def visibility_duration(self) -> float:
        return self.track_duration

    @property
    def screen_distance(self) -> float:
        total = 0.0
        for prev, curr in zip(self.history, self.history[1:], strict=False):
            dx = curr.center_x - prev.center_x
            dy = curr.center_y - prev.center_y
            total += (dx * dx + dy * dy) ** 0.5
        return total

    @property
    def average_screen_speed(self) -> float:
        duration = self.track_duration
        if duration <= 0:
            return 0.0
        return self.screen_distance / duration

    @property
    def direction_changes(self) -> int:
        if len(self.history) < 3:
            return 0
        changes = 0
        prev_angle = None
        for prev, curr in zip(self.history, self.history[1:], strict=False):
            dx = curr.center_x - prev.center_x
            dy = curr.center_y - prev.center_y
            if abs(dx) < 1 and abs(dy) < 1:
                continue
            angle = _atan2(dy, dx)
            if prev_angle is not None:
                delta = abs(angle - prev_angle)
                if delta > 180:
                    delta = 360 - delta
                if delta >= 45:
                    changes += 1
            prev_angle = angle
        return changes

    def summary(self) -> dict:
        return {
            "track_id": self.track_id,
            "class_name": self.class_name,
            "points": len(self.history),
            "track_duration": round(self.track_duration, 3),
            "visibility_duration": round(self.visibility_duration, 3),
            "screen_distance": round(self.screen_distance, 2),
            "average_screen_speed": round(self.average_screen_speed, 2),
            "direction_changes": self.direction_changes,
            "first_seen": self.history[0].timestamp if self.history else None,
            "last_seen": self.history[-1].timestamp if self.history else None,
        }


def _atan2(y: float, x: float) -> float:
    import math

    return math.degrees(math.atan2(y, x))
