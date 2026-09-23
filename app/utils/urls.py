from __future__ import annotations

from urllib.parse import urlparse, unquote

from app.analysis.video.validator import SUPPORTED_EXTENSIONS, VideoValidationError
from app.utils.files import sanitize_filename


def parse_video_url(raw: str) -> tuple[str, str]:
    url = raw.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise VideoValidationError("Нужна прямая ссылка http/https на видео.")
    name = sanitize_filename(unquote(parsed.path.rsplit("/", 1)[-1]) or "gameplay.mp4")
    suffix = name.rsplit(".", 1)
    if len(suffix) == 2 and f".{suffix[1].lower()}" in SUPPORTED_EXTENSIONS:
        return url, name
    return url, "gameplay.mp4"
