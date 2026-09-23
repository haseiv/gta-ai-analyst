from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from app.learning.training_examples import TrainingService
from app.utils.logging import get_logger
from app.utils.time import format_timestamp

if TYPE_CHECKING:
    from app.bot.bot import GTAAnalystBot

logger = get_logger(__name__)


class TrainingModal(discord.ui.Modal, title="Мой разбор"):
    category = discord.ui.TextInput(label="Категория", placeholder="Movement", max_length=64)
    human_analysis = discord.ui.TextInput(label="Разбор", style=discord.TextStyle.paragraph)
    recommendation = discord.ui.TextInput(label="Рекомендация", style=discord.TextStyle.paragraph)

    def __init__(
        self,
        bot: GTAAnalystBot,
        analysis_id: str,
        ai_analysis: str,
        start: float | None,
        end: float | None,
    ) -> None:
        super().__init__()
        self.bot = bot
        self.analysis_id = analysis_id
        self.ai_analysis = ai_analysis
        self.start = start
        self.end = end

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not self.bot.settings.is_developer(interaction.user.id):
            await interaction.response.send_message("Только для разработчиков.", ephemeral=True)
            return
        example = TrainingService().add(
            analysis_id=self.analysis_id,
            created_by=interaction.user.id,
            category=str(self.category.value),
            ai_analysis=self.ai_analysis,
            human_analysis=str(self.human_analysis.value),
            recommendation=str(self.recommendation.value),
            timestamp_start=self.start,
            timestamp_end=self.end,
        )
        logger.info("training example creation id=%s analysis_id=%s", example.id, self.analysis_id)
        await interaction.response.send_message(
            f"Сохранён пример #{example.id} для анализа #{self.analysis_id}.",
            ephemeral=True,
        )


class TrainingAddView(discord.ui.View):
    def __init__(
        self,
        bot: GTAAnalystBot,
        analysis_id: str,
        ai_analysis: str,
        start: float | None,
        end: float | None,
        default_category: str,
    ) -> None:
        super().__init__(timeout=180)
        self.bot = bot
        self.analysis_id = analysis_id
        self.ai_analysis = ai_analysis
        self.start = start
        self.end = end
        self.default_category = default_category

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.bot.settings.is_developer(interaction.user.id):
            return True
        await interaction.response.send_message("Только для разработчиков.", ephemeral=True)
        return False

    @discord.ui.button(label="✅ Добавить как есть", style=discord.ButtonStyle.success)
    async def add_as_is(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        example = TrainingService().add(
            analysis_id=self.analysis_id,
            created_by=interaction.user.id,
            category=self.default_category,
            ai_analysis=self.ai_analysis,
            human_analysis=None,
            recommendation=None,
            timestamp_start=self.start,
            timestamp_end=self.end,
        )
        logger.info("training example creation id=%s analysis_id=%s", example.id, self.analysis_id)
        await interaction.response.edit_message(
            content=f"Сохранён пример #{example.id} ({format_timestamp(self.start)}–{format_timestamp(self.end)}).",
            embed=None,
            view=None,
        )
        self.stop()

    @discord.ui.button(label="✏️ Мой разбор", style=discord.ButtonStyle.primary)
    async def human_review(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(
            TrainingModal(self.bot, self.analysis_id, self.ai_analysis, self.start, self.end)
        )

    @discord.ui.button(label="❌ Отмена", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.edit_message(content="Отменено.", embed=None, view=None)
        self.stop()
