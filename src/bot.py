import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime

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
        """Создание клавиатуры с кнопкой Меню"""
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
    
    def get_save_keyboard(self, recipe_id: str) -> InlineKeyboardMarkup:
        """Клавиатура для сохранения рецепта"""
        keyboard = [
            [
                InlineKeyboardButton("✅ Да, сохранить", callback_data=f"save_{recipe_id}"),
                InlineKeyboardButton("❌ Нет", callback_data="dont_save")
            ]
        ]
        return InlineKeyboardMarkup(keyboard)
    
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик /start"""
        user_name = self.get_user_name(update)
        
        welcome_text = (
            f"👨‍🍳 *Привет, {user_name}!*\n\n"
            "Я бот для парсинга и сохранения рецептов.\n\n"
            "*Что я умею:*\n"
            "• Извлекать рецепты с любых сайтов\n"
            "• Определять тип блюда и КБЖУ\n"
            "• Сохранять рецепты в избранное\n\n"
            "Отправь мне ссылку на рецепт или нажми *📋 Меню*!"
        )
        
        await update.message.reply_text(
            welcome_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard()
        )
    
    async def handle_menu_button(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик кнопки Меню"""
        user_name = self.get_user_name(update)
        
        await update.message.reply_text(
            f"📋 *{user_name}, главное меню*\n\nВыберите действие:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_menu_keyboard()
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
                await self.show_help(query, user_name)
            
            # Сохранение рецепта
            elif data.startswith("save_"):
                recipe_id = data.replace("save_", "")
                logger.info(f"→ Сохраняем рецепт {recipe_id}")
                await self.save_recipe_callback(query, user_id, user_name, recipe_id)
            
            elif data == "dont_save":
                logger.info("→ Отмена сохранения")
                await query.edit_message_text(f"👌 {user_name}, рецепт не сохранен")
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
                await query.edit_message_text(
                    f"📋 *{user_name}, главное меню*\n\nВыберите действие:",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=self.get_menu_keyboard()
                )
            
            else:
                logger.warning(f"⚠️ Неизвестный callback: {data}")
                await query.edit_message_text(
                    f"❌ Неизвестная команда: {data}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📋 В меню", callback_data="back_to_menu")]
                    ])
                )
                
        except Exception as e:
            logger.error(f"❌ Ошибка в callback {data}: {e}", exc_info=True)
            try:
                await query.edit_message_text(
                    f"❌ *{user_name}, произошла ошибка*\n\nПопробуйте еще раз или вернитесь в меню.",
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📋 В меню", callback_data="back_to_menu")]
                    ])
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
                f"📭 *{user_name}, у вас пока нет сохраненных рецептов*\n\n"
                "Отправьте ссылку на рецепт и нажмите 'Да' чтобы сохранить!",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]
                ])
            )
            return
        
        keyboard = []
        for cat in categories:
            callback_data = f"cat_{cat['key']}"
            button_text = f"{cat['name']} ({cat['count']})"
            keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])
            logger.info(f"  → Добавлена кнопка: {button_text} -> {callback_data}")
        
        keyboard.append([InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")])
        
        await query.edit_message_text(
            f"📚 *{user_name}, ваши сохраненные рецепты*\n\n"
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
            
            # Кнопка для просмотра рецепта
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
            ],
            [InlineKeyboardButton("📋 В главное меню", callback_data="back_to_menu")]
        ]
        
        # Обрезаем если слишком длинное
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
                f"✅ *{user_name}, рецепт удален*",
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
    
    async def show_help(self, query, user_name: str):
        """Показ помощи"""
        help_text = (
            f"📚 *{user_name}, как пользоваться ботом:*\n\n"
            "1️⃣ Отправьте ссылку на рецепт\n"
            "2️⃣ Бот обработает и покажет результат\n"
            "3️⃣ Нажмите '✅ Да' чтобы сохранить рецепт\n"
            "4️⃣ Смотрите сохраненные рецепты через *📋 Меню*\n\n"
            "*Кнопки:*\n"
            "📋 Меню - открыть главное меню\n"
            "📚 Сохраненные рецепты - просмотр избранного"
        )
        
        await query.edit_message_text(
            help_text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("◀️ Назад в меню", callback_data="back_to_menu")]
            ])
        )
    
    async def save_recipe_callback(self, query, user_id: int, user_name: str, recipe_id: str):
        """Сохранение рецепта"""
        logger.info(f"💾 Сохранение рецепта {recipe_id} для пользователя {user_id}")
        
        if user_id not in self.temp_recipes:
            logger.error(f"❌ Рецепт {recipe_id} не найден во временном хранилище")
            await query.edit_message_text(f"❌ {user_name}, рецепт не найден")
            return
        
        recipe = self.temp_recipes[user_id]
        filepath = self.storage.save_recipe(user_id, recipe)
        
        category = recipe.get('meal_type', 'другое').lower()
        category_key = self.storage.meal_type_to_category.get(category, 'other')
        category_name = self.storage.get_category_name(category_key)
        
        logger.info(f"✅ Рецепт сохранен в {filepath}")
        
        await query.edit_message_text(
            f"✅ *{user_name}, рецепт сохранен!*\n\n"
            f"📁 Категория: {category_name}\n"
            f"📄 {recipe.get('title', 'Блюдо')}",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📚 Смотреть сохраненные", callback_data="menu_saved")],
                [InlineKeyboardButton("📋 В главное меню", callback_data="back_to_menu")]
            ])
        )
        
        del self.temp_recipes[user_id]
    
    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик URL"""
        url = update.message.text.strip()
        user_id = update.effective_user.id
        user_name = self.get_user_name(update)
        
        if not validate_url(url):
            await update.message.reply_text(f"❌ {user_name}, это некорректная ссылка")
            return
        
        status_message = await update.message.reply_text(
            f"🔍 *{user_name}, бот читает страницу...*",
            parse_mode=ParseMode.MARKDOWN
        )
        
        try:
            # Парсинг
            raw_text = await self.parser.parse_recipe(url)
            
            await status_message.edit_text(
                f"🤖 *{user_name}, анализирую рецепт и считаю КБЖУ...*",
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
                f"💾 *{user_name}, сохранить этот рецепт?*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_save_keyboard(recipe_id)
            )
            
            logger.info(f"✅ Рецепт обработан для пользователя {user_id}")
            
        except Exception as e:
            logger.error(f"Ошибка: {e}")
            await status_message.edit_text(
                f"❌ *{user_name}, произошла ошибка:*\n`{str(e)[:200]}`",
                parse_mode=ParseMode.MARKDOWN
            )
    
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
