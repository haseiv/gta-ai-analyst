from __future__ import annotations

import discord

from app.utils.time import format_timestamp


def build_replay_ready_embed(analysis_id: str, filename: str, retention_minutes: int) -> discord.Embed:
    embed = discord.Embed(title="🎬 ОТКАТ ГОТОВ", color=discord.Color.gold())
    embed.add_field(name="Analysis", value=f"#{analysis_id}", inline=True)
    embed.add_field(name="Video", value=filename, inline=True)
    embed.add_field(
        name="Доступность",
        value=f"Откат доступен ещё {retention_minutes} минут.",
        inline=False,
    )
    return embed


def build_replay_posted_embed(
    analysis_id: str,
    user: discord.abc.User,
    duration: float | None,
    summary: str,
) -> discord.Embed:
    embed = discord.Embed(title="🎬 НОВЫЙ ОТКАТ", color=discord.Color.orange())
    embed.add_field(name="Player", value=user.mention, inline=True)
    embed.add_field(name="Analysis", value=f"#{analysis_id}", inline=True)
    embed.add_field(name="Duration", value=format_timestamp(duration), inline=True)
    embed.add_field(name="AI Summary", value=(summary or "N/A")[:1000], inline=False)
    return embed
