from __future__ import annotations

import asyncio
from pathlib import Path

import aiohttp

from app.analysis.video.sniff import is_html_or_text, read_head
from app.services.ytdlp import download_platform_video
from app.utils.files import unique_temp_path
from app.utils.logging import get_logger
from app.utils.urls import is_direct_video_url, is_platform_url

logger = get_logger(__name__)


class LocalFileStorage:
    """Local temp storage. Can later be replaced with object storage."""

    def __init__(self, temp_dir: Path) -> None:
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def allocate(self, filename: str) -> Path:
        return unique_temp_path(self.temp_dir, filename)

    async def download_video(
        self,
        url: str,
        dest: Path,
        max_bytes: int,
        cookies_file: str | None = None,
    ) -> Path:
        use_ytdlp = is_platform_url(url) or not is_direct_video_url(url)
        if use_ytdlp:
            logger.info("download via yt-dlp url_host")
            return await asyncio.to_thread(download_platform_video, url, dest, max_bytes, cookies_file)

        await self.download(url, dest, max_bytes)
        if dest.exists() and is_html_or_text(read_head(dest)):
            logger.warning("direct download returned HTML; retrying with yt-dlp")
            dest.unlink(missing_ok=True)
            return await asyncio.to_thread(download_platform_video, url, dest, max_bytes, cookies_file)
        return dest

    async def download(self, url: str, dest: Path, max_bytes: int) -> int:
        timeout = aiohttp.ClientTimeout(total=180)
        written = 0
        headers = {"User-Agent": "Mozilla/5.0 (compatible; GTA-AI-Analyst/1.0)"}
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers, allow_redirects=True) as response:
                if response.status >= 400:
                    raise RuntimeError("Не удалось скачать видео по ссылке")
                content_type = (response.headers.get("Content-Type") or "").lower()
                logger.info("download content-type=%s status=%s", content_type, response.status)
                if "text/html" in content_type:
                    dest.unlink(missing_ok=True)
                    raise RuntimeError("По ссылке открылась страница, а не видеофайл")
                with dest.open("wb") as handle:
                    async for chunk in response.content.iter_chunked(64 * 1024):
                        written += len(chunk)
                        if written > max_bytes:
                            handle.close()
                            dest.unlink(missing_ok=True)
                            raise RuntimeError("Скачивание превысило лимит размера")
                        handle.write(chunk)
        logger.info("download complete path=%s bytes=%s", dest.name, written)
        return written

    def delete(self, path: Path | str | None) -> None:
        if not path:
            return
        file_path = Path(path)
        if file_path.exists():
            file_path.unlink()
            logger.info("cleanup deleted %s", file_path.name)
