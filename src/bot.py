import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand
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
        
    def get_user_name(self, update: Update) -> str:
        """Получение имени пользователя"""
        user = update.effective_user
        if user.first_name:
            return user.first_name
        elif user.username:
            return user.username
        else:
            return "Пользователь"
    
    def get_main_keyboard(self) -> ReplyKeyboardMarkup:
        """Создание основной клавиатуры с кнопками"""
        keyboard = [
            [KeyboardButton("📚 Сохраненные рецепты"), KeyboardButton("ℹ️ Помощь")],
            [KeyboardButton("📋 Меню")],
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    def get_menu_keyboard(self) -> InlineKeyboardMarkup:
        """Создание инлайн меню (для совместимости)"""
        keyboard = [
            [InlineKeyboardButton("📚 Сохраненные рецепты", callback_data="menu_saved")],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="menu_help")],
        ]
        return InlineKeyboardMarkup(keyboard)
    
    def get_save_keyboard(self, recipe_id: str) -> InlineKeyboardMarkup:
        """Клавиатура для сохранения рецепта"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, сохранить", callback_data=f"save_{recipe_id}"),
                InlineKeyboardButton("❌ Нет", callback_data="dont_save")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def setup_commands(self, application: Application):
        """Настройка меню команд бота"""
        commands = [
            BotCommand("start", "🚀 Начать работу"),
            BotCommand("menu", "📋 Показать меню"),
            BotCommand("saved", "📚 Сохраненные рецепты"),
            BotCommand("help", "ℹ️ Помощь"),
        ]
        await application.bot.set_my_commands(commands)
        logger.info("✅ Меню команд настроено")
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /start"""
        user_name = self.get_user_name(update)
        
        welcome_text = (
            f"👨‍🍳 *Привет, шеф-повар!*

"
            "Я бот для парсинга и сохранения рецептов.\n\n"
            "*Что я умею:*\n"
            "• Извлекать рецепты с любых сайтов\n"
            "• Определять тип блюда и КБЖУ\n"
            "• Сохранять рецепты в избранное\n\n"
            "Отправь мне ссылку на рецепт или используй кнопки ниже!"
        )
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard()
        )
    
    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /menu"""
        user_name = self.get_user_name(update)
        
        await update.message.reply_text(
            f"📋 *Главное меню*

"
            "Выберите действие на клавиатуре:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard()
        )
    
    async def saved_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /saved"""
        await self.show_saved_recipes(update, context)
    
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /help"""
        user_name = self.get_user_name(update)
        
        help_text = (
            f"📚 *Как пользоваться ботом:*

"
            "1️⃣ Отправьте ссылку на рецепт\n"
            "2️⃣ Бот обработает и покажет результат\n"
            "3️⃣ Нажмите '✅ Да' чтобы сохранить рецепт\n\n"
            "*Кнопки меню:*\n"
            "📚 Сохраненные рецепты - просмотр избранного\n"
            "ℹ️ Помощь - эта справка\n"
            "📋 Меню - показать клавиатуру\n\n"
            "Или используйте команды в меню слева от ввода!"
        )
        
        await update.message.reply_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard()
        )
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        text = update.message.text.strip()
        user_name = self.get_user_name(update)
        
        # Обработка кнопок Reply Keyboard
        if text == "📚 Сохраненные рецепты":
            await self.show_saved_recipes(update, context)
        
        elif text == "ℹ️ Помощь":
            await self.help_command(update, context)
        
        elif text == "📋 Меню":
            await update.message.reply_text(
                f"📋 *Главное меню*

"
                "Используйте кнопки ниже для навигации:",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_main_keyboard()
            )
        
        # Если это URL - обрабатываем как рецепт
        elif text.startswith(('http://', 'https://')):
            await self.handle_url(update, context)
        
        # Обычное сообщение
        else:
            await update.message.reply_text(
                f"👋 *Отправьте ссылку на рецепт!*

"
                "Или используйте кнопки меню ниже.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_main_keyboard()
            )
    
    async def show_saved_recipes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Показ сохраненных рецептов"""
        user_id = update.effective_user.id
        user_name = self.get_user_name(update)
        
        categories = self.storage.get_user_categories(user_id)
        
        if not categories:
            await update.message.reply_text(
                f"📭 *Пока нет сохраненных рецептов*

"
                "Отправьте ссылку на рецепт и нажмите 'Да' чтобы сохранить!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад", callback_data="back_to_menu")]
                ])
            )
            return
        
        keyboard = []
        for cat in categories:
            callback_data = f"cat_{cat['key']}"
            button_text = f"{cat['name']} ({cat['count']})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            logger.info(f"  → Добавлена кнопка: {button_text} -> {callback_data}")
        
        await update.message.reply_text(
            f"📚 *Ваши сохраненные рецепты*

"
            "Выберите категорию:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик инлайн кнопок"""
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "Пользователь"
        data = query.data
        
        logger.info(f"📱 Callback получен: '{data}' от пользователя {user_id}")
        
        try:
            # Меню
            if data == "menu_saved":
                logger.info("→ Показываем категории")
                await self.show_categories(query, user_id, user_name)
            
            elif data == "menu_help":
                logger.info("→ Показываем помощь")
                await self.show_help_inline(query, user_name)
            
            # Сохранение рецепта
            elif data.startswith("save_"):
                recipe_id = data.replace("save_", "")
                logger.info(f"→ Сохраняем рецепт {recipe_id}")
                await self.save_recipe_callback(query, user_id, user_name, recipe_id)
            
            elif data == "dont_save":
                logger.info("→ Отмена сохранения")
                await query.edit_message_text(f"👌 *Рецепт не сохранен*")
                if user_id in self.temp_recipes:
                    del self.temp_recipes[user_id]
            
            # Навигация по категориям
            elif data.startswith("cat_"):
                category = data.replace("cat_", "")
                logger.info(f"→ Открываем категорию: {category}")
                await self.show_recipes_in_category(query, user_id, user_name, category)
            
            # Просмотр рецепта
            elif data.startswith("view_"):
                parts = data.split("_", 2)
                if len(parts) >= 3:
                    category = parts[1]
                    filename = parts[2]
                    logger.info(f"→ Просмотр рецепта: {category}/{filename}")
                    await self.show_recipe(query, user_id, user_name, category, filename)
                else:
                    logger.error(f"❌ Неверный формат view: {data}")
            
            # Удаление рецепта
            elif data.startswith("delete_"):
                parts = data.split("_", 2)
                if len(parts) >= 3:
                    category = parts[1]
                    filename = parts[2]
                    logger.info(f"→ Удаление рецепта: {category}/{filename}")
                    await self.delete_recipe_callback(query, user_id, user_name, category, filename)
                else:
                    logger.error(f"❌ Неверный формат delete: {data}")
            
            # Назад к категориям
            elif data == "back_to_categories":
                logger.info("→ Назад к категориям")
                await self.show_categories(query, user_id, user_name)
            
            # Назад в меню
            elif data == "back_to_menu":
                logger.info("→ Назад в меню")
                await query.delete_message()
                # Отправляем новое сообщение с клавиатурой
                await query.message.reply_text(
                    f"📋 *Главное меню*

"
                    "Используйте кнопки ниже:",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.get_main_keyboard()
                )
            
            else:
                logger.warning(f"⚠️ Неизвестный callback: {data}")
                
        except Exception as e:
            logger.error(f"❌ Ошибка в callback {data}: {e}", exc_info=True)
            try:
                await query.edit_message_text(
                    "❌ *, произошла ошибка*\n\nПопробуйте еще раз.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except:
                pass
    
    async def show_categories(self, query, user_id: int, user_name: str):
        """Показ категорий сохраненных рецептов"""
        logger.info(f"📂 Получаем категории для пользователя {user_id}")
        categories = self.storage.get_user_categories(user_id)
        logger.info(f"📂 Найдено категорий: {len(categories)}")
        
        if not categories:
            await query.edit_message_text(
                f"📭 *Пока нет сохраненных рецептов*

"
                "Отправьте ссылку на рецепт и нажмите 'Да' чтобы сохранить!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Закрыть", callback_data="back_to_menu")]
                ])
            )
            return
        
        keyboard = []
        for cat in categories:
            callback_data = f"cat_{cat['key']}"
            button_text = f"{cat['name']} ({cat['count']})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
        
        keyboard.append([InlineKeyboardButton("◀️ Закрыть", callback_data="back_to_menu")])
        
        await query.edit_message_text(
            f"📚 *Ваши сохраненные рецепты*

"
            "Выберите категорию:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_recipes_in_category(self, query, user_id: int, user_name: str, category: str):
        """Показ рецептов в категории"""
        logger.info(f"📖 Получаем рецепты в категории '{category}' для пользователя {user_id}")
        recipes = self.storage.get_recipes_in_category(user_id, category)
        category_name = self.storage.get_category_name(category)
        logger.info(f"📖 Найдено рецептов: {len(recipes)}")
        
        if not recipes:
            await query.edit_message_text(
                f"📭 *В категории «{category_name}» пока нет рецептов*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")]
                ])
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
            
            callback_data = f"view_{category}_{recipe['filename']}"
            keyboard.append([InlineKeyboardButton(f"📖 {title[:30]}", callback_data=callback_data)])
        
        if len(recipes) > 15:
            text += f"\n_... и еще {len(recipes) - 15} рецептов_"
        
        keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")])
        
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def show_recipe(self, query, user_id: int, user_name: str, category: str, filename: str):
        """Показ полного рецепта"""
        logger.info(f"👁 Просмотр рецепта: {category}/{filename}")
        recipe = self.storage.get_recipe(user_id, category, filename)
        
        if not recipe:
            logger.error(f"❌ Рецепт не найден: {category}/{filename}")
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
                InlineKeyboardButton("◀️ Назад к списку", callback_data=f"cat_{category}")
            ]
        ]
        
        if len(formatted) > 4000:
            formatted = formatted[:4000] + "\n\n_(текст обрезан)_"
        
        await query.edit_message_text(
            formatted,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    async def delete_recipe_callback(self, query, user_id: int, user_name: str, category: str, filename: str):
        """Удаление рецепта"""
        logger.info(f"🗑 Удаление рецепта: {category}/{filename}")
        
        if self.storage.delete_recipe(user_id, category, filename):
            await query.edit_message_text(
                f"✅ *Рецепт удален*",
                parse_mode=ParseMode.MARKDOWN,
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
    
    async def show_help_inline(self, query, user_name: str):
        """Показ помощи через инлайн"""
        help_text = (
            "📚 *, как пользоваться:*\n\n"
            "• Отправьте ссылку на рецепт\n"
            "• Нажмите 'Да' чтобы сохранить\n"
            "• Используйте кнопки меню для навигации"
        )
        
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Закрыть", callback_data="back_to_menu")]
            ])
        )
    
        async def save_recipe_callback(self, query, user_id: int, user_name: str, recipe_id: str):
        """Сохранение рецепта"""
        logger.info(f"💾 Сохранение рецепта {recipe_id} для пользователя {user_id}")
        
        if user_id not in self.temp_recipes:
            logger.error(f"❌ Рецепт {recipe_id} не найден")
            await query.edit_message_text("❌ , рецепт не найден")
            return
        
        recipe = self.temp_recipes[user_id]
        filepath = self.storage.save_recipe(user_id, recipe)
        
        category = recipe.get('meal_type', 'другое').lower()
        category_key = self.storage.meal_type_to_category.get(category, 'other')
        category_name = self.storage.get_category_name(category_key)
        
        logger.info(f"✅ Рецепт сохранен в {filepath}")
        
        # Просто подтверждаем сохранение без дополнительных кнопок
        await query.edit_message_text(
            "✅ *, рецепт сохранен!*

"
            f"📁 Категория: {category_name}
"
            f"📄 {recipe.get('title', 'Блюдо')}",
            parse_mode=ParseMode.MARKDOWN
        )
        
        del self.temp_recipes[user_id]
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик URL"""
        url = update.message.text.strip()
        user_id = update.effective_user.id
        user_name = self.get_user_name(update)
        
        if not validate_url(url):
            await update.message.reply_text(
                f"❌ *Это некорректная ссылка*",
                reply_markup=self.get_main_keyboard()
            )
            return
        
        status_message = await update.message.reply_text(
            f"🔍 *Читаю страницу, один момент\.\.\.*",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            # Парсинг
            raw_text = await self.parser.parse_recipe(url)
            
            await status_message.edit_text(
                f"🤖 *Анализирую рецепт и считаю КБЖУ\.\.\.*",
                parse_mode=ParseMode.MARKDOWN
            )
            
            # Нормализация
            recipe = await self.normalizer.normalize(raw_text)
            recipe['source_url'] = url
            
            # Сохраняем во временное хранилище
            recipe_id = f"{user_id}_{int(datetime.now().timestamp())}"
            self.temp_recipes[user_id] = recipe
            
            # Форматируем
            formatted_text = format_recipe_for_telegram(recipe)
            
            # Удаляем статус
            await status_message.delete()
            
            # Отправляем результат
            await update.message.reply_text(
                formatted_text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            
            # Кнопки сохранения отдельным сообщением
            await update.message.reply_text(
                f"💾 *Сохранить этот рецепт в избранное?*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_save_keyboard(recipe_id)
            )
            
            logger.info(f"✅ Рецепт обработан для пользователя {user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            await status_message.edit_text(
                "❌ *, произошла ошибка:*\n`{str(e)[:200]}`",
                parse_mode=ParseMode.MARKDOWN
            )
    
    async def post_init(self, application: Application):
        """Вызывается после инициализации приложения"""
        await self.setup_commands(application)
    
    def run(self):
        """Запуск бота"""
        app = Application.builder().token(self.telegram_token).post_init(self.post_init).build()
        
        # Обработчики команд
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("menu", self.menu_command))
        app.add_handler(CommandHandler("saved", self.saved_command))
        app.add_handler(CommandHandler("help", self.help_command))
        
        # Обработчик текстовых сообщений (включая кнопки Reply Keyboard)
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        
        # Обработчик инлайн кнопок
        app.add_handler(CallbackQueryHandler(self.handle_callback))
        
        logger.info("🚀 Бот запущен с Reply Keyboard меню!")
        app.run_polling(drop_pending_updates=True)
    
    async def cleanup(self):
        await self.parser.close()

    # В методе handle_message добавляем подсказку для обычных сообщений
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик текстовых сообщений"""
        text = update.message.text.strip()
        user_name = self.get_user_name(update)
        
        # Обработка кнопок Reply Keyboard
        if text == "📚 Сохраненные рецепты":
            await self.show_saved_recipes(update, context)
        
        elif text == "ℹ️ Помощь":
            await self.help_command(update, context)
        
        elif text == "📋 Меню":
            await update.message.reply_text(
                f"📋 *Главное меню*

"
                "Используйте кнопки ниже для навигации:\n"
                "• 📚 Сохраненные рецепты - просмотр избранного\n"
                "• ℹ️ Помощь - справка\n\n"
                "💡 *Чтобы обработать рецепт, просто отправьте ссылку на него!*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_main_keyboard()
            )
        
        # Если это URL - обрабатываем как рецепт
        elif text.startswith(('http://', 'https://')):
            await self.handle_url(update, context)
        
        # Обычное сообщение - подсказываем
        else:
            await update.message.reply_text(
                f"👋 *Отправьте ссылку на рецепт!*

"
                "Пример: `https://eda.ru/recepty/...`\n\n"
                "Или используйте кнопки меню ниже.",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_main_keyboard()
            )
