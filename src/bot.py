from datetime import datetime
import os
import logging
from typing import Optional, Dict, Any

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ParseMode

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
        
        # Временное хранение рецепта перед сохранением
        self.temp_recipes: Dict[int, Dict[str, Any]] = {}
        
    def get_main_menu(self) -> ReplyKeyboardMarkup:
        """Создание главного меню"""
        keyboard = [
            [KeyboardButton("📋 Меню")],
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Создание инлайн меню"""
        keyboard = [
            [InlineKeyboardButton("📚 Сохраненные рецепты", callback_data="menu_saved")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="menu_help")],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /start"""
        welcome_text = (
            "👨‍🍳 *Recipe Parser Bot*\n\n"
            "Отправь мне ссылку на рецепт, и я:\n"
            "• Извлеку ингредиенты и шаги\n"
            "• Определю тип блюда\n"
            "• Рассчитаю КБЖУ\n\n"
            "Используй кнопку *📋 Меню* для навигации!"
        )
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_menu()
        )
    
    async def handle_menu_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки Меню"""
        await update.message.reply_text(
            "📋 *Главное меню*\n\nВыберите действие:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_menu_keyboard()
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик инлайн кнопок"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        data = query.data
        
        # Меню
        if data == "menu_saved":
            await self.show_categories(query, user_id)
        
        elif data == "menu_help":
            await self.show_help(query)
        
        # Сохранение рецепта
        elif data.startswith("save_"):
            recipe_id = data.replace("save_", "")
            await self.save_recipe_callback(query, user_id, recipe_id)
        
        elif data == "dont_save":
            await query.edit_message_text("👌 Рецепт не сохранен")
            if user_id in self.temp_recipes:
                del self.temp_recipes[user_id]
        
        # Навигация по категориям
        elif data.startswith("cat_"):
            category = data.replace("cat_", "")
            await self.show_recipes_in_category(query, user_id, category)
        
        # Просмотр рецепта
        elif data.startswith("view_"):
            parts = data.split("_")
            category = parts[1]
            filename = "_".join(parts[2:])
            await self.show_recipe(query, user_id, category, filename)
        
        # Удаление рецепта
        elif data.startswith("delete_"):
            parts = data.split("_")
            category = parts[1]
            filename = "_".join(parts[2:])
            await self.delete_recipe_callback(query, user_id, category, filename)
        
        # Назад к категориям
        elif data == "back_to_categories":
            await self.show_categories(query, user_id)
        
        # Назад в меню
        elif data == "back_to_menu":
            await query.edit_message_text(
                "📋 *Главное меню*\n\nВыберите действие:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_menu_keyboard()
            )
    
    async def show_categories(self, query, user_id: int):
        """Показ категорий сохраненных рецептов"""
        categories = self.storage.get_user_categories(user_id)
        
        if not categories:
            await query.edit_message_text(
                "📭 У вас пока нет сохраненных рецептов.\n\n"
                "Отправьте ссылку на рецепт и нажмите 'Да' чтобы сохранить!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]
                ])
            )
            return
        
        keyboard = []
        for cat in categories:
            keyboard.append([
                InlineKeyboardButton(
                    f"{cat['name']} ({cat['count']})",
                    callback_data=f"cat_{cat['key']}"
                )
            ])
        
        keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")])
        
        await query.edit_message_text(
            "📚 *Ваши сохраненные рецепты*\n\n"
            "Выберите категорию:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_recipes_in_category(self, query, user_id: int, category: str):
        """Показ рецептов в категории"""
        recipes = self.storage.get_recipes_in_category(user_id, category)
        category_name = self.storage.get_category_name(category)
        
        if not recipes:
            await query.edit_message_text(
                f"📭 В категории *{category_name}* пока нет рецептов",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")]
                ])
            )
            return
        
        # Показываем первые 10 рецептов
        text = f"*{category_name}*\n\n"
        keyboard = []
        
        for i, recipe in enumerate(recipes[:10]):
            emoji = "🍴"
            text += f"{i+1}. {recipe['title']}\n"
            text += f"   🔥 {recipe.get('calories', 0)} ккал | ⏱ {recipe.get('cook_time', 0)} мин\n\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"📖 {recipe['title'][:20]}",
                    callback_data=f"view_{category}_{recipe['filename']}"
                )
            ])
        
        if len(recipes) > 10:
            text += f"\n_... и еще {len(recipes) - 10} рецептов_"
        
        keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")])
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_recipe(self, query, user_id: int, category: str, filename: str):
        """Показ полного рецепта"""
        recipe = self.storage.get_recipe(user_id, category, filename)
        
        if not recipe:
            await query.edit_message_text(
                "❌ Рецепт не найден",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад", callback_data=f"cat_{category}")]
                ])
            )
            return
        
        formatted = format_recipe_for_telegram(recipe)
        
        keyboard = [
            [
                InlineKeyboardButton("🗑 Удалить", callback_data=f"delete_{category}_{filename}"),
                InlineKeyboardButton("◀️ Назад", callback_data=f"cat_{category}")
            ]
        ]
        
        await query.edit_message_text(
            formatted,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def delete_recipe_callback(self, query, user_id: int, category: str, filename: str):
        """Удаление рецепта"""
        if self.storage.delete_recipe(user_id, category, filename):
            await query.edit_message_text(
                "✅ Рецепт удален",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")]
                ])
            )
        else:
            await query.edit_message_text(
                "❌ Не удалось удалить рецепт",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад", callback_data=f"cat_{category}")]
                ])
            )
    
    async def show_help(self, query):
        """Показ помощи"""
        help_text = (
            "📚 *Как пользоваться:*\n\n"
            "1️⃣ Отправь ссылку на рецепт\n"
            "2️⃣ Бот обработает и покажет результат\n"
            "3️⃣ Нажми 'Да' чтобы сохранить\n"
            "4️⃣ Смотри сохраненные в Меню\n\n"
            "*Кнопки:*\n"
            "📋 Меню - главное меню\n"
            "📚 Сохраненные рецепты - просмотр сохраненных"
        )
        
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]
            ])
        )
    
    async def save_recipe_callback(self, query, user_id: int, recipe_id: str):
        """Сохранение рецепта"""
        if user_id not in self.temp_recipes:
            await query.edit_message_text("❌ Рецепт не найден")
            return
        
        recipe = self.temp_recipes[user_id]
        filepath = self.storage.save_recipe(user_id, recipe)
        
        category = recipe.get('meal_type', 'другое')
        category_name = self.storage.get_category_name(
            self.storage.meal_type_to_category.get(category.lower(), 'other')
        )
        
        await query.edit_message_text(
            f"✅ Рецепт сохранен!\n\n"
            f"📁 Категория: {category_name}\n"
            f"📄 {recipe.get('title', 'Блюдо')}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 Смотреть сохраненные", callback_data="menu_saved")],
                [InlineKeyboardButton("◀️ В меню", callback_data="back_to_menu")]
            ])
        )
        
        del self.temp_recipes[user_id]
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик URL"""
        url = update.message.text.strip()
        user_id = update.effective_user.id
        
        if not validate_url(url):
            await update.message.reply_text("❌ Некорректная ссылка")
            return
        
        status_message = await update.message.reply_text("🔍 Начинаю обработку рецепта...")
        
        try:
            # Парсинг
            await status_message.edit_text("🌐 Парсим страницу...")
            raw_text = await self.parser.parse_recipe(url)
            
            # Нормализация
            await status_message.edit_text("🤖 GPT-4o анализирует рецепт...")
            recipe = await self.normalizer.normalize(raw_text)
            recipe['source_url'] = url
            
            # Сохраняем во временное хранилище
            recipe_id = f"{user_id}_{int(datetime.now().timestamp())}"
            self.temp_recipes[user_id] = recipe
            
            # Форматируем
            formatted_text = format_recipe_for_telegram(recipe)
            
            # Удаляем статус
            await status_message.delete()
            
            # Отправляем результат с кнопками сохранения
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✅ Да", callback_data=f"save_{recipe_id}"),
                    InlineKeyboardButton("❌ Нет", callback_data="dont_save")
                ]
            ])
            
            await update.message.reply_text(
                formatted_text + "\n\n💾 *Сохранить рецепт?*",
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
            
            logger.info(f"✅ Рецепт обработан для пользователя {user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            await status_message.edit_text(f"❌ Ошибка: {str(e)[:200]}")
    
    def run(self):
        """Запуск бота"""
        app = Application.builder().token(self.telegram_token).build()
        
        # Обработчики команд
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("menu", self.handle_menu_button))
        
        # Обработчик кнопки Меню
        app.add_handler(MessageHandler(filters.Regex("^📋 Меню$"), self.handle_menu_button))
        
        # Обработчик URL
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_url))
        
        # Обработчик инлайн кнопок
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        logger.info("🚀 Бот запущен с меню и историей!")
        app.run_polling(drop_pending_updates=True)
    
    async def cleanup(self):
        await self.parser.close()

# Импорт для datetime
from datetime import datetime
