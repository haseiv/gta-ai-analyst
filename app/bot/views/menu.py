from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from app.bot.analysis_submit import submit_video_url

if TYPE_CHECKING:
    from app.bot.bot import GTAAnalystBot


def build_menu_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🎮 GTA AI Analyst",
        description=(
            "Пришли **ссылку** на откат — бот скачает видео и разберёт геймплей.\n"
            "Файлы в Discord не принимаются."
        ),
        color=discord.Color.blurple(),
    )
    embed.add_field(
        name="Какие ссылки подходят",
        value="YouTube, Google Disk, Rutube или прямая ссылка. Видео качается на сервер (до 2 ГБ).",
        inline=False,
    )
    embed.add_field(
        name="Как пользоваться",
        value=(
            "1. Нажми **Залить откат**\n"
            "2. Вставь ссылку на видео\n"
            "3. Дождись разбора в этом канале"
        ),
        inline=False,
    )
    embed.add_field(name="Команды", value="`/menu` — это меню\n`/status` — статус анализа", inline=False)
    return embed


class UploadReplayModal(discord.ui.Modal, title="Залить откат"):
    url = discord.ui.TextInput(
        label="Ссылка на видео",
        placeholder="YouTube, Google Диск, Rutube или прямая ссылка",
        style=discord.TextStyle.paragraph,
        max_length=1000,
    )

    def __init__(self, bot: GTAAnalystBot) -> None:
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await submit_video_url(self.bot, interaction, str(self.url.value))


class MainMenuView(discord.ui.View):
    def __init__(self, bot: GTAAnalystBot) -> None:
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="🎬 Залить откат", style=discord.ButtonStyle.success, custom_id="gta:upload_replay")
    async def upload(self, interaction: discord.Interaction, _button: discord.ui.Button) -> None:
        await interaction.response.send_modal(UploadReplayModal(self.bot))
