from __future__ import annotations

import discord

from app.config.settings import Settings


def deny_if_not_developer(interaction: discord.Interaction, settings: Settings) -> str | None:
    if settings.is_developer(interaction.user.id):
        return None
    return "This command is available only to developers."
