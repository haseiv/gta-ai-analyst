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


def _infer_player_name(names: list[str]) -> str | None:
    """Recover the local name from repeated, sometimes edge-cropped OCR reads."""
    candidates = [(name, _name_key(name)) for name in names if len(_name_key(name)) >= 4]
    if not candidates:
        return None
    name, _ = max(
        candidates,
        key=lambda item: (
            sum(
                1
                for _, other in candidates
                if item[1] in other or other in item[1]
            ),
            len(item[1]),
        ),
    )
    return name


def _same_ocr_name(left: str, right: str) -> bool:
    left_key, right_key = _name_key(left), _name_key(right)
    if min(len(left_key), len(right_key)) < 4:
        return False
    return left_key in right_key or right_key in left_key


def _feed_pairs(result: list | None) -> list[tuple[str, str]]:
    """Pair OCR names on opposite sides of a weapon icon in the kill feed."""
    return [(killer, victim) for killer, victim, _ in _feed_rows(result)]


def _feed_rows(result: list | None) -> list[tuple[str, str, float]]:
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
    pairs: list[tuple[str, str, float]] = []
    for left_y, killer in left:
        close = [(abs(left_y - right_y), victim) for right_y, victim in right]
        if close:
            distance, victim = min(close)
            if distance <= 12:
                pairs.append((killer, victim, left_y))
    return pairs


def _has_player_highlight(image: np.ndarray, row_y: float) -> bool:
    """Majestic outlines the local player's kill-feed row in red."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    red = cv2.bitwise_or(
        cv2.inRange(hsv, (0, 70, 50), (12, 255, 255)),
        cv2.inRange(hsv, (170, 70, 50), (179, 255, 255)),
    )
    mask = red > 0
    row = int(round(row_y))
    top_start, top_end = max(0, row - 40), max(0, row - 10)
    bottom_start, bottom_end = min(mask.shape[0] - 1, row + 10), min(mask.shape[0], row + 45)
    if top_start >= top_end or bottom_start >= bottom_end:
        return False
    top_coverage = max(float(mask[y].mean()) for y in range(top_start, top_end))
    bottom_coverage = max(float(mask[y].mean()) for y in range(bottom_start, bottom_end))
    band_start, band_end = max(0, row - 40), min(mask.shape[0], row + 45)
    dense_rows = sum(float(mask[y].mean()) >= 0.60 for y in range(band_start, band_end))
    return top_coverage >= 0.85 and bottom_coverage >= 0.85 and dense_rows <= 10


@dataclass(frozen=True)
class CaptSample:
    timestamp: float
    ammo: int | None
    reserve: int | None


class CaptHudTracker:
    """Evidence-only observer for the 16:9 Majestic combat HUD.

    Local kills are identified by the red row outline in the kill feed. An
    MCL scoreboard is optional because deathmatch and other combat modes use
    the same ammo and kill-feed widgets without that scoreboard. No nickname
    input or target tracking is required or inferred.
    """

    def __init__(self) -> None:
        self._ocr: object | None = None
        self._available = True
        self._recognized_hud = False
        self._hud_variant: str | None = None
        self._combat_signature_hits = 0
        self._last_brand_check = -5.0
        self._last_sample = -1.0
        self.samples: list[CaptSample] = []
        self.feed: list[tuple[float, str, str, bool]] = []
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
        detected_ammo: tuple[int | None, int | None] | None = None
        if not self._recognized_hud:
            if timestamp - self._last_brand_check < 5.0:
                return
            self._last_brand_check = timestamp
            ocr = self._engine()
            if ocr is None:
                return
            corner = _recognized(ocr, _crop(frame, 2300, 15, 2560, 140))
            detected_ammo = _parse_ammo(_recognized(ocr, _crop(frame, 2410, 155, 2545, 198)))
            scoreboard = _recognized(ocr, _crop(frame, 1080, 20, 1500, 150))
            has_brand = any("majestic" in text.casefold() and conf >= 0.7 for text, conf in corner)
            has_mcl = any(text.strip().upper() == "MCL" and conf >= 0.6 for text, conf in corner)
            has_timer = any(TIMER_RE.fullmatch(text.strip()) and conf >= 0.6 for text, conf in scoreboard)
            if detected_ammo[0] is not None:
                self._combat_signature_hits += 1
            else:
                self._combat_signature_hits = 0
            # Majestic deathmatch has no MCL timer. The brand plus a valid ammo
            # counter is a strong signature. Two consecutive valid ammo reads
            # are also accepted because YouTube compression can blur the logo.
            self._recognized_hud = detected_ammo[0] is not None and (
                has_brand or self._combat_signature_hits >= 2
            )
            if not self._recognized_hud:
                return
            self._hud_variant = "mcl" if has_mcl and has_timer else "deathmatch_or_other"
        if timestamp - self._last_sample < 0.9:
            return
        ocr = self._engine()
        if ocr is None:
            return
        self._last_sample = timestamp
        ammo, reserve = detected_ammo or _parse_ammo(
            _recognized(ocr, _crop(frame, 2410, 155, 2545, 198))
        )
        self.samples.append(CaptSample(timestamp, ammo, reserve))
        if ammo is None:
            return

        feed_image = _crop(frame, 2200, 205, 2560, 460)
        result, _ = ocr(feed_image)
        for killer, victim, row_y in _feed_rows(result):
            key = (_name_key(killer), _name_key(victim))
            if self._feed_initialized and timestamp - self._last_seen.get(key, -30.0) > 15.0:
                self.feed.append((timestamp, killer, victim, _has_player_highlight(feed_image, row_y)))
            self._last_seen[key] = timestamp
        self._feed_initialized = True

    def finalize(self) -> tuple[dict, list[GameEvent]]:
        if not self._recognized_hud:
            return {"profile": None, "available": False}, []
        valid_ammo = [(sample.timestamp, sample.ammo) for sample in self.samples if sample.ammo is not None]
        if len(valid_ammo) < 3:
            return {"profile": "majestic_capt", "available": False, "ammo_samples": len(valid_ammo)}, []

        shot_times: list[tuple[float, int]] = []
        reload_times: list[float] = []
        for (before_time, before), (timestamp, after) in zip(valid_ammo, valid_ammo[1:]):
            delta = before - after
            if 0 < timestamp - before_time <= 2.5 and 0 < delta <= 40:
                shot_times.append((timestamp, delta))
            elif 0 < timestamp - before_time <= 2.5 and -delta >= 5:
                reload_times.append(timestamp)

        events: list[GameEvent] = []
        rated: list[dict] = []
        own_kill_times: list[float] = []
        highlighted_names = [killer for _, killer, _, highlighted in self.feed if highlighted]
        inferred_player = _infer_player_name(highlighted_names)
        recent_victims: list[tuple[float, str]] = []
        for index, (timestamp, killer, victim, highlighted) in enumerate(self.feed, 1):
            if not highlighted or inferred_player is None or not _same_ocr_name(killer, inferred_player):
                continue
            # A feed row remains visible for several sampled frames. OCR often
            # clips its first letters as it moves, so exact-string dedupe alone
            # would count one kill two or three times.
            if any(
                timestamp - previous_time <= 4.0 and _same_ocr_name(victim, previous_victim)
                for previous_time, previous_victim in recent_victims
            ):
                continue
            recent_victims = [
                (previous_time, previous_victim)
                for previous_time, previous_victim in recent_victims
                if timestamp - previous_time <= 4.0
            ]
            recent_victims.append((timestamp, victim))
            own_kill_times.append(timestamp)
            rounds = sum(
                count for shot_time, count in shot_times if timestamp - 4.0 <= shot_time <= timestamp
            )
            events.append(
                GameEvent(
                    id=f"CAPT-K{index:04d}",
                    type=EventType.KILL,
                    timestamp=round(timestamp, 2),
                    confidence=0.85,
                    metadata={
                        "source": "majestic_capt_hud_ocr",
                        "killer": killer,
                        "victim": victim,
                        "player_confirmed": True,
                        "player_attribution": "red_feed_highlight",
                        "rounds_in_previous_4s": rounds,
                    },
                )
            )
            if rounds > 0:
                # A narrow outcome/efficiency rubric for one confirmed engagement,
                # not a general aim, movement, or positioning skill rating.
                score = max(5.0, min(9.0, 10.0 - max(rounds - 4, 0) * 0.15))
                rated.append({
                    "timestamp": round(timestamp, 2),
                    "victim": victim,
                    "rounds_in_previous_4s": rounds,
                    "score": round(score, 1),
                })

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

        unconverted = []
        for index, (start, end, count) in enumerate(bursts, 1):
            if count < 8 or any(start <= kill <= end + 2.0 for kill in own_kill_times):
                continue
            unconverted.append({"timestamp": round(start, 2), "rounds": count})
            events.append(
                GameEvent(
                    id=f"CAPT-B{index:04d}",
                    type=EventType.BURST_NO_KILL,
                    timestamp=round(start, 2),
                    confidence=0.50,
                    metadata={
                        "source": "majestic_capt_hud_ocr",
                        "end": round(end, 2),
                        "rounds_observed": count,
                        "meaning": "shooting_without_local_kill_feed_highlight; review candidate",
                    },
                )
            )

        return {
            "profile": "majestic_capt",
            "hud_variant": self._hud_variant,
            "available": True,
            "ammo_samples": len(valid_ammo),
            "rounds_observed": sum(count for _, count in shot_times),
            "kill_feed_entries": len(self.feed),
            "player_name": inferred_player,
            "player_name_source": "red_feed_highlight" if inferred_player else None,
            "player_kills": len(own_kill_times),
            "rated_engagements": rated,
            "unconverted_bursts": unconverted,
            "finish_score": round(sum(item["score"] for item in rated) / len(rated), 1) if rated else None,
        }, events
