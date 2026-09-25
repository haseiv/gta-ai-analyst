from __future__ import annotations

import subprocess
from pathlib import Path

from app.utils.logging import get_logger

logger = get_logger(__name__)


def decodes_first_frame(path: Path) -> bool:
    import cv2

    capture = cv2.VideoCapture(str(path))
    try:
        if not capture.isOpened():
            return False
        ok, frame = capture.read()
        return bool(ok and frame is not None and frame.size)
    finally:
        capture.release()


def ensure_cv_compatible(path: Path, max_bytes: int) -> Path:
    """Transcode a downloaded video only when OpenCV cannot decode its first frame."""
    if decodes_first_frame(path):
        return path

    converted = path.with_name(f"{path.stem}_cv.mp4")
    converted.unlink(missing_ok=True)
    logger.warning("OpenCV cannot decode downloaded video; transcoding to H.264 path=%s", path.name)
    command = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(converted),
    ]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=1800, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        converted.unlink(missing_ok=True)
        raise RuntimeError("FFmpeg не смог подготовить видео для анализа.") from exc
    if completed.returncode != 0 or not converted.is_file() or converted.stat().st_size <= 0:
        converted.unlink(missing_ok=True)
        logger.error("H.264 transcode failed: %s", completed.stderr[-1000:])
        raise RuntimeError("FFmpeg не смог перекодировать видео в H.264 для анализа.")
    if converted.stat().st_size > max_bytes:
        converted.unlink(missing_ok=True)
        raise RuntimeError("Видео после перекодировки превышает лимит размера.")
    if not decodes_first_frame(converted):
        converted.unlink(missing_ok=True)
        raise RuntimeError("OpenCV не смог прочитать видео даже после перекодировки в H.264.")
    path.unlink(missing_ok=True)
    logger.info("H.264 compatibility transcode complete path=%s", converted.name)
    return converted
