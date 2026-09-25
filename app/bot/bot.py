from __future__ import annotations

import json
from pathlib import Path

import discord
from discord.ext import commands

from app.ai.provider import HTTPAIProvider
from app.analysis.video.validator import VideoValidationError, validate_video_file
from app.bot.commands.analyze import AnalyzeCog
from app.bot.commands.help import HelpCog
from app.bot.commands.status import StatusCog
from app.bot.commands.training import TrainingCog
from app.bot.embeds.analysis import build_analysis_embeds, build_failed_embed
from app.bot.embeds.replay import build_replay_posted_embed, build_replay_ready_embed
from app.bot.views.replay import ReplayReadyView
from app.config.settings import Settings
from app.database.repository import AnalysisRepository, ReplayRepository
from app.database.session import init_db
from app.learning.knowledge import CoachKnowledgeBase
from app.services.cleanup import CleanupService
from app.services.jobs import AnalysisJob, JobQueue, replay_expiry
from app.services.replay import ReplayService
from app.services.storage import LocalFileStorage
from app.services.ytdlp import VideoDownloadError
from app.utils.logging import get_logger
from app.utils.time import utc_now

logger = get_logger(__name__)

SAFE_ERRORS = {
    "ffprobe": "Не удалось прочитать метаданные. Это может быть не видео.",
    "YOLO model not found": "Модель зрения не установлена на сервере.",
    "yolov8": "Не удалось загрузить модель зрения. На сервере нет весов или мало RAM.",
    "ultralytics": "Не удалось загрузить модель зрения.",
    "MemoryError": "Не хватает памяти сервера. Пришли более короткий откат.",
    "out of memory": "Не хватает памяти сервера. Пришли более короткий откат.",
    "OpenCV": "Не удалось декодировать видео.",
    "лимит размера": "Видео больше разрешённого размера.",
    "даже в 360p": "Видео слишком тяжёлое. Сократи откат или подними MAX_VIDEO_SIZE_MB.",
    "скачать видео": "Не удалось скачать видео по ссылке.",
    "этой ссылке": "Не удалось скачать видео. Ссылка закрыта, удалена или не поддерживается.",
    "confirm your age": "YouTube не отдаёт 18+ без cookies. Положи cookies.txt или залей на Диск.",
    "18+": "YouTube не отдаёт 18+ без cookies. Положи cookies.txt или залей на Диск.",
    "возраст": "YouTube не отдаёт 18+ без cookies. Положи cookies.txt или залей на Диск.",
    "не поддерживается": "Эта ссылка не поддерживается.",
    "веб-страница": "Скачалась страница сайта, а не видео. Нужна открытая ссылка YouTube / Диск / Rutube.",
    "не видео": "Файл скачался, но это не видео.",
}


def public_error(exc: Exception) -> str:
    if isinstance(exc, (VideoDownloadError, VideoValidationError)):
        return str(exc)
    text = str(exc)
    for needle, message in SAFE_ERRORS.items():
        if needle in text:
            return message
    return "Внутренняя ошибка анализа. Подробности в логах сервера."


class GTAAnalystBot(commands.Bot):
    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)
        self.settings = settings
        self.analyses = AnalysisRepository()
        self.replays = ReplayRepository()
        self.storage = LocalFileStorage(settings.temp_dir)
        self.replay_service = ReplayService(settings, self.storage, self.analyses, self.replays)
        self.cleanup = CleanupService(settings, self.storage, self.analyses, self.replays)
        self.provider = HTTPAIProvider(
            settings.ai_base_url,
            settings.ai_api_key,
            settings.ai_model,
            timeout_seconds=settings.ai_timeout_seconds,
            max_retries=settings.ai_max_retries,
        )
        from app.analysis.pipeline import AnalysisPipeline

        self.pipeline = AnalysisPipeline(
            settings,
            self.provider,
            knowledge=CoachKnowledgeBase(top_k=settings.human_examples_top_k),
        )
        self.job_queue = JobQueue(settings, self.process_job, self.analyses, self.replays)

    async def setup_hook(self) -> None:
        init_db(self.settings)
        await self.add_cog(AnalyzeCog(self))
        await self.add_cog(StatusCog(self))
        await self.add_cog(HelpCog(self))
        await self.add_cog(TrainingCog(self))
        from app.bot.views.menu import MainMenuView

        self.add_view(MainMenuView(self))
        await self.job_queue.start()
        await self.cleanup.start()
        await self.tree.sync()
        logger.info("bot startup complete")

    async def close(self) -> None:
        await self.job_queue.stop()
        await self.cleanup.stop()
        await self.provider.close()
        await super().close()

    async def process_job(self, job: AnalysisJob) -> None:
        try:
            await self._process_job(job)
        except Exception as exc:
            logger.exception("analysis failed analysis_id=%s", job.analysis_id)
            self._fail(job, public_error(exc))
            await self._notify_channel(job.channel_id, embed=build_failed_embed(job.analysis_id, public_error(exc)))

    async def _process_job(self, job: AnalysisJob) -> None:
        self._set_job(job, "DOWNLOADING", 5)
        dest = self.storage.allocate(job.filename)
        max_bytes = self.settings.max_video_size_mb * 1024 * 1024
        dest = await self.storage.download_video(
            job.video_url,
            dest,
            max_bytes,
            cookies_file=self.settings.ytdlp_cookies_file or None,
            cookies_base64=self.settings.ytdlp_cookies_base64 or None,
        )
        job.video_path = str(dest)
        job.filename = dest.name
        self.analyses.update(job.analysis_id, video_path=str(dest), filename=dest.name, status="DOWNLOADING")

        metadata = validate_video_file(dest, self.settings.max_video_size_mb)
        logger.info(
            "video metadata analysis_id=%s duration=%.1f %sx%s fps=%.2f codec=%s",
            job.analysis_id,
            metadata.duration,
            metadata.width,
            metadata.height,
            metadata.fps,
            metadata.codec,
        )
        self.analyses.update(job.analysis_id, video_duration=metadata.duration)

        self._set_job(job, "PROCESSING", 10)

        def on_progress(value: float) -> None:
            job.progress = value
            status = "AI_ANALYSIS" if value >= 92 else "PROCESSING"
            job.status = status
            if int(value) % 15 == 0:
                self.analyses.update(job.analysis_id, progress=value, status=status)

        result = await self.pipeline.run(job.analysis_id, dest, metadata, on_progress)
        self._set_job(job, "COMPLETED", 100)
        self.analyses.update(
            job.analysis_id,
            status="COMPLETED",
            progress=100,
            completed_at=utc_now(),
            result_json=json.dumps(result),
            video_path=str(dest),
            video_duration=metadata.duration,
            error=None,
        )
        self.replays.create(job.analysis_id, replay_expiry(self.settings), status="AVAILABLE")
        logger.info("analysis completed analysis_id=%s", job.analysis_id)

        channel = self.get_channel(job.channel_id)
        if isinstance(channel, discord.abc.Messageable):
            for embed in build_analysis_embeds(job.analysis_id, result):
                await channel.send(embed=embed)
            await channel.send(
                embed=build_replay_ready_embed(
                    job.analysis_id,
                    job.filename,
                    self.settings.replay_retention_minutes,
                ),
                view=ReplayReadyView(
                    self,
                    job.analysis_id,
                    job.discord_user_id,
                    timeout=self.settings.replay_retention_minutes * 60,
                ),
            )

    def _set_job(self, job: AnalysisJob, status: str, progress: float) -> None:
        job.status = status
        job.progress = progress
        self.analyses.update(job.analysis_id, status=status, progress=progress)
        logger.info("queue analysis_id=%s status=%s progress=%.0f", job.analysis_id, status, progress)

    def _fail(self, job: AnalysisJob, message: str) -> None:
        job.status = "FAILED"
        self.analyses.update(job.analysis_id, status="FAILED", error=message, completed_at=utc_now())

    async def _notify_channel(self, channel_id: int, embed: discord.Embed) -> None:
        channel = self.get_channel(channel_id)
        if isinstance(channel, discord.abc.Messageable):
            await channel.send(embed=embed)

    async def send_replay(self, interaction: discord.Interaction, analysis_id: str) -> None:
        async with self.replay_service.lock_for(analysis_id):
            allowed, reason = self.replay_service.can_send(analysis_id, interaction.user.id)
            if not allowed:
                await interaction.response.send_message(reason, ephemeral=True)
                return
            claimed = self.replays.claim_for_send(analysis_id)
            if claimed is None:
                await interaction.response.send_message("Этот откат нельзя отправить.", ephemeral=True)
                return
            analysis = self.analyses.get(analysis_id)
            assert analysis is not None
            video_path = Path(analysis.video_path or "")
            target_id = self.settings.replay_channel_id or interaction.channel_id
            channel = self.get_channel(target_id) if target_id else None
            if not isinstance(channel, discord.abc.Messageable):
                self.replay_service.mark_failed(analysis_id)
                await interaction.response.send_message("Канал для откатов не настроен или бот его не видит.", ephemeral=True)
                return
            summary = ""
            if analysis.result_json:
                payload = json.loads(analysis.result_json)
                summary = (payload.get("coach") or {}).get("summary") or ""
            try:
                embed = build_replay_posted_embed(analysis_id, interaction.user, analysis.video_duration, summary)
                await channel.send(
                    embed=embed,
                    file=discord.File(video_path, filename=analysis.filename),
                )
            except discord.HTTPException:
                logger.exception("replay send failed analysis_id=%s", analysis_id)
                self.replay_service.mark_failed(analysis_id)
                await interaction.response.send_message(
                    "Discord отклонил загрузку. Файл может быть больше лимита сервера.",
                    ephemeral=True,
                )
                return
            self.replay_service.mark_sent(analysis_id)
            await interaction.response.send_message("Откат отправлен.", ephemeral=True)


def create_bot(settings: Settings) -> GTAAnalystBot:
    return GTAAnalystBot(settings)
