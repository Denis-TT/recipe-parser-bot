import os
import logging
from typing import Dict, Any
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode
from parser import RecipeParser
from normalizer_github import GitHubModelNormalizer
from utils import format_recipe_for_telegram, validate_url
from storage import RecipeStorage
logger = logging.getLogger(__name__)
class RecipeBot:
    """Telegram бот для парсинга и сохранения рецептов"""
    def __init__(self, telegram_token: str, github_token: str):
        self.telegram_token = telegram_token
        self.parser = RecipeParser()
        self.normalizer = GitHubModelNormalizer(github_token)
        self.storage = RecipeStorage()
        self.temp_recipes: Dict[int, Dict[str, Any]] = {}
        logger.info("🤖 RecipeBot инициализирован")
    def get_main_keyboard(self) -> ReplyKeyboardMarkup:
        """Главная клавиатура"""
        keyboard = [[KeyboardButton("📋 Меню")]]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    def get_menu_keyboard(self) -> ReplyKeyboardMarkup:
        """Клавиатура меню"""
        keyboard = [
            [KeyboardButton("📚 Сохраненные рецепты"), KeyboardButton("ℹ️ Помощь")],
            [KeyboardButton("⬅️ Назад")],
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    def get_save_keyboard(self, recipe_id: str) -> InlineKeyboardMarkup:
        logger.info(f"🔘 Созданы кнопки сохранения с recipe_id={recipe_id}")
        print(f"🔘 Созданы кнопки сохранения с recipe_id={recipe_id}")
        """Клавиатура для сохранения рецепта"""
        keyboard = [[
            InlineKeyboardButton("✅ Да, сохранить", callback_data=f"save_{recipe_id}"),
            InlineKeyboardButton("❌ Нет", callback_data="dont_save")
        ]]
        return InlineKeyboardMarkup(keyboard)
    async def setup_commands(self, application: Application):
        """Настройка команд бота"""
        await application.bot.set_my_commands([])
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /start"""
        await update.message.reply_text(
            "👨‍🍳 *Привет, шеф-повар!*\n\n"
            "Я бот для парсинга и сохранения рецептов.\n\n"
            "Отправь мне ссылку на рецепт или используй кнопки ниже!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard()
        )
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /menu и кнопки Меню"""
        await update.message.reply_text(
            "📋 *Главное меню*\n\n"
            "Выберите действие:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_menu_keyboard()
        )
    async def saved_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /saved"""
        await self.show_saved_recipes(update, context)
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /help и кнопки Помощь"""
        await update.message.reply_text(
            "📚 *Как пользоваться ботом*\n\n"
            "1️⃣ Отправьте ссылку на рецепт\n"
            "2️⃣ Бот обработает рецепт\n"
            "3️⃣ Нажмите «✅ Да» чтобы сохранить\n\n"
            "Сохраненные рецепты доступны в меню!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_menu_keyboard()
        )
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        text = update.message.text.strip()
        logger.info(f"📨 Получено сообщение: {text[:50]}")
        if text == "📚 Сохраненные рецепты":
            await self.show_saved_recipes(update, context)
        elif text == "ℹ️ Помощь":
            await self.help_command(update, context)
        elif text == "📋 Меню":
            await self.menu_command(update, context)
        elif text == "⬅️ Назад":
            await update.message.reply_text(
                "🏠 Главное окно. Нажмите «📋 Меню» чтобы открыть разделы.",
                reply_markup=self.get_main_keyboard()
            )
        elif text.startswith(('http://', 'https://')):
            await self.handle_url(update, context)
        else:
            await update.message.reply_text(
                "👋 *Отправьте ссылку на рецепт!*\n\n"
                "Пример: `https://eda.ru/recepty/...`",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_main_keyboard()
            )
    async def show_saved_recipes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показ сохраненных рецептов"""
        user_id = update.effective_user.id
        categories = self.storage.get_user_categories(user_id)
        if not categories:
            await update.message.reply_text(
                "📭 *Пока нет сохраненных рецептов*\n\n"
                "Отправьте ссылку на рецепт и нажмите «Да» чтобы сохранить!",
                parse_mode=ParseMode.MARKDOWN
            )
            return
        keyboard = []
        for cat in categories:
            button = InlineKeyboardButton(
                f"{cat['name']} ({cat['count']})",
                callback_data=f"cat_{cat['key']}"
            )
            keyboard.append([button])
        await update.message.reply_text(
            "📚 *Ваши сохраненные рецепты*\n\nВыберите категорию:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        print("🔥🔥🔥 CALLBACK HANDLER CALLED! 🔥🔥🔥")
        logger.info("🔥🔥🔥 CALLBACK HANDLER CALLED! 🔥🔥🔥")
        """Обработчик inline-кнопок"""
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        data = query.data
        logger.info(f"🔥 CALLBACK: {data} от user {user_id}")
        try:
            if data.startswith("save_"):
                recipe_id = data.replace("save_", "")
                await self.save_recipe_callback(query, user_id, recipe_id)
            elif data == "dont_save":
                await query.edit_message_text("👌 Рецепт не сохранен")
                if user_id in self.temp_recipes:
                    del self.temp_recipes[user_id]
            elif data.startswith("cat_"):
                category = data.replace("cat_", "")
                await self.show_recipes_in_category(query, user_id, category)
            elif data.startswith("view_"):
                parts = data.split("_", 2)
                if len(parts) >= 3:
                    await self.show_recipe(query, user_id, parts[1], parts[2])
            elif data.startswith("delete_"):
                parts = data.split("_", 2)
                if len(parts) >= 3:
                    await self.delete_recipe_callback(query, user_id, parts[1], parts[2])
            elif data == "back_to_categories":
                await self.show_categories_inline(query, user_id)
            else:
                logger.warning(f"⚠️ Неизвестный callback: {data}")
        except Exception as e:
            logger.error(f"❌ Ошибка в callback: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Произошла ошибка: {str(e)[:100]}")
    async def show_categories_inline(self, query, user_id: int):
        """Показ категорий в inline-режиме"""
        categories = self.storage.get_user_categories(user_id)
        if not categories:
            await query.edit_message_text("📭 Пока нет сохраненных рецептов")
            return
        keyboard = []
        for cat in categories:
            button = InlineKeyboardButton(
                f"{cat['name']} ({cat['count']})",
                callback_data=f"cat_{cat['key']}"
            )
            keyboard.append([button])
        await query.edit_message_text(
            "📚 *Выберите категорию:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    async def show_recipes_in_category(self, query, user_id: int, category: str):
        """Показ рецептов в категории"""
        recipes = self.storage.get_recipes_in_category(user_id, category)
        category_name = self.storage.get_category_name(category)
        if not recipes:
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_categories")]]
            await query.edit_message_text(
                f"📭 В категории «{category_name}» пока нет рецептов",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            return
        text = f"*{category_name}*\n\n"
        keyboard = []
        for i, recipe in enumerate(recipes[:15]):
            title = recipe['title'][:40]
            calories = recipe.get('calories', 0)
            cook_time = recipe.get('cook_time', 0)
            text += f"{i+1}. *{title}*\n"
            text += f"   🔥 {calories} ккал | ⏱ {cook_time} мин\n\n"
            button = InlineKeyboardButton(
                f"📖 {title[:30]}",
                callback_data=f"view_{category}_{recipe['recipe_uid']}"
            )
            keyboard.append([button])
        keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")])
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    async def show_recipe(self, query, user_id: int, category: str, recipe_uid: str):
        """Показ полного рецепта"""
        recipe = self.storage.get_recipe_by_uid(user_id, category, recipe_uid)
        if not recipe:
            await query.edit_message_text("❌ Рецепт не найден")
            return
        formatted = format_recipe_for_telegram(recipe)
        if len(formatted) > 4000:
            formatted = formatted[:4000] + "\n\n_(текст обрезан)_"
        keyboard = [[
            InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{category}_{recipe_uid}"),
            InlineKeyboardButton("◀️ Назад", callback_data=f"cat_{category}")
        ]]
        await query.edit_message_text(
            formatted,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    async def delete_recipe_callback(self, query, user_id: int, category: str, recipe_uid: str):
        """Удаление рецепта"""
        if self.storage.delete_recipe_by_uid(user_id, category, recipe_uid):
            keyboard = [[InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")]]
            await query.edit_message_text(
                "✅ Рецепт удален",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.edit_message_text("❌ Не удалось удалить рецепт")
    async def save_recipe_callback(self, query, user_id: int, recipe_id: str):
        """Сохранение рецепта"""
        logger.info(f"💾 Сохранение рецепта: user={user_id}, id={recipe_id}")
        if user_id not in self.temp_recipes:
            logger.error(f"❌ Рецепт {recipe_id} не найден в temp_recipes")
            await query.edit_message_text("❌ Рецепт не найден")
            return
        recipe = self.temp_recipes[user_id]
        logger.info(f"📄 Рецепт: {recipe.get('title', 'Без названия')}")
        try:
            result = self.storage.save_recipe(user_id, recipe)
            logger.info(f"✅ Сохранено: {result}")
            category = recipe.get('meal_type', 'другое').lower()
            category_key = self.storage.meal_type_to_category.get(category, 'other')
            category_name = self.storage.get_category_name(category_key)
            await query.edit_message_text(
                f"✅ *Рецепт сохранен!*\n\n"
                f"📁 Категория: {category_name}\n"
                f"📄 {recipe.get('title', 'Блюдо')}",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            logger.error(f"❌ Ошибка сохранения: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Ошибка при сохранении: {str(e)[:100]}")
        finally:
            if user_id in self.temp_recipes:
                del self.temp_recipes[user_id]
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка URL рецепта"""
        url = update.message.text.strip()
        user_id = update.effective_user.id
        if not validate_url(url):
            await update.message.reply_text("❌ Некорректная ссылка")
            return
        status_message = await update.message.reply_text("🔍 *Читаю страницу...*", parse_mode=ParseMode.MARKDOWN)
        try:
            raw_text = await self.parser.parse_recipe(url)
            await status_message.edit_text("🤖 *Анализирую рецепт...*", parse_mode=ParseMode.MARKDOWN)
            recipe = await self.normalizer.normalize(raw_text)
            recipe['source_url'] = url
            recipe_id = f"{user_id}_{int(datetime.now().timestamp())}"
            self.temp_recipes[user_id] = recipe
            logger.info(f"📦 Рецепт во временном хранилище: {recipe_id}")
            formatted_text = format_recipe_for_telegram(recipe)
            await status_message.delete()
            # Отправляем рецепт с кнопками сохранения в ОДНОМ сообщении
            await update.message.reply_text(
                formatted_text + "\n\n💾 *Сохранить этот рецепт?*",
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
                reply_markup=self.get_save_keyboard(recipe_id)
            )
        except Exception as e:
            logger.error(f"❌ Ошибка обработки URL: {e}", exc_info=True)
            await status_message.edit_text(f"❌ Ошибка: {str(e)[:200]}")
    async def post_init(self, application: Application):
        """Инициализация после запуска"""
        await self.setup_commands(application)
        logger.info("✅ Post-init выполнен")
    def run(self):
        """Запуск бота"""
        logger.info("🚀 Запуск приложения...")
        app = Application.builder().token(self.telegram_token).post_init(self.post_init).build()
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("menu", self.menu_command))
        app.add_handler(CommandHandler("saved", self.saved_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        logger.info("🤖 Бот готов к работе!")
        app.add_error_handler(self.error_handler)
        app.run_polling(drop_pending_updates=True)

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        logger.error(f"❌ Ошибка: {context.error}", exc_info=True)
        print(f"❌ Ошибка: {context.error}")

    async def cleanup(self):
        """Очистка ресурсов"""
        await self.parser.close()
        logger.info("🧹 Ресурсы очищены")
