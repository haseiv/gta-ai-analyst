from __future__ import annotations

import re
from dataclasses import dataclass

import numpy as np

from app.analysis.events.models import EventType, GameEvent
from app.utils.logging import get_logger

logger = get_logger(__name__)

AMMO_RE = re.compile(r"^\s*(\d{1,3})\s*/\s*(\d{1,4})\s*$")
KILLS_RE = re.compile(r"^\s*(\d{1,3})\s*$")


@dataclass(frozen=True)
class HudSample:
    timestamp: float
    ammo: int | None
    reserve: int | None
    kills: int | None


def _crop(frame: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    height, width = frame.shape[:2]
    return frame[
        round(y1 * height / 1200) : round(y2 * height / 1200),
        round(x1 * width / 1920) : round(x2 * width / 1920),
    ]


def _recognized(ocr: object, image: np.ndarray) -> list[tuple[str, float]]:
    result, _ = ocr(image)
    return [(str(item[1]), float(item[2])) for item in (result or [])]


def _parse_ammo(words: list[tuple[str, float]]) -> tuple[int | None, int | None]:
    for word, confidence in words:
        match = AMMO_RE.fullmatch(word)
        if match and confidence >= 0.58:
            ammo, reserve = map(int, match.groups())
            if ammo <= 150 and reserve <= 9999:
                return ammo, reserve
    return None, None


def _parse_kills(words: list[tuple[str, float]]) -> int | None:
    for word, confidence in words:
        match = KILLS_RE.fullmatch(word)
        if match and confidence >= 0.50:
            return int(match.group(1))
    return None


class MajesticHudTracker:
    """Read only the fixed HUD fields in the supplied Majestic/FiveM layout.

    This does not detect players, damage, aim, or whether a particular enemy died.
    An ammo decrease is a shot observation, not a hit observation. OCR is sampled at
    most once per second to keep analysis bounded on long videos.
    """

    def __init__(self) -> None:
        self._ocr: object | None = None
        self._available = True
        self._recognized_brand = False
        self._last_brand_check = -5.0
        self._last_sample = -1.0
        self.samples: list[HudSample] = []

    @property
    def recognized_brand(self) -> bool:
        return self._recognized_brand

    def _engine(self) -> object | None:
        if self._ocr is not None:
            return self._ocr
        if not self._available:
            return None
        try:
            from rapidocr_onnxruntime import RapidOCR

            self._ocr = RapidOCR()
        except (ImportError, OSError) as exc:
            logger.warning("Majestic HUD OCR unavailable: %s", exc)
            self._available = False
        return self._ocr

    def update(self, timestamp: float, frame: np.ndarray) -> None:
        height, width = frame.shape[:2]
        if width < 1280 or height < 800 or not 1.57 <= width / height <= 1.63:
            return
        if not self._recognized_brand:
            if timestamp - self._last_brand_check < 5.0 or timestamp > 30.0:
                return
            self._last_brand_check = timestamp
            ocr = self._engine()
            if ocr is None:
                return
            brand = _recognized(ocr, _crop(frame, 1690, 0, 1920, 80))
            self._recognized_brand = any(
                "majestic" in text.lower() and confidence >= 0.7 for text, confidence in brand
            )
            if not self._recognized_brand:
                return
        if timestamp - self._last_sample < 0.9:
            return
        ocr = self._engine()
        if ocr is None:
            return
        self._last_sample = timestamp
        ammo, reserve = _parse_ammo(_recognized(ocr, _crop(frame, 1780, 125, 1900, 160)))
        kills = _parse_kills(_recognized(ocr, _crop(frame, 1780, 1092, 1890, 1140)))
        self.samples.append(HudSample(timestamp, ammo, reserve, kills))

    def finalize(self) -> tuple[dict, list[GameEvent]]:
        if not self._recognized_brand:
            return {"profile": None, "available": False}, []

        valid_ammo = [(sample.timestamp, sample.ammo) for sample in self.samples if sample.ammo is not None]
        valid_kills = [(sample.timestamp, sample.kills) for sample in self.samples if sample.kills is not None]
        if len(valid_ammo) < 3 or len(valid_kills) < 3:
            return {
                "profile": "majestic",
                "available": False,
                "ammo_samples": len(valid_ammo),
                "kill_samples": len(valid_kills),
            }, []

        shots = 0
        shot_times: list[tuple[float, int]] = []
        reload_times: list[float] = []
        for (previous_time, previous), (timestamp, current) in zip(valid_ammo, valid_ammo[1:]):
            delta = previous - current
            if 0 < timestamp - previous_time <= 2.5 and 0 < delta <= 40:
                shots += delta
                shot_times.append((timestamp, delta))
            elif 0 < timestamp - previous_time <= 2.5 and -delta >= 5:
                reload_times.append(timestamp)

        kill_times: list[tuple[float, int]] = []
        for (previous_time, previous), (timestamp, current) in zip(valid_kills, valid_kills[1:]):
            delta = current - previous
            if 0 < timestamp - previous_time <= 2.5 and 0 < delta <= 3:
                kill_times.append((timestamp, delta))

        events = [
            GameEvent(
                id=f"HUD-K{index:04d}",
                type=EventType.KILL,
                timestamp=round(timestamp, 2),
                confidence=0.65,
                metadata={"source": "majestic_hud_ocr", "count": count},
            )
            for index, (timestamp, count) in enumerate(kill_times, 1)
        ]

        bursts: list[tuple[float, float, int]] = []
        for timestamp, count in shot_times:
            if (
                bursts
                and timestamp - bursts[-1][1] <= 2.5
                and not any(bursts[-1][1] < reload <= timestamp for reload in reload_times)
            ):
                start, _, previous_count = bursts[-1]
                bursts[-1] = (start, timestamp, previous_count + count)
            else:
                bursts.append((timestamp, timestamp, count))
        without_kill = 0
        for index, (start, end, count) in enumerate(bursts, 1):
            if count < 5:
                continue
            if any(start <= timestamp <= end + 2.0 for timestamp, _ in kill_times):
                continue
            without_kill += 1
            events.append(
                GameEvent(
                    id=f"HUD-B{index:04d}",
                    type=EventType.BURST_NO_KILL,
                    timestamp=round(start, 2),
                    confidence=0.55,
                    metadata={
                        "source": "majestic_hud_ocr",
                        "end": round(end, 2),
                        "rounds_observed": count,
                        "meaning": "shots_without_kill_counter_increase; not proof of missed aim",
                    },
                )
            )

        return {
            "profile": "majestic",
            "available": True,
            "ammo_samples": len(valid_ammo),
            "kill_samples": len(valid_kills),
            "rounds_observed": shots,
            "kills_observed": sum(count for _, count in kill_times),
            "bursts_without_kill": without_kill,
        }, events
