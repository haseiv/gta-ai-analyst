from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np

from app.analysis.events.models import EventType, GameEvent
from app.analysis.hud.majestic import _parse_ammo, _recognized
from app.utils.logging import get_logger

logger = get_logger(__name__)
NAME_RE = re.compile(r"^[A-Za-zА-Яа-яЁё][A-Za-zА-Яа-яЁё0-9_. -]{1,35}$")
TIMER_RE = re.compile(r"^\d{1,2}:\d{2}$")


def _crop(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    height, width = frame.shape[:2]
    cropped = frame[
        round(y1 * height / 1440) : round(y2 * height / 1440),
        round(x1 * width / 2560) : round(x2 * width / 2560),
    ]
    if width < 2560:
        cropped = cv2.resize(cropped, (x2 - x1, y2 - y1), interpolation=cv2.INTER_CUBIC)
    return cropped


def _name_key(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())


def _feed_pairs(result: list | None) -> list[tuple[str, str]]:
    """Pair OCR names on opposite sides of a weapon icon in the kill feed."""
    left: list[tuple[float, str]] = []
    right: list[tuple[float, str]] = []
    for box, raw_text, raw_confidence in result or []:
        name = str(raw_text).strip()
        if float(raw_confidence) < 0.65 or not NAME_RE.fullmatch(name):
            continue
        x = sum(point[0] for point in box) / 4
        y = sum(point[1] for point in box) / 4
        if x < 190:
            left.append((y, name))
        elif x > 220:
            right.append((y, name))
    pairs = []
    for left_y, killer in left:
        close = [(abs(left_y - right_y), victim) for right_y, victim in right]
        if close:
            distance, victim = min(close)
            if distance <= 12:
                pairs.append((killer, victim))
    return pairs


@dataclass(frozen=True)
class CaptSample:
    timestamp: float
    ammo: int | None
    reserve: int | None


class CaptHudTracker:
    """Evidence-only observer for the 16:9 Majestic capt HUD.

    A feed entry is attributed to the submitting player only when their in-game
    name was supplied. No target or crosshair tracking is inferred from the HUD.
    """

    def __init__(self, player_name: str | None = None) -> None:
        self.player_name = (player_name or "").strip()
        self._ocr: object | None = None
        self._available = True
        self._recognized_hud = False
        self._last_brand_check = -5.0
        self._last_sample = -1.0
        self.samples: list[CaptSample] = []
        self.feed: list[tuple[float, str, str]] = []
        self._last_seen: dict[tuple[str, str], float] = {}
        self._feed_initialized = False

    def _engine(self) -> object | None:
        if self._ocr is not None:
            return self._ocr
        if not self._available:
            return None
        try:
            from rapidocr_onnxruntime import RapidOCR

            self._ocr = RapidOCR()
        except (ImportError, OSError) as exc:
            logger.warning("Capt HUD OCR unavailable: %s", exc)
            self._available = False
        return self._ocr

    def update(self, timestamp: float, frame: np.ndarray) -> None:
        height, width = frame.shape[:2]
        if width < 1280 or height < 720 or not 1.75 <= width / height <= 1.80:
            return
        if not self._recognized_hud:
            if timestamp - self._last_brand_check < 5.0:
                return
            self._last_brand_check = timestamp
            ocr = self._engine()
            if ocr is None:
                return
            corner = _recognized(ocr, _crop(frame, 2300, 15, 2560, 140))
            scoreboard = _recognized(ocr, _crop(frame, 1080, 20, 1500, 150))
            self._recognized_hud = (
                any("majestic" in text.casefold() and conf >= 0.7 for text, conf in corner)
                and any(text.strip().upper() == "MCL" and conf >= 0.6 for text, conf in corner)
                and any(TIMER_RE.fullmatch(text.strip()) and conf >= 0.6 for text, conf in scoreboard)
            )
            if not self._recognized_hud:
                return
        if timestamp - self._last_sample < 0.9:
            return
        ocr = self._engine()
        if ocr is None:
            return
        self._last_sample = timestamp
        ammo, reserve = _parse_ammo(_recognized(ocr, _crop(frame, 2410, 155, 2545, 198)))
        self.samples.append(CaptSample(timestamp, ammo, reserve))
        if ammo is None:
            return

        result, _ = ocr(_crop(frame, 2200, 205, 2560, 460))
        for killer, victim in _feed_pairs(result):
            key = (_name_key(killer), _name_key(victim))
            if self._feed_initialized and timestamp - self._last_seen.get(key, -30.0) > 15.0:
                self.feed.append((timestamp, killer, victim))
            self._last_seen[key] = timestamp
        self._feed_initialized = True

    def finalize(self) -> tuple[dict, list[GameEvent]]:
        if not self._recognized_hud:
            return {"profile": None, "available": False}, []
        valid_ammo = [(sample.timestamp, sample.ammo) for sample in self.samples if sample.ammo is not None]
        if len(valid_ammo) < 3:
            return {"profile": "majestic_capt", "available": False, "ammo_samples": len(valid_ammo)}, []

        shot_times: list[tuple[float, int]] = []
        for (before_time, before), (timestamp, after) in zip(valid_ammo, valid_ammo[1:]):
            delta = before - after
            if 0 < timestamp - before_time <= 2.5 and 0 < delta <= 40:
                shot_times.append((timestamp, delta))

        events: list[GameEvent] = []
        rated: list[dict] = []
        player_key = _name_key(self.player_name)
        for index, (timestamp, killer, victim) in enumerate(self.feed, 1):
            own_kill = bool(player_key and _name_key(killer) == player_key)
            if player_key and not own_kill:
                continue
            rounds = sum(
                count for shot_time, count in shot_times if timestamp - 4.0 <= shot_time <= timestamp
            )
            events.append(
                GameEvent(
                    id=f"CAPT-K{index:04d}",
                    type=EventType.KILL if own_kill else EventType.KILL_FEED_ENTRY,
                    timestamp=round(timestamp, 2),
                    confidence=0.75 if own_kill else 0.65,
                    metadata={
                        "source": "majestic_capt_hud_ocr",
                        "killer": killer,
                        "victim": victim,
                        "player_confirmed": own_kill,
                        "rounds_in_previous_4s": rounds,
                    },
                )
            )
            if own_kill and rounds > 0:
                # A narrow outcome/efficiency rubric for one confirmed engagement,
                # not a general aim, movement, or positioning skill rating.
                score = max(5.0, min(9.0, 10.0 - max(rounds - 4, 0) * 0.15))
                rated.append({
                    "timestamp": round(timestamp, 2),
                    "victim": victim,
                    "rounds_in_previous_4s": rounds,
                    "score": round(score, 1),
                })

        return {
            "profile": "majestic_capt",
            "available": True,
            "ammo_samples": len(valid_ammo),
            "rounds_observed": sum(count for _, count in shot_times),
            "kill_feed_entries": len(self.feed),
            "player_name": self.player_name or None,
            "player_kills": sum(1 for _, killer, _ in self.feed if player_key and _name_key(killer) == player_key)
            if player_key else None,
            "rated_engagements": rated,
            "finish_score": round(sum(item["score"] for item in rated) / len(rated), 1) if rated else None,
        }, events
