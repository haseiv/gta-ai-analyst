from __future__ import annotations

import discord

from app.utils.time import format_timestamp


def build_replay_ready_embed(analysis_id: str, filename: str, retention_minutes: int) -> discord.Embed:
    embed = discord.Embed(title="🎬 ОТКАТ ГОТОВ", color=discord.Color.gold())
    embed.add_field(name="Анализ", value=f"#{analysis_id}", inline=True)
    embed.add_field(name="Видео", value=filename, inline=True)
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
    embed.add_field(name="Игрок", value=user.mention, inline=True)
    embed.add_field(name="Анализ", value=f"#{analysis_id}", inline=True)
    embed.add_field(name="Длительность", value=format_timestamp(duration), inline=True)
    embed.add_field(name="Итог ИИ", value=(summary or "Н/Д")[:1000], inline=False)
    return embed
