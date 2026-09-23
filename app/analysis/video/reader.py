from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import numpy as np


def iter_sampled_frames(
    path: Path,
    analysis_fps: float,
    source_fps: float | None = None,
) -> Iterator[tuple[float, np.ndarray]]:
    """Stream frames one at a time. Never load the full video into RAM."""
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError("OpenCV could not open the video")

    try:
        detected_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
        fps = source_fps or detected_fps or 30.0
        interval = max(1, int(round(fps / analysis_fps)))
        frame_index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index % interval == 0:
                timestamp = frame_index / fps
                yield timestamp, frame
            del frame
            frame_index += 1
    finally:
        capture.release()
