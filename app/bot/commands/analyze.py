from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.analysis_submit import submit_video_url

if TYPE_CHECKING:
    from app.bot.bot import GTAAnalystBot


class AnalyzeCog(commands.Cog):
    def __init__(self, bot: GTAAnalystBot) -> None:
        self.bot = bot

    @app_commands.command(name="analyze", description="Разобрать откат по ссылке")
    @app_commands.describe(url="Прямая ссылка на видео (.mp4 .mov .mkv .webm)")
    async def analyze(self, interaction: discord.Interaction, url: str) -> None:
        await submit_video_url(self.bot, interaction, url)
