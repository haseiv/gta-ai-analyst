from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO

import numpy as np


def _read_exact(stream: BinaryIO, size: int) -> bytes:
    chunks: list[bytes] = []
    remaining = size
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _scaled_size(width: int, height: int, max_width: int = 1280) -> tuple[int, int]:
    if width <= max_width:
        return width - width % 2, height - height % 2
    scaled_height = round(height * max_width / width)
    return max_width, max(2, scaled_height - scaled_height % 2)


def _iter_ffmpeg_frames(
    ffmpeg: str,
    path: Path,
    analysis_fps: float,
    width: int,
    height: int,
) -> Iterator[tuple[float, np.ndarray]]:
    output_width, output_height = _scaled_size(width, height)
    frame_bytes = output_width * output_height * 3
    command = [
        ffmpeg,
        "-nostdin",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(path),
        "-an",
        "-sn",
        "-dn",
        "-vf",
        f"fps={analysis_fps},scale={output_width}:{output_height}",
        "-pix_fmt",
        "bgr24",
        "-f",
        "rawvideo",
        "pipe:1",
    ]
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    frame_index = 0
    try:
        assert process.stdout is not None
        while True:
            raw = _read_exact(process.stdout, frame_bytes)
            if not raw:
                break
            if len(raw) != frame_bytes:
                break
            frame = np.frombuffer(raw, dtype=np.uint8).reshape(output_height, output_width, 3)
            yield frame_index / analysis_fps, frame
            frame_index += 1
    finally:
        if process.stdout is not None:
            process.stdout.close()
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=10)
    if frame_index == 0:
        raise RuntimeError("FFmpeg decoded zero frames")


def iter_sampled_frames(
    path: Path,
    analysis_fps: float,
    source_fps: float | None = None,
) -> Iterator[tuple[float, np.ndarray]]:
    """Stream only sampled, downscaled frames and never load the full video into RAM."""
    import cv2

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError("OpenCV could not open the video")

    width = int(capture.get(getattr(cv2, "CAP_PROP_FRAME_WIDTH", 3)) or 0)
    height = int(capture.get(getattr(cv2, "CAP_PROP_FRAME_HEIGHT", 4)) or 0)
    detected_fps = float(capture.get(cv2.CAP_PROP_FPS) or 0)
    capture.release()

    # Let FFmpeg perform temporal sampling and scaling in its optimized decoder.
    # The previous OpenCV loop decoded and converted every 60 FPS source frame,
    # even though only 0.5-5 FPS were actually analyzed.
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg and width > 0 and height > 0:
        yield from _iter_ffmpeg_frames(ffmpeg, path, analysis_fps, width, height)
        return

    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError("OpenCV could not open the video")

    try:
        fps = source_fps or detected_fps or 30.0
        interval = max(1, int(round(fps / analysis_fps)))
        frame_index = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                if frame_index == 0:
                    raise RuntimeError("OpenCV decoded zero frames")
                break
            if frame_index % interval == 0:
                timestamp = frame_index / fps
                yield timestamp, frame
            del frame
            frame_index += 1
    finally:
        capture.release()
