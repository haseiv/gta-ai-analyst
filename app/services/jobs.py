from __future__ import annotations

import asyncio
import secrets
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.config.settings import Settings
from app.database.repository import AnalysisRepository, ReplayRepository
from app.utils.logging import get_logger
from app.utils.time import utc_now

logger = get_logger(__name__)

JobHandler = Callable[["AnalysisJob"], Awaitable[None]]


@dataclass
class AnalysisJob:
    analysis_id: str
    discord_user_id: int
    video_url: str
    filename: str
    channel_id: int
    interaction_token: str
    application_id: int
    video_path: str | None = None
    status: str = "QUEUED"
    progress: float = 0.0
    created_at: datetime = field(default_factory=utc_now)


class JobQueue:
    def __init__(
        self,
        settings: Settings,
        handler: JobHandler,
        analyses: AnalysisRepository | None = None,
        replays: ReplayRepository | None = None,
    ) -> None:
        self.settings = settings
        self.handler = handler
        self.analyses = analyses or AnalysisRepository()
        self.replays = replays or ReplayRepository()
        self.queue: asyncio.Queue[AnalysisJob] = asyncio.Queue()
        self.jobs: dict[str, AnalysisJob] = {}
        self._workers: list[asyncio.Task] = []
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        self._started = True
        for index in range(self.settings.max_concurrent_analyses):
            self._workers.append(asyncio.create_task(self._worker(index), name=f"analysis-worker-{index}"))
        logger.info("queue workers=%s", self.settings.max_concurrent_analyses)

    async def stop(self) -> None:
        for worker in self._workers:
            worker.cancel()
        self._workers.clear()
        self._started = False

    def generate_analysis_id(self) -> str:
        for _ in range(12):
            candidate = "A" + secrets.token_hex(2).upper()
            if not self.analyses.exists(candidate):
                return candidate
        raise RuntimeError("Could not allocate analysis id")

    async def enqueue(self, job: AnalysisJob) -> AnalysisJob:
        self.jobs[job.analysis_id] = job
        await self.queue.put(job)
        logger.info("queue analysis_id=%s status=QUEUED", job.analysis_id)
        return job

    def get(self, analysis_id: str) -> AnalysisJob | None:
        return self.jobs.get(analysis_id)

    async def _worker(self, index: int) -> None:
        while True:
            job = await self.queue.get()
            try:
                logger.info("analysis started analysis_id=%s worker=%s", job.analysis_id, index)
                await self.handler(job)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("analysis worker failed analysis_id=%s", job.analysis_id)
            finally:
                self.queue.task_done()


def replay_expiry(settings: Settings) -> datetime:
    return utc_now() + timedelta(minutes=settings.replay_retention_minutes)
