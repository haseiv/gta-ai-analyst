from __future__ import annotations

import cv2
import numpy as np


class ScreenMotionAnalyzer:
    """Compare consecutive sampled frames. Never keeps the video in RAM."""

    def __init__(self) -> None:
        self._prev: np.ndarray | None = None
        self.samples: list[tuple[float, float]] = []

    def update(self, timestamp: float, frame: np.ndarray) -> None:
        small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA)
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        del small
        if self._prev is not None:
            score = float(cv2.absdiff(self._prev, gray).mean())
            self.samples.append((timestamp, score))
        self._prev = gray

    def stats(self) -> dict | None:
        if len(self.samples) < 3:
            return None
        scores = [item[1] for item in self.samples]
        mean = sum(scores) / len(scores)
        variance = sum((item - mean) ** 2 for item in scores) / len(scores)
        std = variance**0.5
        spike_cut = mean + max(std * 1.4, 6.0)
        still_cut = max(mean * 0.35, 1.5)
        spikes = [(ts, value) for ts, value in self.samples if value >= spike_cut]
        stills = [(ts, value) for ts, value in self.samples if value <= still_cut]
        consistency = 1.0 / (1.0 + variance / max(mean, 1.0))
        return {
            "activity": mean,
            "consistency": consistency,
            "spikes": len(spikes),
            "stills": len(stills),
            "sample_size": len(scores),
            "spike_times": [ts for ts, _ in spikes[:12]],
            "still_times": [ts for ts, _ in stills[:12]],
        }
