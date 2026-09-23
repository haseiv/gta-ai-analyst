from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

from app.bot.views.menu import MainMenuView, build_menu_embed

if TYPE_CHECKING:
    from app.bot.bot import GTAAnalystBot


class HelpCog(commands.Cog):
    def __init__(self, bot: GTAAnalystBot) -> None:
        self.bot = bot

    @app_commands.command(name="menu", description="Открыть меню бота")
    async def menu(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=build_menu_embed(), view=MainMenuView(self.bot))

    @app_commands.command(name="help", description="Как пользоваться ботом")
    async def help(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(embed=build_menu_embed(), view=MainMenuView(self.bot))
