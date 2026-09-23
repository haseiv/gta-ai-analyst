from __future__ import annotations

from pathlib import Path


def read_head(path: Path, size: int = 64) -> bytes:
    with path.open("rb") as handle:
        return handle.read(size)


def is_html_or_text(data: bytes) -> bool:
    sample = data.lstrip().lower()
    return sample.startswith((b"<", b"<!doctype", b"{", b"<!"))


def is_webpage_payload(path: Path) -> bool:
    return is_html_or_text(read_head(path))
