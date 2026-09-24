from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

import numpy as np


@dataclass(slots=True)
class Detection:
    class_id: int
    class_name: str
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    center_x: float
    center_y: float
    track_id: int | None = None


class BaseDetector(ABC):
    """Swap default.pt for a custom GTA model without changing the pipeline."""

    @property
    def gameplay_capable(self) -> bool:
        """Whether detections are trained well enough to drive gameplay claims."""
        return True

    @property
    def profile(self) -> str:
        return "custom_gameplay"

    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[Detection]:
        raise NotImplementedError

    def track(self, frame: np.ndarray) -> list[Detection]:
        return self.detect(frame)

    def reset(self) -> None:
        return None
