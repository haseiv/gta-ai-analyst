from __future__ import annotations

import base64
import binascii
import os
from pathlib import Path

from app.utils.logging import get_logger

logger = get_logger(__name__)

_FORMATS = (
    "bv*[vcodec^=avc1][height<=1080]+ba[acodec^=mp4a]/b[vcodec^=avc1][height<=1080]",
    "bv*[vcodec^=avc1][height<=720]+ba[acodec^=mp4a]/b[vcodec^=avc1][height<=720]",
    "bv*[height<=1080]+ba/b[height<=1080]",
    "bv*[height<=720]+ba/b[height<=720]",
    "bv*[height<=480]+ba/b[height<=480]",
    "bv*[height<=360]+ba/b[height<=360]",
    "worst",
)


class VideoDownloadError(RuntimeError):
    pass


def _friendly_error(text: str) -> str | None:
    lower = text.lower()
    if "confirm you're not a bot" in lower or "confirm you’re not a bot" in lower:
        return (
            "YouTube требует авторизацию для проверки, что запрос делает не бот. "
            "Обнови cookies через YTDLP_COOKIES_FILE или YTDLP_COOKIES_BASE64."
        )
    if "confirm your age" in lower or "age-restricted" in lower or "sign in to confirm" in lower:
        return (
            "YouTube не отдаёт это видео без входа (возраст / 18+). "
            "Положи cookies.txt на сервер и укажи YTDLP_COOKIES_FILE, "
            "либо залей откат на Google Диск / Rutube."
        )
    if "private video" in lower or "login required" in lower:
        return "Видео приватное. Сделай доступ по ссылке или положи cookies YouTube на сервер."
    if "video unavailable" in lower:
        return "YouTube пишет, что видео недоступно."
    if "cookies are no longer valid" in lower or "cookies have expired" in lower:
        return "Cookies YouTube устарели. Экспортируй свежие cookies и перезапусти бота."
    return None


def download_platform_video(
    url: str,
    dest: Path,
    max_bytes: int,
    cookies_file: str | None = None,
    cookies_base64: str | None = None,
) -> Path:
    """Download YouTube / Google Drive / Rutube. Writes to disk only."""
    from yt_dlp import YoutubeDL
    from yt_dlp.utils import DownloadError, UnsupportedError

    dest.parent.mkdir(parents=True, exist_ok=True)
    template = dest.with_suffix("")
    last_error: Exception | None = None
    cookie_path = _prepare_cookies(cookies_file, cookies_base64, dest.parent)

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
        if cookie_path:
            opts["cookiefile"] = str(cookie_path)
            logger.info("yt-dlp using cookies file")
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
            friendly = _friendly_error(str(exc))
            _cleanup_partial(template)
            if friendly:
                raise VideoDownloadError(friendly) from exc
            last_error = exc
            logger.warning("yt-dlp format failed: %s", fmt)
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
        raise VideoDownloadError(_friendly_error(str(last_error)) or "Не удалось скачать видео по этой ссылке.") from last_error
    raise VideoDownloadError("Не удалось скачать видео по этой ссылке.")


def _prepare_cookies(
    cookies_file: str | None,
    cookies_base64: str | None,
    target_dir: Path,
) -> Path | None:
    if cookies_file:
        path = Path(cookies_file).expanduser()
        if not path.is_file():
            raise VideoDownloadError(
                f"Файл cookies не найден: {path}. Проверь YTDLP_COOKIES_FILE."
            )
        return path

    if not cookies_base64:
        return None

    try:
        payload = base64.b64decode(cookies_base64, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise VideoDownloadError("YTDLP_COOKIES_BASE64 содержит некорректный base64.") from exc
    if not payload.strip():
        raise VideoDownloadError("YTDLP_COOKIES_BASE64 пуст после декодирования.")

    path = target_dir / "youtube-cookies.txt"
    path.write_bytes(payload)
    try:
        os.chmod(path, 0o600)
    except OSError:
        logger.warning("could not restrict permissions on cookies file")
    return path


def _too_large(max_bytes: int) -> str:
    mb = max(1, max_bytes // (1024 * 1024))
    return f"Видео больше {mb} МБ даже в 360p. Сократи откат или поставь MAX_VIDEO_SIZE_MB больше."


def _cleanup_partial(template: Path) -> None:
    for path in template.parent.glob(f"{template.name}.*"):
        path.unlink(missing_ok=True)
