from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from app.analysis.video.validator import VideoValidationError
from app.bot.embeds.analysis import build_status_embed
from app.services.jobs import AnalysisJob
from app.utils.logging import get_logger
from app.utils.urls import parse_video_url

if TYPE_CHECKING:
    from app.bot.bot import GTAAnalystBot

logger = get_logger(__name__)


async def submit_video_url(
    bot: GTAAnalystBot,
    interaction: discord.Interaction,
    raw_url: str,
    player_name: str | None = None,
) -> None:
    try:
        url, filename = parse_video_url(raw_url)
    except VideoValidationError as exc:
        await interaction.response.send_message(exc.user_message, ephemeral=True)
        return

    await interaction.response.defer(thinking=True)
    analysis_id = bot.job_queue.generate_analysis_id()
    bot.analyses.create(
        analysis_id=analysis_id,
        discord_user_id=interaction.user.id,
        guild_id=interaction.guild_id,
        filename=filename,
        status="QUEUED",
    )
    job = AnalysisJob(
        analysis_id=analysis_id,
        discord_user_id=interaction.user.id,
        video_url=url,
        filename=filename,
        channel_id=interaction.channel_id or 0,
        interaction_token=interaction.token,
        application_id=bot.application_id or 0,
        player_name=(player_name or "").strip()[:50] or None,
    )
    await bot.job_queue.enqueue(job)
    logger.info("analysis created analysis_id=%s user=%s", analysis_id, interaction.user.id)
    await interaction.followup.send(embed=build_status_embed(analysis_id, "QUEUED", 0))
