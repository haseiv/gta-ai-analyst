from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class ProbeError(RuntimeError):
    pass


@dataclass(slots=True)
class VideoMetadata:
    duration: float
    width: int
    height: int
    fps: float
    codec: str


def _parse_frame_rate(value: str | None) -> float:
    if not value or value == "0/0":
        return 0.0
    if "/" in value:
        num, den = value.split("/", 1)
        denominator = float(den)
        if denominator == 0:
            return 0.0
        return float(num) / denominator
    return float(value)


def probe_video(path: Path) -> VideoMetadata:
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        raise ProbeError("ffprobe не установлен или не найден в PATH")

    command = [
        ffprobe,
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,codec_name,codec_type",
        "-show_entries",
        "format=duration,format_name",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("ffprobe слишком долго читал метаданные видео") from exc

    if completed.returncode != 0:
        raise ProbeError("ffprobe не смог прочитать этот файл как видео")

    try:
        payload = json.loads(completed.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise ProbeError("ffprobe вернул некорректные метаданные") from exc

    streams = payload.get("streams") or []
    video_stream = next((item for item in streams if item.get("codec_type") == "video"), None)
    if video_stream is None and streams:
        video_stream = streams[0]
    if video_stream is None:
        raise ProbeError("В файле нет видеопотока")

    fmt = payload.get("format") or {}
    duration_raw = fmt.get("duration")
    try:
        duration = float(duration_raw)
    except (TypeError, ValueError) as exc:
        raise ProbeError("Длительность видео отсутствует или некорректна") from exc

    width = int(video_stream.get("width") or 0)
    height = int(video_stream.get("height") or 0)
    fps = _parse_frame_rate(video_stream.get("avg_frame_rate"))
    codec = str(video_stream.get("codec_name") or "unknown")

    if duration <= 0 or width <= 0 or height <= 0:
        raise ProbeError("Метаданные видео неполные (длительность или разрешение)")

    return VideoMetadata(duration=duration, width=width, height=height, fps=fps, codec=codec)
