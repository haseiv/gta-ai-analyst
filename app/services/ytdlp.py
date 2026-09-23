from __future__ import annotations

from pathlib import Path

from app.utils.logging import get_logger

logger = get_logger(__name__)

_FORMATS = (
    "bv*[height<=720]+ba/b[height<=720]",
    "bv*[height<=480]+ba/b[height<=480]",
    "bv*[height<=360]+ba/b[height<=360]",
    "worst",
)


class VideoDownloadError(RuntimeError):
    pass


def download_platform_video(url: str, dest: Path, max_bytes: int) -> Path:
    """Download YouTube / Google Drive / Rutube at 720p or lower. Writes to disk only."""
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError, UnsupportedError

    dest.parent.mkdir(parents=True, exist_ok=True)
    template = dest.with_suffix("")
    last_error: Exception | None = None

    for fmt in _FORMATS:
        _cleanup_partial(template)
        logger.info("yt-dlp format=%s", fmt)

        def hook(info: dict) -> None:
            downloaded = int(info.get("downloaded_bytes") or 0)
            if downloaded > max_bytes:
                raise VideoDownloadError(_too_large(max_bytes))

        opts = {
            "outtmpl": str(template) + ".%(ext)s",
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "noprogress": True,
            "restrictfilenames": True,
            "overwrites": True,
            "merge_output_format": "mp4",
            "format": fmt,
            "socket_timeout": 30,
            "retries": 2,
            "progress_hooks": [hook],
        }
        try:
            with YoutubeDL(opts) as client:
                client.download([url])
        except VideoDownloadError as exc:
            last_error = exc
            _cleanup_partial(template)
            continue
        except UnsupportedError as exc:
            _cleanup_partial(template)
            raise VideoDownloadError("Эта ссылка не поддерживается.") from exc
        except DownloadError as exc:
            last_error = exc
            logger.warning("yt-dlp format failed: %s", fmt)
            _cleanup_partial(template)
            continue

        produced = [path for path in dest.parent.glob(f"{template.name}.*") if path.is_file()]
        if not produced:
            last_error = VideoDownloadError("После скачивания файл не появился.")
            continue
        video = max(produced, key=lambda path: path.stat().st_size)
        if video.stat().st_size <= 0:
            video.unlink(missing_ok=True)
            last_error = VideoDownloadError("Скачанный файл пустой.")
            continue
        if video.stat().st_size > max_bytes:
            logger.info("file too large (%s), trying lower quality", video.stat().st_size)
            video.unlink(missing_ok=True)
            last_error = VideoDownloadError(_too_large(max_bytes))
            continue
        final = dest.with_suffix(video.suffix)
        if video.resolve() != final.resolve():
            final.unlink(missing_ok=True)
            video.replace(final)
        logger.info("yt-dlp download complete path=%s bytes=%s", final.name, final.stat().st_size)
        return final

    _cleanup_partial(template)
    if last_error:
        raise VideoDownloadError(str(last_error)) from last_error
    raise VideoDownloadError("Не удалось скачать видео по этой ссылке.")


def _too_large(max_bytes: int) -> str:
    mb = max(1, max_bytes // (1024 * 1024))
    return f"Видео больше {mb} МБ даже в 360p. Сократи откат или поставь MAX_VIDEO_SIZE_MB больше."


def _cleanup_partial(template: Path) -> None:
    for path in template.parent.glob(f"{template.name}.*"):
        path.unlink(missing_ok=True)
