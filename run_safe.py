#!/usr/bin/env python3
import os
import sys
import fcntl
import logging

# Загружаем .env вручную
env_file = '.env'
if os.path.exists(env_file):
    with open(env_file, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#'):
                if '=' in line:
                    key, value = line.split('=', 1)
                    os.environ[key.strip()] = value.strip()

# Добавляем src в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

# Файл блокировки
LOCK_FILE = '/tmp/recipe_bot.lock'

def check_lock():
    """Проверка, что запущен только один экземпляр"""
    global lock_file
    lock_file = open(LOCK_FILE, 'w')
    try:
        fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except IOError:
        print("❌ Бот уже запущен! Остановите другой экземпляр.")
        sys.exit(1)

if __name__ == "__main__":
    check_lock()
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    # Импортируем после настройки пути
    from bot import RecipeBot
    
    telegram_token = os.getenv("TELEGRAM_BOT_TOKEN")
    github_token = os.getenv("GITHUB_TOKEN")
    
    if not telegram_token or not github_token:
        logger.error("❌ Токены не найдены в .env файле")
        sys.exit(1)
    
    logger.info("🚀 Запуск бота...")
    bot = RecipeBot(telegram_token, github_token)
    
    try:
        bot.run()
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен")
    except Exception as e:
        logger.error(f"❌ Ошибка: {e}")
    finally:
        lock_file.close()
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
