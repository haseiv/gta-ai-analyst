from __future__ import annotations

from pathlib import Path

from app.utils.logging import get_logger

logger = get_logger(__name__)


class VideoDownloadError(RuntimeError):
    pass


def download_platform_video(url: str, dest: Path, max_bytes: int) -> Path:
    """Download YouTube / Google Drive / Rutube to disk. Does not load the file into RAM."""
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError, UnsupportedError

    dest.parent.mkdir(parents=True, exist_ok=True)
    template = dest.with_suffix("")

    def hook(info: dict) -> None:
        downloaded = int(info.get("downloaded_bytes") or 0)
        total = int(info.get("total_bytes") or info.get("total_bytes_estimate") or 0)
        if downloaded > max_bytes or total > max_bytes:
            raise VideoDownloadError("Скачивание превысило лимит размера")

    opts = {
        "outtmpl": str(template) + ".%(ext)s",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "restrictfilenames": True,
        "overwrites": True,
        "merge_output_format": "mp4",
        "format": "bv*+ba/b",
        "max_filesize": max_bytes,
        "socket_timeout": 30,
        "retries": 2,
        "progress_hooks": [hook],
    }
    try:
        with YoutubeDL(opts) as client:
            client.download([url])
    except VideoDownloadError:
        _cleanup_partial(template)
        raise
    except UnsupportedError as exc:
        _cleanup_partial(template)
        raise VideoDownloadError("Эта ссылка не поддерживается.") from exc
    except DownloadError as exc:
        _cleanup_partial(template)
        logger.warning("yt-dlp failed")
        raise VideoDownloadError("Не удалось скачать видео по этой ссылке.") from exc

    produced = [path for path in dest.parent.glob(f"{template.name}.*") if path.is_file()]
    if not produced:
        raise VideoDownloadError("После скачивания файл не появился.")
    video = max(produced, key=lambda path: path.stat().st_size)
    if video.stat().st_size <= 0:
        video.unlink(missing_ok=True)
        raise VideoDownloadError("Скачанный файл пустой.")
    if video.stat().st_size > max_bytes:
        video.unlink(missing_ok=True)
        raise VideoDownloadError("Скачивание превысило лимит размера")
    final = dest.with_suffix(video.suffix)
    if video.resolve() != final.resolve():
        final.unlink(missing_ok=True)
        video.replace(final)
    logger.info("yt-dlp download complete path=%s bytes=%s", final.name, final.stat().st_size)
    return final


def _cleanup_partial(template: Path) -> None:
    for path in template.parent.glob(f"{template.name}.*"):
        path.unlink(missing_ok=True)
