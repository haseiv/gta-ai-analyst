from __future__ import annotations

import asyncio
from pathlib import Path

from app.config.settings import Settings
from app.database.repository import AnalysisRepository, ReplayRepository
from app.services.storage import LocalFileStorage
from app.utils.logging import get_logger
from app.utils.time import as_utc, utc_now

logger = get_logger(__name__)


class ReplayService:
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
        self._locks: dict[str, asyncio.Lock] = {}

    def lock_for(self, analysis_id: str) -> asyncio.Lock:
        if analysis_id not in self._locks:
            self._locks[analysis_id] = asyncio.Lock()
        return self._locks[analysis_id]

    def can_send(self, analysis_id: str, user_id: int) -> tuple[bool, str]:
        analysis = self.analyses.get(analysis_id)
        if analysis is None:
            return False, "Analysis not found."
        if analysis.discord_user_id != user_id:
            return False, "Only the analysis owner can send this replay."
        replay = self.replays.get_by_analysis(analysis_id)
        if replay is None:
            return False, "Replay is not available."
        if replay.status == "SENT":
            return False, "This replay was already sent."
        if replay.status == "SENDING":
            return False, "This replay is already being sent."
        if replay.status == "EXPIRED" or as_utc(replay.expires_at) <= utc_now():
            return False, "This replay has expired."
        if replay.status != "AVAILABLE":
            return False, "This replay cannot be sent."
        if not analysis.video_path or not Path(analysis.video_path).exists():
            return False, "Replay file is no longer on disk."
        size = Path(analysis.video_path).stat().st_size
        if size > self.settings.discord_upload_limit_mb * 1024 * 1024:
            return False, (
                f"Video exceeds the Discord upload limit "
                f"({self.settings.discord_upload_limit_mb} MB)."
            )
        return True, ""

    def mark_sent(self, analysis_id: str) -> None:
        self.replays.update(analysis_id, status="SENT", sent_at=utc_now())
        logger.info("replay send analysis_id=%s", analysis_id)
        if self.settings.delete_replay_after_send:
            analysis = self.analyses.get(analysis_id)
            if analysis and analysis.video_path:
                self.storage.delete(analysis.video_path)
                self.analyses.update(analysis_id, video_path=None)

    def mark_failed(self, analysis_id: str) -> None:
        replay = self.replays.get_by_analysis(analysis_id)
        if replay and replay.status == "SENDING":
            self.replays.update(analysis_id, status="AVAILABLE")

    def mark_expired(self, analysis_id: str) -> None:
        analysis = self.analyses.get(analysis_id)
        self.replays.update(analysis_id, status="EXPIRED")
        if analysis and analysis.video_path:
            self.storage.delete(analysis.video_path)
            self.analyses.update(analysis_id, video_path=None)
