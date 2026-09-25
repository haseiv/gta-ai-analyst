from __future__ import annotations

import json
from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.permissions import deny_if_not_developer
from app.bot.views.training import TrainingAddView
from app.database.repository import DistilledExampleRepository, TrainingRepository
from app.utils.time import format_timestamp, parse_timestamp

if TYPE_CHECKING:
    from app.bot.bot import GTAAnalystBot


class TrainingCog(commands.Cog):
    def __init__(self, bot: GTAAnalystBot) -> None:
        self.bot = bot
        self.training = TrainingRepository()
        self.distilled = DistilledExampleRepository()

    async def _guard(self, interaction: discord.Interaction) -> bool:
        reason = deny_if_not_developer(interaction, self.bot.settings)
        if reason:
            await interaction.response.send_message(reason, ephemeral=True)
            return False
        return True

    @app_commands.command(name="train_add", description="Добавить готовый анализ в базу знаний")
    @app_commands.describe(analysis_id="Номер анализа", start="Необязательно ММ:СС", end="Необязательно ММ:СС")
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
            await interaction.response.send_message("Готовый анализ не найден.", ephemeral=True)
            return
        try:
            start_ts = parse_timestamp(start)
            end_ts = parse_timestamp(end)
        except ValueError as exc:
            await interaction.response.send_message(str(exc), ephemeral=True)
            return
        result = json.loads(row.result_json)
        coach = result.get("coach") or {}
        ai_analysis = coach.get("summary") or "Итог ИИ не сохранён."
        embed = discord.Embed(title="🧠 ПРИМЕР ДЛЯ ОБУЧЕНИЯ", color=discord.Color.purple())
        embed.add_field(name="Анализ", value=f"#{analysis_id}", inline=True)
        embed.add_field(
            name="Момент",
            value=f"{format_timestamp(start_ts)}–{format_timestamp(end_ts)}",
            inline=True,
        )
        embed.add_field(name="🤖 РАЗБОР ИИ", value=ai_analysis[:1000], inline=False)
        await interaction.response.send_message(
            embed=embed,
            ephemeral=True,
            view=TrainingAddView(self.bot, analysis_id, ai_analysis, start_ts, end_ts, "General"),
        )

    @app_commands.command(name="train_list", description="Список примеров в базе знаний")
    async def train_list(self, interaction: discord.Interaction) -> None:
        if not await self._guard(interaction):
            return
        rows = self.training.list(15)
        if not rows:
            await interaction.response.send_message("База знаний пуста.", ephemeral=True)
            return
        lines = [
            f"#{item.id} {item.analysis_id} {item.category} {format_timestamp(item.timestamp_start)}–{format_timestamp(item.timestamp_end)}"
            for item in rows
        ]
        await interaction.response.send_message("\n".join(lines), ephemeral=True)

    @app_commands.command(name="train_remove", description="Удалить пример из базы знаний")
    async def train_remove(self, interaction: discord.Interaction, example_id: int) -> None:
        if not await self._guard(interaction):
            return
        deleted = self.training.delete(example_id)
        await interaction.response.send_message(
            "Удалено." if deleted else "Пример не найден.",
            ephemeral=True,
        )

    @app_commands.command(name="train_stats", description="Статистика базы знаний")
    async def train_stats(self, interaction: discord.Interaction) -> None:
        if not await self._guard(interaction):
            return
        stats = self.training.stats()
        student_total = self.distilled.count()
        embed = discord.Embed(title="🧠 БАЗА ЗНАНИЙ GTA AI", color=discord.Color.purple())
        embed.add_field(name="Примеров", value=str(stats.get("total", 0)), inline=False)
        for category in ("Movement", "Positioning", "Awareness", "Combat", "Aim", "General"):
            embed.add_field(name=category, value=str(stats.get(category, 0)), inline=True)
        embed.add_field(name="Метки локального ученика", value=str(student_total), inline=False)
        embed.add_field(name="Версия датасета", value="v2-teacher-student", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
