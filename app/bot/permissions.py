from __future__ import annotations

import discord

from app.config.settings import Settings


def deny_if_not_developer(interaction: discord.Interaction, settings: Settings) -> str | None:
    if settings.is_developer(interaction.user.id):
        return None
    guild = interaction.guild
    if guild is not None and getattr(guild, "owner_id", None) == interaction.user.id:
        return None
    permissions = getattr(interaction.user, "guild_permissions", None)
    if permissions is not None and (
        getattr(permissions, "administrator", False)
        or getattr(permissions, "manage_guild", False)
    ):
        return None
    return "Эта команда доступна разработчикам и администраторам сервера."
