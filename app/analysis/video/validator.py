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
            f"Формат «{suffix or 'неизвестный'}» не поддерживается. Нужен .mp4, .mov, .mkv или .webm."
        )
    return suffix


def validate_size(size_bytes: int, max_mb: int) -> None:
    max_bytes = max_mb * 1024 * 1024
    if size_bytes <= 0:
        raise VideoValidationError("Файл пустой.")
    if size_bytes > max_bytes:
        raise VideoValidationError(
            f"Видео слишком большое ({size_bytes / (1024 * 1024):.1f} МБ). Максимум {max_mb} МБ."
        )


def validate_video_file(path: Path, max_mb: int) -> VideoMetadata:
    if not path.exists():
        raise VideoValidationError("После скачивания файл не найден.")
    validate_extension(path.name)
    validate_size(path.stat().st_size, max_mb)
    try:
        return probe_video(path)
    except ProbeError as exc:
        raise VideoValidationError(str(exc)) from exc
