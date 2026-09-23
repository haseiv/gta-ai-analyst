from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.embeds.analysis import build_failed_embed, build_status_embed

if TYPE_CHECKING:
    from app.bot.bot import GTAAnalystBot


class StatusCog(commands.Cog):
    def __init__(self, bot: GTAAnalystBot) -> None:
        self.bot = bot

    @app_commands.command(name="status", description="Show analysis status")
    @app_commands.describe(analysis_id="Analysis id, for example A184")
    async def status(self, interaction: discord.Interaction, analysis_id: str) -> None:
        analysis_id = analysis_id.strip().upper()
        job = self.bot.job_queue.get(analysis_id)
        row = self.bot.analyses.get(analysis_id)
        if job is None and row is None:
            await interaction.response.send_message(f"Analysis #{analysis_id} was not found.", ephemeral=True)
            return
        status = job.status if job else row.status
        progress = job.progress if job else row.progress
        if status == "FAILED":
            await interaction.response.send_message(
                embed=build_failed_embed(analysis_id, row.error if row and row.error else "Unknown error")
            )
            return
        await interaction.response.send_message(embed=build_status_embed(analysis_id, status, progress))
