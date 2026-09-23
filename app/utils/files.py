from __future__ import annotations

import re
import uuid
from pathlib import Path

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(name: str, fallback: str = "gameplay.mp4") -> str:
    cleaned = Path(name).name
    cleaned = _UNSAFE.sub("_", cleaned).strip("._")
    if not cleaned or cleaned in {".", ".."}:
        return fallback
    return cleaned[:120]


def unique_temp_path(directory: Path, original_name: str) -> Path:
    safe = sanitize_filename(original_name)
    return directory / f"{uuid.uuid4().hex}_{safe}"
