#!/usr/bin/env python3
import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env файл
load_dotenv()

# Добавляем src в путь ДО импортов
sys.path.insert(0, str(Path(__file__).parent / 'src'))

# Теперь импортируем из src
from bot import RecipeBot

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def main():
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    github_token = os.getenv("GITHUB_TOKEN")
    
    if not telegram_token:
        logger.error("❌ TELEGRAM_BOT_TOKEN не найден в .env файле")
        sys.exit(1)
    
    if not github_token:
        logger.error("❌ GITHUB_TOKEN не найден в .env файле")
        sys.exit(1)
    
    logger.info("✅ Токены загружены. Запуск бота...")
    
    try:
        bot = RecipeBot(telegram_token, github_token)
        bot.run()
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
