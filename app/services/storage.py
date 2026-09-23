from __future__ import annotations

from pathlib import Path

import aiohttp

from app.utils.files import unique_temp_path
from app.utils.logging import get_logger

logger = get_logger(__name__)


class LocalFileStorage:
    """Local temp storage. Can later be replaced with object storage."""

    def __init__(self, temp_dir: Path) -> None:
        self.temp_dir = temp_dir
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    def allocate(self, filename: str) -> Path:
        return unique_temp_path(self.temp_dir, filename)

    async def download(self, url: str, dest: Path, max_bytes: int) -> int:
        timeout = aiohttp.ClientTimeout(total=180)
        written = 0
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status >= 400:
                    raise RuntimeError("Could not download the Discord attachment")
                with dest.open("wb") as handle:
                    async for chunk in response.content.iter_chunked(64 * 1024):
                        written += len(chunk)
                        if written > max_bytes:
                            handle.close()
                            dest.unlink(missing_ok=True)
                            raise RuntimeError("Download exceeded the configured size limit")
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
