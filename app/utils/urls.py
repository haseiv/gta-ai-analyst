from __future__ import annotations

from urllib.parse import urlparse, unquote

from app.analysis.video.validator import SUPPORTED_EXTENSIONS, VideoValidationError
from app.utils.files import sanitize_filename

PLATFORM_HOSTS = (
    "youtube.com",
    "youtu.be",
    "youtube-nocookie.com",
    "drive.google.com",
    "docs.google.com",
    "rutube.ru",
)


def _host(parsed) -> str:
    return (parsed.hostname or "").lower().removeprefix("www.").removeprefix("m.")


def is_platform_url(url: str) -> bool:
    parsed = urlparse(url)
    host = _host(parsed)
    return any(host == item or host.endswith(f".{item}") for item in PLATFORM_HOSTS)


def is_direct_video_url(url: str) -> bool:
    parsed = urlparse(url)
    name = unquote(parsed.path.rsplit("/", 1)[-1]).lower()
    return any(name.endswith(ext) for ext in SUPPORTED_EXTENSIONS)


def parse_video_url(raw: str) -> tuple[str, str]:
    url = raw.strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise VideoValidationError("Нужна ссылка http/https: YouTube, Google Диск, Rutube или прямой файл.")
    if is_platform_url(url):
        host = _host(parsed)
        if "youtu" in host:
            return url, "youtube.mp4"
        if "google" in host:
            return url, "gdrive.mp4"
        return url, "rutube.mp4"
    name = sanitize_filename(unquote(parsed.path.rsplit("/", 1)[-1]) or "gameplay.mp4")
    suffix = name.rsplit(".", 1)
    if len(suffix) == 2 and f".{suffix[1].lower()}" in SUPPORTED_EXTENSIONS:
        return url, name
    raise VideoValidationError(
        "Ссылка не распознана. Нужен YouTube, Google Диск, Rutube или прямой .mp4/.mov/.mkv/.webm."
    )
