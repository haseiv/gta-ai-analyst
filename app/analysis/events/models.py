from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EventType(StrEnum):
    OBJECT_APPEARED = "OBJECT_APPEARED"
    OBJECT_DISAPPEARED = "OBJECT_DISAPPEARED"
    RAPID_MOVEMENT = "RAPID_MOVEMENT"
    DIRECTION_CHANGE = "DIRECTION_CHANGE"
    MULTIPLE_TARGETS_VISIBLE = "MULTIPLE_TARGETS_VISIBLE"
    LONG_TARGET_VISIBILITY = "LONG_TARGET_VISIBILITY"
    PLAYER_DEATH = "PLAYER_DEATH"
    DAMAGE_RECEIVED = "DAMAGE_RECEIVED"
    ENEMY_DETECTED = "ENEMY_DETECTED"
    SHOT_FIRED = "SHOT_FIRED"
    KILL = "KILL"
    KILL_FEED_ENTRY = "KILL_FEED_ENTRY"
    BURST_NO_KILL = "BURST_NO_KILL"
    COVER_EXIT = "COVER_EXIT"
    VEHICLE_ENTER = "VEHICLE_ENTER"
    VEHICLE_EXIT = "VEHICLE_EXIT"


class GameEvent(BaseModel):
    id: str
    type: EventType
    timestamp: float
    confidence: float
    metadata: dict[str, Any] = Field(default_factory=dict)
