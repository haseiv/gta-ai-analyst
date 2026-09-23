from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from app.bot.views.confirmation import ReplayConfirmView

if TYPE_CHECKING:
    from app.bot.bot import GTAAnalystBot


class ReplayReadyView(discord.ui.View):
    def __init__(self, bot: GTAAnalystBot, analysis_id: str, owner_id: int, timeout: float) -> None:
        super().__init__(timeout=timeout)
        self.bot = bot
        self.analysis_id = analysis_id
        self.owner_id = owner_id

    @discord.ui.button(label="📤 Отправить откат", style=discord.ButtonStyle.primary)
    async def send_replay(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("Отправить откат может только автор анализа.", ephemeral=True)
            return
        allowed, reason = self.bot.replay_service.can_send(self.analysis_id, interaction.user.id)
        if not allowed:
            button.disabled = True
            await interaction.response.send_message(reason, ephemeral=True)
            if interaction.message:
                await interaction.message.edit(view=self)
            return
        await interaction.response.send_message(
            "Отправить этот откат?",
            ephemeral=True,
            view=ReplayConfirmView(self.bot, self.analysis_id, self.owner_id),
        )
