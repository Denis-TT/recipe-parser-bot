#!/usr/bin/env python3
import atexit
import fcntl
import json
import logging
import os
import signal
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Загружаем .env только для локальной разработки
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass  # На Railway dotenv не нужен

# Добавляем src в путь
sys.path.insert(0, str(Path(__file__).parent / "src"))

from bot import RecipeBot

LOCK_FILE_PATH = "/tmp/recipe_bot.lock"
LOCK_FD: Optional[int] = None


class JsonFormatter(logging.Formatter):
    """JSON formatter для структурированных логов."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class HealthHandler(BaseHTTPRequestHandler):
    """Мини healthcheck endpoint для Railway."""

    def do_GET(self):  # noqa: N802
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, _format: str, *_args):
        # Убираем шум healthcheck логов
        return


def configure_logging() -> None:
    os.makedirs("logs", exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(stream_handler)

    file_handler = RotatingFileHandler(
        "logs/recipe-bot.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(JsonFormatter())
    root_logger.addHandler(file_handler)


def ensure_single_instance(lock_file_path: str = LOCK_FILE_PATH) -> int:
    """Блокирует запуск второго экземпляра процесса."""
    global LOCK_FD

    lock_fd = os.open(lock_file_path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        logging.getLogger(__name__).error(
            "❌ Обнаружен второй экземпляр. Завершаем запуск во избежание 409 Conflict"
        )
        os.close(lock_fd)
        sys.exit(1)

    os.ftruncate(lock_fd, 0)
    os.write(lock_fd, str(os.getpid()).encode("utf-8"))
    LOCK_FD = lock_fd
    return lock_fd


def release_lock() -> None:
    global LOCK_FD
    if LOCK_FD is None:
        return

    try:
        fcntl.flock(LOCK_FD, fcntl.LOCK_UN)
    finally:
        os.close(LOCK_FD)
        LOCK_FD = None


def start_health_server() -> Optional[HTTPServer]:
    port = int(os.environ.get("PORT", "8080"))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthHandler)
    except OSError as error:
        logging.getLogger(__name__).warning(
            "⚠️ Healthcheck сервер не запущен: %s", error
        )
        return None

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    logging.getLogger(__name__).info("✅ Healthcheck сервер запущен на порту %s", port)
    return server


def main() -> None:
    configure_logging()
    logger = logging.getLogger(__name__)

    ensure_single_instance()
    atexit.register(release_lock)

    health_server = start_health_server()

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

    def shutdown_handler(signum, _frame):
        logger.info("📴 Получен сигнал %s, завершаем процесс", signum)
        release_lock()
        if health_server:
            health_server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    logger.info("✅ Токены загружены из переменных окружения")
    logger.info("🚀 Запуск бота...")

    try:
        bot = RecipeBot(telegram_token, github_token)
        bot.run()
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен")
    except Exception as e:
        logger.error("❌ Ошибка: %s", e, exc_info=True)
        sys.exit(1)
    finally:
        if health_server:
            health_server.shutdown()
        release_lock()


if __name__ == "__main__":
    main()
