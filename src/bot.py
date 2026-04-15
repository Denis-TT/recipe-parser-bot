import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode
from telegram.helpers import escape_markdown

from parser import RecipeParser
from normalizer_github import GitHubModelNormalizer
from utils import format_recipe_for_telegram, save_recipe_to_file, validate_url
from storage import RecipeStorage

logger = logging.getLogger(__name__)

class RecipeBot:
    """Telegram бот для парсинга рецептов с историей"""

    def __init__(self, telegram_token: str, github_token: str):
        self.telegram_token = telegram_token
        self.parser = RecipeParser()
        self.normalizer = GitHubModelNormalizer(github_token)
        self.storage = RecipeStorage()
        self.temp_recipes: Dict[int, Dict[str, Any]] = {}

    def get_main_keyboard(self) -> ReplyKeyboardMarkup:
        keyboard = [[KeyboardButton("📋 Меню")]]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_menu_keyboard(self) -> ReplyKeyboardMarkup:
        keyboard = [
            [KeyboardButton("📚 Сохраненные рецепты"), KeyboardButton("ℹ️ Помощь")],
            [KeyboardButton("⬅️ Назад")],
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_save_keyboard(self, recipe_id: str) -> InlineKeyboardMarkup:
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, сохранить", callback_data=f"save_{recipe_id}"),
                InlineKeyboardButton("❌ Нет", callback_data="dont_save")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

    async def setup_commands(self, application: Application):
        # Убираем командное меню (кнопку "/" в Telegram), оставляя только reply-клавиатуру.
        await application.bot.set_my_commands([])

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        welcome_text = "👨‍🍳 *Привет, шеф-повар!*\n\nЯ бот для парсинга и сохранения рецептов.\n\n*Что я умею:*\n• Извлекать рецепты с любых сайтов\n• Определять тип блюда и КБЖУ\n• Сохранять рецепты в избранное\n\nОтправь мне ссылку на рецепт или используй кнопки ниже!"
        await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_main_keyboard())

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("📋 *Главное меню*\n\nИспользуйте кнопки ниже для навигации:\n• 📚 Сохраненные рецепты - просмотр избранного\n• ℹ️ Помощь - справка\n\n💡 *Чтобы обработать рецепт, просто отправьте ссылку на него!*", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_menu_keyboard())

    async def saved_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.show_saved_recipes(update, context)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        help_text = "📚 *Как пользоваться ботом:*\n\n1️⃣ Нажмите «📋 Меню»\n2️⃣ Выберите «📚 Сохраненные рецепты» или отправьте ссылку\n3️⃣ После обработки нажмите «✅ Да», чтобы сохранить рецепт"
        await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_menu_keyboard())

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text.strip()
        if text == "📚 Сохраненные рецепты":
            await self.show_saved_recipes(update, context)
        elif text == "ℹ️ Помощь":
            await self.help_command(update, context)
        elif text == "📋 Меню":
            await self.menu_command(update, context)
        elif text == "⬅️ Назад":
            await update.message.reply_text("🏠 Главное окно. Нажмите «📋 Меню», чтобы открыть разделы.", reply_markup=self.get_main_keyboard())
        elif text.startswith(('http://', 'https://')):
            await self.handle_url(update, context)
        else:
            await update.message.reply_text("👋 *Отправьте ссылку на рецепт!*\n\nПример: `https://eda.ru/recepty/...`\n\nИли используйте кнопки меню ниже.", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_main_keyboard())

    async def show_saved_recipes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        categories = self.storage.get_user_categories(user_id)
        if not categories:
            await update.message.reply_text("📭 *Пока нет сохраненных рецептов*\n\nОтправьте ссылку на рецепт и нажмите 'Да' чтобы сохранить!", parse_mode=ParseMode.MARKDOWN)
            return
        keyboard = []
        for cat in categories:
            keyboard.append([InlineKeyboardButton(f"{cat['name']} ({cat['count']})", callback_data=f"cat_{cat['key']}")])
        await update.message.reply_text("📚 *Ваши сохраненные рецепты*\n\nВыберите категорию:", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        data = query.data
        logger.info(f"Callback: {data}")

        if data == "menu_saved":
            await self.show_categories_inline(query, user_id)
        elif data.startswith("save_"):
            await self.save_recipe_callback(query, user_id, data.replace("save_", ""))
        elif data == "dont_save":
            await query.edit_message_text("👌 *Рецепт не сохранен*", parse_mode=ParseMode.MARKDOWN)
            if user_id in self.temp_recipes:
                del self.temp_recipes[user_id]
        elif data.startswith("cat_"):
            await self.show_recipes_in_category(query, user_id, data.replace("cat_", ""))
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
        elif data == "back_to_menu":
            await query.delete_message()

    async def show_categories_inline(self, query, user_id: int):
        categories = self.storage.get_user_categories(user_id)
        if not categories:
            await query.edit_message_text("📭 *Пока нет сохраненных рецептов*", parse_mode=ParseMode.MARKDOWN)
            return
        keyboard = []
        for cat in categories:
            keyboard.append([InlineKeyboardButton(f"{cat['name']} ({cat['count']})", callback_data=f"cat_{cat['key']}")])
        await query.edit_message_text("📚 *Ваши сохраненные рецепты*\n\nВыберите категорию:", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

    async def show_recipes_in_category(self, query, user_id: int, category: str):
        recipes = self.storage.get_recipes_in_category(user_id, category)
        category_name = self.storage.get_category_name(category)
        if not recipes:
            await query.edit_message_text(f"📭 *В категории «{category_name}» пока нет рецептов*", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="back_to_categories")]]))
            return
        text = f"*{category_name}*\n\n"
        keyboard = []
        for i, recipe in enumerate(recipes[:15]):
            title = recipe['title'][:40]
            escaped_title = escape_markdown(title, version=1)
            text += f"{i+1}. *{escaped_title}*\n   🔥 {recipe.get('calories', 0)} ккал | ⏱ {recipe.get('cook_time', 0)} мин\n\n"
            keyboard.append([InlineKeyboardButton(f"📖 {title[:30]}", callback_data=f"view_{category}_{recipe['recipe_uid']}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
        escaped_title = escape_markdown(title, version=2)
        text += f"{i+1}. *{escaped_title}*\n   🔥 {recipe.get('calories', 0)} ккал | ⏱ {recipe.get('cook_time', 0)} мин\n\n"
        keyboard.append([InlineKeyboardButton(f"📖 {title[:30]}", callback_data=f"view_{category}_{recipe['recipe_uid']}")])
        keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN_V2, reply_markup=InlineKeyboardMarkup(keyboard))
main+history

async def show_recipe(self, query, user_id: int, category: str, recipe_uid: str):
    recipe = self.storage.get_recipe_by_uid(user_id, category, recipe_uid)
    if not recipe:
        await query.edit_message_text("❌ Рецепт не найден")
        return
        formatted = format_recipe_for_telegram(recipe)
        if len(formatted) > 4000:
            formatted = formatted[:4000] + "\n\n_(текст обрезан)_"
        keyboard = [[InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{category}_{recipe_uid}"), InlineKeyboardButton("◀️ Назад", callback_data=f"cat_{category}")]]
        await query.edit_message_text(formatted, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

    async def delete_recipe_callback(self, query, user_id: int, category: str, recipe_uid: str):
        if self.storage.delete_recipe_by_uid(user_id, category, recipe_uid):
            await query.edit_message_text("✅ *Рецепт удален*", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")]]))
        else:
            await query.edit_message_text("❌ Не удалось удалить рецепт")

    async def save_recipe_callback(self, query, user_id: int, recipe_id: str):
        if user_id not in self.temp_recipes:
            await query.edit_message_text("❌ *Рецепт не найден*", parse_mode=ParseMode.MARKDOWN)
            return
        recipe = self.temp_recipes[user_id]
        self.storage.save_recipe(user_id, recipe)
        category = recipe.get('meal_type', 'другое').lower()
        category_name = self.storage.get_category_name(self.storage.meal_type_to_category.get(category, 'other'))
        await query.edit_message_text(f"✅ *Рецепт сохранен в избранное!*\n\n📁 Категория: {category_name}\n📄 {recipe.get('title', 'Блюдо')}", parse_mode=ParseMode.MARKDOWN)
        del self.temp_recipes[user_id]

    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        url = update.message.text.strip()
        user_id = update.effective_user.id
        if not validate_url(url):
            await update.message.reply_text("❌ *Это некорректная ссылка*", parse_mode=ParseMode.MARKDOWN)
            return
        status_message = await update.message.reply_text("🔍 *Читаю страницу, один момент...*", parse_mode=ParseMode.MARKDOWN)
        try:
            raw_text = await self.parser.parse_recipe(url)
            await status_message.edit_text("🤖 *Анализирую рецепт и считаю КБЖУ...*", parse_mode=ParseMode.MARKDOWN)
            recipe = await self.normalizer.normalize(raw_text)
            recipe['source_url'] = url
            recipe_id = f"{user_id}_{int(datetime.now().timestamp())}"
            self.temp_recipes[user_id] = recipe
            formatted_text = format_recipe_for_telegram(recipe)
            await status_message.delete()
            await update.message.reply_text(formatted_text, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
            await update.message.reply_text("💾 *Сохранить этот рецепт в избранное?*", parse_mode=ParseMode.MARKDOWN, reply_markup=self.get_save_keyboard(recipe_id))
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            await status_message.edit_text(f"❌ *Упс, что-то пошло не так:*\n`{str(e)[:200]}`", parse_mode=ParseMode.MARKDOWN)

    async def post_init(self, application: Application):
        await self.setup_commands(application)

    def run(self):
        app = Application.builder().token(self.telegram_token).post_init(self.post_init).build()
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("menu", self.menu_command))
        app.add_handler(CommandHandler("saved", self.saved_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        logger.info("🚀 Бот запущен!")
        app.run_polling(drop_pending_updates=True)

    async def cleanup(self):
        await self.parser.close()
