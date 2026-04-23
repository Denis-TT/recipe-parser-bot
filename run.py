#!/usr/bin/env python3
import logging
import sys

from dotenv import load_dotenv

from app.backend.factory import build_repository
from app.bot.recipe_bot import RecipeBot
from app.shared.config import Settings
from app.shared.logging import configure_logging


def main() -> None:
    load_dotenv()
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    logger = logging.getLogger(__name__)

    if not settings.telegram_bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not set.")
        sys.exit(1)
    if not settings.github_token:
        logger.error("GITHUB_TOKEN is not set.")
        sys.exit(1)

    repository = build_repository(settings)
    bot = RecipeBot(settings=settings, repository=repository)
    bot.run()


if __name__ == "__main__":
    main()
