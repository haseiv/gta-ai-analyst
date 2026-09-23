from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from app.bot.bot import GTAAnalystBot


class ReplayConfirmView(discord.ui.View):
    def __init__(self, bot: GTAAnalystBot, analysis_id: str, owner_id: int) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.analysis_id = analysis_id
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Подтвердить может только автор анализа.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="✅ Отправить", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await self.bot.send_replay(interaction, self.analysis_id)
        self.stop()

    @discord.ui.button(label="❌ Отмена", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_message("Отправка отменена.", ephemeral=True)
        self.stop()
