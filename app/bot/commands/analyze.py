from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from app.analysis.video.validator import VideoValidationError, validate_extension, validate_size
from app.bot.embeds.analysis import build_status_embed
from app.services.jobs import AnalysisJob
from app.utils.files import sanitize_filename
from app.utils.logging import get_logger

if TYPE_CHECKING:
    from app.bot.bot import GTAAnalystBot

logger = get_logger(__name__)


class AnalyzeCog(commands.Cog):
    def __init__(self, bot: GTAAnalystBot) -> None:
        self.bot = bot

    @app_commands.command(name="analyze", description="Analyze a GTA V / FiveM gameplay video")
    @app_commands.describe(video="Gameplay recording (.mp4 .mov .mkv .webm)")
    async def analyze(self, interaction: discord.Interaction, video: discord.Attachment) -> None:
        await interaction.response.defer(thinking=True)
        filename = sanitize_filename(video.filename)
        try:
            validate_extension(filename)
            validate_size(video.size, self.bot.settings.max_video_size_mb)
        except VideoValidationError as exc:
            await interaction.followup.send(exc.user_message, ephemeral=True)
            return

        analysis_id = self.bot.job_queue.generate_analysis_id()
        self.bot.analyses.create(
            analysis_id=analysis_id,
            discord_user_id=interaction.user.id,
            guild_id=interaction.guild_id,
            filename=filename,
            status="QUEUED",
        )
        job = AnalysisJob(
            analysis_id=analysis_id,
            discord_user_id=interaction.user.id,
            video_url=video.url,
            filename=filename,
            channel_id=interaction.channel_id or 0,
            interaction_token=interaction.token,
            application_id=self.bot.application_id or 0,
        )
        await self.bot.job_queue.enqueue(job)
        logger.info("analysis created analysis_id=%s user=%s", analysis_id, interaction.user.id)
        await interaction.followup.send(embed=build_status_embed(analysis_id, "QUEUED", 0))
