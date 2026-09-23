from __future__ import annotations

import json
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.permissions import deny_if_not_developer
from app.bot.views.training import TrainingAddView
from app.database.repository import TrainingRepository
from app.utils.time import format_timestamp, parse_timestamp

if TYPE_CHECKING:
    from app.bot.bot import GTAAnalystBot


class TrainingCog(commands.Cog):
    def __init__(self, bot: GTAAnalystBot) -> None:
        self.bot = bot
        self.training = TrainingRepository()

    async def _guard(self, interaction: discord.Interaction) -> bool:
        reason = deny_if_not_developer(interaction, self.bot.settings)
        if reason:
            await interaction.response.send_message(reason, ephemeral=True)
            return False
        return True

    @app_commands.command(name="train_add", description="Add a completed analysis to the knowledge base")
    @app_commands.describe(analysis_id="Existing analysis id", start="Optional MM:SS", end="Optional MM:SS")
    async def train_add(
        self,
        interaction: discord.Interaction,
        analysis_id: str,
        start: str | None = None,
        end: str | None = None,
    ) -> None:
        if not await self._guard(interaction):
            return
        analysis_id = analysis_id.strip().upper()
        row = self.bot.analyses.get(analysis_id)
        if row is None or row.status != "COMPLETED" or not row.result_json:
            await interaction.response.send_message("Completed analysis not found.", ephemeral=True)
            return
        try:
            start_ts = parse_timestamp(start)
            end_ts = parse_timestamp(end)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        result = json.loads(row.result_json)
        coach = result.get("coach") or {}
        ai_analysis = coach.get("summary") or "No AI summary stored."
        embed = discord.Embed(title="🧠 TRAINING EXAMPLE", color=discord.Color.purple())
        embed.add_field(name="Analysis", value=f"#{analysis_id}", inline=True)
        embed.add_field(
            name="Moment",
            value=f"{format_timestamp(start_ts)}–{format_timestamp(end_ts)}",
            inline=True,
        )
        embed.add_field(name="🤖 AI ANALYSIS", value=ai_analysis[:1000], inline=False)
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
            view=TrainingAddView(self.bot, analysis_id, ai_analysis, start_ts, end_ts, "General"),
        )

    @app_commands.command(name="train_list", description="List developer-selected training examples")
    async def train_list(self, interaction: discord.Interaction) -> None:
        if not await self._guard(interaction):
            return
        rows = self.training.list(15)
        if not rows:
            await interaction.response.send_message("Knowledge base is empty.", ephemeral=True)
            return
        lines = [
            f"#{item.id} {item.analysis_id} {item.category} {format_timestamp(item.timestamp_start)}–{format_timestamp(item.timestamp_end)}"
            for item in rows
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="train_remove", description="Remove a training example")
    async def train_remove(self, interaction: discord.Interaction, example_id: int) -> None:
        if not await self._guard(interaction):
            return
        deleted = self.training.delete(example_id)
        await interaction.response.send_message(
            "Removed." if deleted else "Example not found.",
            ephemeral=True,
        )

    @app_commands.command(name="train_stats", description="Knowledge base stats")
    async def train_stats(self, interaction: discord.Interaction) -> None:
        if not await self._guard(interaction):
            return
        stats = self.training.stats()
        embed = discord.Embed(title="🧠 GTA AI KNOWLEDGE", color=discord.Color.purple())
        embed.add_field(name="Training examples", value=str(stats.get("total", 0)), inline=False)
        for category in ("Movement", "Positioning", "Awareness", "Combat", "Aim", "General"):
            embed.add_field(name=category, value=str(stats.get(category, 0)), inline=True)
        embed.add_field(name="Dataset version", value="v1", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
