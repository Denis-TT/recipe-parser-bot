import os
import logging
import asyncio
from typing import Optional

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

from parser import RecipeParser
from normalizer_github import GitHubModelNormalizer
from utils import format_recipe_for_telegram, save_recipe_to_file, validate_url

logger = logging.getLogger(__name__)

class RecipeBot:
    def __init__(self, telegram_token: str, github_token: str):
        self.telegram_token = telegram_token
        self.parser = RecipeParser()
        self.normalizer = GitHubModelNormalizer(github_token)
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = (
            "👨‍🍳 *Recipe Parser Bot с КБЖУ*\n\n"
            "Привет! Отправь ссылку на рецепт, и я:\n"
            "• Извлеку ингредиенты и шаги\n"
            "• Определю тип блюда (завтрак/обед/ужин/десерт)\n"
            "• Рассчитаю примерное КБЖУ\n"
            "• Сохраню рецепт локально\n\n"
            "/help - подробнее"
        )
        
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = (
            "📚 *Как это работает:*\n\n"
            "1️⃣ Отправь ссылку на рецепт\n"
            "2️⃣ Бот спарсит страницу\n"
            "3️⃣ GPT-4o проанализирует рецепт\n"
            "4️⃣ Определит тип блюда и рассчитает КБЖУ\n"
            "5️⃣ Ты получишь структурированный рецепт\n\n"
            "*В ответе будет:*\n"
            "• Тип блюда (🍳 завтрак, 🍲 обед, 🍽 ужин, 🍰 десерт)\n"
            "• Время приготовления\n"
            "• КБЖУ на порцию и на 100г\n"
            "• Диетические метки (веган, без глютена и т.д.)\n\n"
            "*Рецепты сохраняются локально в папку output/*"
        )
        
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        url = update.message.text.strip()
        
        if not validate_url(url):
            await update.message.reply_text("❌ Некорректная ссылка")
            return
        
        # Отправляем начальное сообщение и сохраняем его ID
        status_message = await update.message.reply_text("🔍 Начинаю обработку рецепта...")
        message_id = status_message.message_id
        chat_id = update.effective_chat.id
        
        try:
            # Функция для безопасного обновления статуса
            async def update_status(text: str):
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=message_id,
                        text=text
                    )
                except Exception as e:
                    logger.warning(f"Не удалось обновить статус: {e}")
            
            await update_status("🌐 Парсим страницу...")
            raw_text = await self.parser.parse_recipe(url)
            
            await update_status("🤖 GPT-4o анализирует рецепт и рассчитывает КБЖУ...")
            recipe = await self.normalizer.normalize(raw_text)
            recipe['source_url'] = url
            
            # Сохраняем локально
            filename = save_recipe_to_file(recipe)
            
            # Форматируем текст для Telegram
            formatted_text = format_recipe_for_telegram(recipe)
            
            # Удаляем статусное сообщение
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
            except:
                pass
            
            # Отправляем результат
            await update.message.reply_text(
                formatted_text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            
            logger.info(f"✅ Рецепт обработан и сохранен: {filename}")
            
        except Exception as e:
            logger.error(f"Ошибка обработки: {e}")
            
            # Пытаемся отправить ошибку
            error_text = f"❌ Ошибка при обработке: {str(e)[:150]}"
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=error_text
                )
            except:
                await update.message.reply_text(error_text)
    
    def run(self):
        app = (
            Application.builder()
            .token(self.telegram_token)
            .connect_timeout(60.0)
            .read_timeout(60.0)
            .write_timeout(60.0)
            .build()
        )
        
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_url))
        
        logger.info("🚀 Бот запущен! Ожидаю сообщения...")
        
        try:
            app.run_polling(drop_pending_updates=True)
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
            raise
    
    async def cleanup(self):
        await self.parser.close()
