from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def format_timestamp(seconds: float | None) -> str:
    if seconds is None:
        return "N/A"
    total = max(0, int(seconds))
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def parse_timestamp(value: str | None) -> float | None:
    if value is None or value.strip() == "":
        return None
    parts = value.strip().split(":")
    if not parts or any(not part.isdigit() for part in parts):
        raise ValueError("Timestamp must look like MM:SS or HH:MM:SS")
    numbers = [int(part) for part in parts]
    if len(numbers) == 2:
        minutes, seconds = numbers
        return float(minutes * 60 + seconds)
    if len(numbers) == 3:
        hours, minutes, seconds = numbers
        return float(hours * 3600 + minutes * 60 + seconds)
    raise ValueError("Timestamp must look like MM:SS or HH:MM:SS")
