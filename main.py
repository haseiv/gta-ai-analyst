from __future__ import annotations

# Boot marker: if /app/main.py line 3 still imports create_bot, the host is on old code.
from app.config.settings import get_settings
from app.utils.logging import setup_logging
from app.utils.opencv_runtime import ensure_cv2


def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    ensure_cv2()
    from app.bot.bot import create_bot
    if not settings.discord_token:
        raise SystemExit("Нет DISCORD_TOKEN. Скопируй .env.example в .env и заполни.")
    bot = create_bot(settings)
    bot.run(settings.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
