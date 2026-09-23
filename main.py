from __future__ import annotations

from app.bot.bot import create_bot
from app.config.settings import get_settings
from app.utils.logging import setup_logging


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    if not settings.discord_token:
        raise SystemExit("DISCORD_TOKEN is missing. Copy .env.example to .env and fill it in.")
    bot = create_bot(settings)
    bot.run(settings.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
