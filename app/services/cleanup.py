from __future__ import annotations

import asyncio
from pathlib import Path

from app.config.settings import Settings
from app.database.repository import AnalysisRepository, ReplayRepository
from app.services.storage import LocalFileStorage
from app.utils.logging import get_logger
from app.utils.time import as_utc, utc_now

logger = get_logger(__name__)


class CleanupService:
    def __init__(
        self,
        settings: Settings,
        storage: LocalFileStorage,
        analyses: AnalysisRepository | None = None,
        replays: ReplayRepository | None = None,
    ) -> None:
        self.settings = settings
        self.storage = storage
        self.analyses = analyses or AnalysisRepository()
        self.replays = replays or ReplayRepository()
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._loop(), name="replay-cleanup")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                self.run_once()
            except Exception:
                logger.exception("cleanup failed")
            await asyncio.sleep(60)

    def run_once(self) -> int:
        expired = self.replays.list_expired()
        cleaned = 0
        for replay in expired:
            analysis = self.analyses.get(replay.analysis_id)
            self.replays.update(replay.analysis_id, status="EXPIRED")
            if as_utc(replay.expires_at) > utc_now():
                continue
            if analysis and analysis.video_path:
                self.storage.delete(analysis.video_path)
                self.analyses.update(replay.analysis_id, video_path=None)
            cleaned += 1
        orphan_minutes = self.settings.replay_retention_minutes
        cutoff = utc_now().timestamp() - orphan_minutes * 60
        for path in self.settings.temp_dir.glob("*"):
            if path.is_file() and path.stat().st_mtime < cutoff:
                self.storage.delete(path)
                cleaned += 1
        if cleaned:
            logger.info("cleanup removed=%s", cleaned)
        return cleaned
