from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands


class HelpCog(commands.Cog):
    @app_commands.command(name="help", description="How to use GTA AI Analyst")
    async def help(self, interaction: discord.Interaction) -> None:
        embed = discord.Embed(title="GTA AI Analyst", color=discord.Color.blurple())
        embed.add_field(
            name="Player commands",
            value=(
                "`/analyze video:` — queue a gameplay clip\n"
                "`/status analysis_id:` — check progress\n"
                "`/help` — this message"
            ),
            inline=False,
        )
        embed.add_field(
            name="Developer commands",
            value="`/train_add` `/train_list` `/train_remove` `/train_stats`",
            inline=False,
        )
        embed.add_field(
            name="Limits",
            value="Standard YOLO is not a GTA-specific model. Aim/cover/world distance are not scored yet.",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
