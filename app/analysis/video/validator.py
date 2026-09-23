from __future__ import annotations

from pathlib import Path

from app.analysis.video.metadata import ProbeError, VideoMetadata, probe_video

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm"}


class VideoValidationError(ValueError):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.user_message = message


def validate_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise VideoValidationError(
            f"Unsupported file type '{suffix or 'unknown'}'. Use .mp4, .mov, .mkv, or .webm."
        )
    return suffix


def validate_size(size_bytes: int, max_mb: int) -> None:
    max_bytes = max_mb * 1024 * 1024
    if size_bytes <= 0:
        raise VideoValidationError("The attachment is empty.")
    if size_bytes > max_bytes:
        raise VideoValidationError(
            f"Video is too large ({size_bytes / (1024 * 1024):.1f} MB). Max size is {max_mb} MB."
        )


def validate_video_file(path: Path, max_mb: int) -> VideoMetadata:
    if not path.exists():
        raise VideoValidationError("Video file was not found after download.")
    validate_extension(path.name)
    validate_size(path.stat().st_size, max_mb)
    try:
        return probe_video(path)
    except ProbeError as exc:
        raise VideoValidationError(str(exc)) from exc
