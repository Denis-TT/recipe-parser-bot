#!/usr/bin/env python3
import os
import sys
import logging
from pathlib import Path

# Загружаем .env только для локальной разработки
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # На Railway dotenv не нужен

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from bot import RecipeBot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def main():
    # Railway передает переменные через os.environ
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    github_token = os.environ.get("GITHUB_TOKEN")
    
    if not telegram_token:
        logger.error("❌ TELEGRAM_BOT_TOKEN не найден в переменных окружения")
        logger.info("Добавьте переменные в Railway Dashboard → Variables")
        sys.exit(1)
    
    if not github_token:
        logger.error("❌ GITHUB_TOKEN не найден в переменных окружения")
        sys.exit(1)
    
    logger.info("✅ Токены загружены из переменных окружения")
    logger.info("🚀 Запуск бота...")
    
    try:
        bot = RecipeBot(telegram_token, github_token)
        bot.run()
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
