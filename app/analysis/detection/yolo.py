from __future__ import annotations

from pathlib import Path

import numpy as np

from app.analysis.detection.base import BaseDetector, Detection
from app.utils.logging import get_logger

logger = get_logger(__name__)

_MODEL = None
_MODEL_PATH: str | None = None


def _load_model(model_path: str):
    global _MODEL, _MODEL_PATH
    if _MODEL is not None and _MODEL_PATH == model_path:
        return _MODEL
    from ultralytics import YOLO

    resolved = Path(model_path)
    if not resolved.exists():
        raise FileNotFoundError(
            f"YOLO model not found at {model_path}. Place models/default.pt or set YOLO_MODEL_PATH."
        )
    logger.info("Loading YOLO model from %s", resolved)
    _MODEL = YOLO(str(resolved))
    _MODEL_PATH = model_path
    return _MODEL


class YOLODetector(BaseDetector):
    def __init__(self, model_path: str) -> None:
        self.model_path = model_path
        self.model = _load_model(model_path)

    def detect(self, frame: np.ndarray) -> list[Detection]:
        results = self.model.predict(frame, verbose=False)
        return self._to_detections(results)

    def track(self, frame: np.ndarray) -> list[Detection]:
        results = self.model.track(
            frame,
            persist=True,
            verbose=False,
            tracker="bytetrack.yaml",
        )
        return self._to_detections(results)

    def reset(self) -> None:
        predictor = getattr(self.model, "predictor", None)
        if predictor is not None:
            predictor.trackers = []
            predictor.vid_path = [None]

    def _to_detections(self, results) -> list[Detection]:
        detections: list[Detection] = []
        if not results:
            return detections
        result = results[0]
        boxes = getattr(result, "boxes", None)
        if boxes is None:
            return detections
        names = result.names or {}
        xyxy = boxes.xyxy.tolist() if boxes.xyxy is not None else []
        confs = boxes.conf.tolist() if boxes.conf is not None else []
        clss = boxes.cls.tolist() if boxes.cls is not None else []
        ids = boxes.id.tolist() if getattr(boxes, "id", None) is not None else [None] * len(xyxy)
        for box, conf, cls, track_id in zip(xyxy, confs, clss, ids, strict=False):
            x1, y1, x2, y2 = (float(v) for v in box)
            class_id = int(cls)
            detections.append(
                Detection(
                    class_id=class_id,
                    class_name=str(names.get(class_id, str(class_id))),
                    confidence=float(conf),
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    center_x=(x1 + x2) / 2,
                    center_y=(y1 + y2) / 2,
                    track_id=int(track_id) if track_id is not None else None,
                )
            )
        return detections
