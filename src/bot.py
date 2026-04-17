import asyncio
import logging
import os
import time
from typing import Any, Dict, Optional

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    WebAppInfo,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackContext,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from normalizer_github import GitHubModelNormalizer
from parser import RecipeParser
from storage import RecipeStorage
from utils import format_recipe_for_telegram, validate_url

logger = logging.getLogger(__name__)


class RecipeBot:
    """Telegram бот для парсинга и сохранения рецептов."""

    TEMP_TTL_SECONDS = 20 * 60
    MAX_PARSE_RETRIES = 3
    CATEGORY_KEY_ALIASES = {
        "завтрак": "breakfast",
        "обед": "lunch",
        "ужин": "dinner",
        "десерт": "dessert",
        "перекус": "snack",
        "закуска": "snack",
        "салат": "salad",
        "суп": "soup",
        "выпечка": "baking",
        "напиток": "drink",
        "другое": "other",
        "основное блюдо": "dinner",
    }
    MEAL_TYPE_NAMES = {
        "breakfast": "🍳 Завтраки",
        "lunch": "🍲 Обеды",
        "dinner": "🍽️ Ужины",
        "dessert": "🍰 Десерты",
        "snack": "🥨 Перекусы",
        "salad": "🥗 Салаты",
        "soup": "🥣 Супы",
        "baking": "🧁 Выпечка",
        "drink": "🥤 Напитки",
        "other": "📦 Другое",
    }

    def __init__(self, telegram_token: str, github_token: str):
        self.telegram_token = telegram_token
        self.parser = RecipeParser()
        self.normalizer = GitHubModelNormalizer(github_token)
        self.storage = RecipeStorage()
        self.temp_recipes: Dict[int, Dict[str, Any]] = {}
        self.last_request_at: Dict[int, float] = {}
        logger.info("🤖 RecipeBot инициализирован")

    # ========== КЛАВИАТУРЫ ==========

    def get_main_keyboard(self) -> ReplyKeyboardMarkup:
        keyboard = [[KeyboardButton("📋 Меню")]]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_menu_keyboard(self) -> ReplyKeyboardMarkup:
        keyboard = [
            [KeyboardButton("📚 Сохраненные рецепты"), KeyboardButton("ℹ️ Помощь")],
            [KeyboardButton("⬅️ Назад")],
        ]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    def get_save_keyboard(self) -> ReplyKeyboardMarkup:
        keyboard = [[KeyboardButton("✅ Да, сохранить"), KeyboardButton("❌ Нет")]]
        return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

    # ========== ИНИЦИАЛИЗАЦИЯ ==========

    async def setup_commands(self, application: Application) -> None:
        await application.bot.set_my_commands([])

    async def post_init(self, application: Application) -> None:
        await self.setup_commands(application)
        logger.info("✅ Post-init выполнен")

    async def post_shutdown(self, _application: Application) -> None:
        await self.cleanup()

    async def global_error_handler(
        self,
        update: Optional[object],
        context: CallbackContext,
    ) -> None:
        logger.error("❌ Глобальная ошибка в update=%s", update, exc_info=context.error)

        if isinstance(update, Update) and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ Произошла ошибка на нашей стороне. Попробуйте снова через минуту."
            )

    # ========== КОМАНДЫ ==========

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "👨‍🍳 *Привет, шеф-повар!*\n\n"
            "Я бот для парсинга и сохранения рецептов.\n\n"
            "Отправь мне ссылку на рецепт или используй кнопки ниже!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard(),
        )

    async def menu_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        webapp_url = os.environ.get("WEBAPP_URL", "https://your-app.railway.app")
        keyboard = [
            [InlineKeyboardButton("📚 Сохраненные рецепты", web_app=WebAppInfo(url=webapp_url))],
            [InlineKeyboardButton("ℹ️ Помощь", callback_data="menu_help")],
        ]
        await update.message.reply_text(
            "📋 *Главное меню*\n\nВыберите действие:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def saved_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self.show_saved_recipes(update, context)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "📚 *Как пользоваться ботом*\n\n"
            "1️⃣ Отправьте ссылку на рецепт\n"
            "2️⃣ Бот обработает рецепт\n"
            "3️⃣ Нажмите «✅ Да, сохранить» чтобы сохранить\n\n"
            "Сохраненные рецепты доступны в меню!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_menu_keyboard(),
        )

    # ========== ОБРАБОТКА СООБЩЕНИЙ ==========

    def _cleanup_temp_recipes(self) -> None:
        now = time.time()
        expired = [
            user_id
            for user_id, payload in self.temp_recipes.items()
            if now - payload.get("created_at_ts", now) > self.TEMP_TTL_SECONDS
        ]
        for user_id in expired:
            del self.temp_recipes[user_id]
            logger.info("🧹 Удален протухший временный рецепт для user_id=%s", user_id)

    def _is_rate_limited(self, user_id: int) -> bool:
        now = time.time()
        previous = self.last_request_at.get(user_id)
        self.last_request_at[user_id] = now
        return previous is not None and (now - previous) < 1.0

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = (update.message.text or "").strip()
        user_id = update.effective_user.id
        self._cleanup_temp_recipes()
        logger.info("📨 Получено сообщение от %s: %s", user_id, text[:80])

        if text == "📚 Сохраненные рецепты":
            await self.menu_command(update, context)
            return
        if text == "ℹ️ Помощь":
            await self.help_command(update, context)
            return
        if text == "📋 Меню":
            await self.menu_command(update, context)
            return
        if text == "⬅️ Назад":
            await update.message.reply_text(
                "🏠 Главное окно. Нажмите «📋 Меню» чтобы открыть разделы.",
                reply_markup=self.get_main_keyboard(),
            )
            return

        if text == "✅ Да, сохранить":
            await self._confirm_save(update, user_id)
            return

        if text == "❌ Нет":
            self.temp_recipes.pop(user_id, None)
            await update.message.reply_text(
                "👌 Рецепт не сохранен",
                reply_markup=ReplyKeyboardRemove(),
            )
            await update.message.reply_text(
                "Возвращаю в главное меню.",
                reply_markup=self.get_main_keyboard(),
            )
            return

        if text.startswith(("http://", "https://")):
            if self._is_rate_limited(user_id):
                await update.message.reply_text(
                    "⏳ Слишком часто. Подождите 1 секунду и отправьте ссылку снова."
                )
                return
            await self.handle_url(update, context)
            return

        await update.message.reply_text(
            "👋 *Отправьте ссылку на рецепт!*\n\n"
            "Пример: `https://eda.ru/recepty/...`",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=self.get_main_keyboard(),
        )

    async def _confirm_save(self, update: Update, user_id: int) -> None:
        pending = self.temp_recipes.get(user_id)
        if not pending:
            await update.message.reply_text(
                "❌ Нет рецепта для сохранения",
                reply_markup=self.get_main_keyboard(),
            )
            return

        recipe = pending["recipe"]
        try:
            self.storage.save_recipe(user_id, recipe)
            await update.message.reply_text(
                f"✅ Рецепт сохранен!\n\n📄 {recipe.get('title', 'Блюдо')}",
                reply_markup=ReplyKeyboardRemove(),
            )
            await update.message.reply_text(
                "Готово. Можете отправить новую ссылку.",
                reply_markup=self.get_main_keyboard(),
            )
            logger.info("✅ Рецепт сохранен: %s", recipe.get("title"))
        except Exception as error:
            logger.error("❌ Ошибка сохранения: %s", error, exc_info=True)
            await update.message.reply_text(
                "❌ Не удалось сохранить рецепт. Попробуйте еще раз чуть позже.",
                reply_markup=self.get_main_keyboard(),
            )
        finally:
            self.temp_recipes.pop(user_id, None)

    async def handle_url(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        url = update.message.text.strip()
        user_id = update.effective_user.id

        if not validate_url(url):
            await update.message.reply_text("❌ Некорректная ссылка")
            return

        status_message = await update.message.reply_text(
            "🔍 *Читаю страницу...*",
            parse_mode=ParseMode.MARKDOWN,
        )

        try:
            raw_text = ""
            for attempt in range(1, self.MAX_PARSE_RETRIES + 1):
                try:
                    raw_text = await self.parser.parse_recipe(url)
                    break
                except Exception as parse_error:
                    logger.warning(
                        "⚠️ Ошибка парсинга попытка %s/%s: %s",
                        attempt,
                        self.MAX_PARSE_RETRIES,
                        parse_error,
                    )
                    if attempt == self.MAX_PARSE_RETRIES:
                        raise
                    await asyncio.sleep(attempt)

            await status_message.edit_text(
                "🤖 *Анализирую рецепт...*",
                parse_mode=ParseMode.MARKDOWN,
            )
            recipe = await self.normalizer.normalize(raw_text)
            recipe["source_url"] = url

            self.temp_recipes[user_id] = {
                "recipe": recipe,
                "created_at_ts": time.time(),
            }
            logger.info("📦 Рецепт во временном хранилище: %s", recipe.get("title"))

            formatted_text = format_recipe_for_telegram(recipe)
            await status_message.delete()
            await update.message.reply_text(
                formatted_text,
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            await update.message.reply_text(
                "💾 *Сохранить этот рецепт?*",
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=self.get_save_keyboard(),
            )

        except Exception as error:
            logger.error("❌ Ошибка обработки URL: %s", error, exc_info=True)
            self.temp_recipes.pop(user_id, None)
            await status_message.edit_text(f"❌ Ошибка: {str(error)[:200]}")

    # ========== СОХРАНЕННЫЕ РЕЦЕПТЫ ==========

    @classmethod
    def _normalize_category_key(cls, key: str) -> str:
        normalized = (key or "").strip().lower()
        return cls.CATEGORY_KEY_ALIASES.get(normalized, normalized or "other")

    async def show_saved_recipes(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        categories = self.storage.get_user_categories(user_id)

        if not categories:
            await update.message.reply_text(
                "📭 *Пока нет сохраненных рецептов*\n\n"
                "Отправьте ссылку на рецепт и нажмите «✅ Да, сохранить».",
                parse_mode=ParseMode.MARKDOWN,
            )
            return

        keyboard = []
        for cat in categories:
            latin_key = self._normalize_category_key(cat.get("key", "other"))
            display_name = self.MEAL_TYPE_NAMES.get(latin_key, latin_key)
            callback_data = f"cat_{latin_key}"
            logger.info("Создана кнопка категории: %s", callback_data)
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{display_name} ({cat['count']})",
                        callback_data=callback_data,
                    )
                ]
            )

        await update.message.reply_text(
            "📚 *Ваши сохраненные рецепты*\n\nВыберите категорию:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    # ========== CALLBACK ОБРАБОТЧИК (для категорий) ==========

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        data = query.data
        logger.info("🔥🔥🔥 CALLBACK ПОЛУЧЕН: %s от user %s", data, user_id)
        print(f"🔥🔥🔥 CALLBACK ПОЛУЧЕН: {data} от user {user_id}")

        try:
            if data == "menu_help":
                await query.edit_message_text(
                    "📚 *Как пользоваться ботом*\n\n"
                    "1️⃣ Отправьте ссылку на рецепт\n"
                    "2️⃣ Бот обработает рецепт\n"
                    "3️⃣ Нажмите «✅ Да, сохранить» чтобы сохранить\n\n"
                    "Открывайте «📚 Сохраненные рецепты» через Mini App в меню.",
                    parse_mode=ParseMode.MARKDOWN,
                )
                return
            if data.startswith("cat_"):
                category = data[len("cat_") :]
                await self.show_recipes_in_category(query, user_id, category)
            elif data.startswith("view_"):
                payload = data[len("view_") :]
                if "_" in payload:
                    category, recipe_uid = payload.rsplit("_", 1)
                    await self.show_recipe(query, user_id, category, recipe_uid)
            elif data.startswith("delete_"):
                payload = data[len("delete_") :]
                if "_" in payload:
                    category, recipe_uid = payload.rsplit("_", 1)
                    await self.delete_recipe_callback(query, user_id, category, recipe_uid)
            elif data == "back_to_categories":
                await self.show_categories_inline(query, user_id)
        except Exception as error:
            logger.error("❌ Ошибка в callback: %s", error, exc_info=True)
            await query.edit_message_text("❌ Ошибка обработки действия")

    async def show_categories_inline(self, query, user_id: int):
        categories = self.storage.get_user_categories(user_id)

        if not categories:
            await query.edit_message_text("📭 Пока нет сохраненных рецептов")
            return

        keyboard = []
        for cat in categories:
            latin_key = self._normalize_category_key(cat.get("key", "other"))
            display_name = self.MEAL_TYPE_NAMES.get(latin_key, latin_key)
            callback_data = f"cat_{latin_key}"
            logger.info("Создана кнопка категории: %s", callback_data)
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{display_name} ({cat['count']})",
                        callback_data=callback_data,
                    )
                ]
            )

        await query.edit_message_text(
            "📚 *Выберите категорию:*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def show_recipes_in_category(self, query, user_id: int, category: str):
        recipes = self.storage.get_recipes_in_category(user_id, category)
        logger.info("📖 Категория: %s, рецептов: %s", category, len(recipes))
        category_name = self.storage.get_category_name(category)

        if not recipes:
            keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_categories")]]
            await query.edit_message_text(
                f"📭 В категории «{category_name}» пока нет рецептов",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
            return

        text = f"*{category_name}*\n\n"
        keyboard = []

        for i, recipe in enumerate(recipes[:15]):
            title = (recipe.get("title") or "Без названия")[:40]
            calories = recipe.get("calories", 0)
            cook_time = recipe.get("cook_time", 0)

            text += f"{i + 1}. *{title}*\n"
            text += f"   🔥 {calories} ккал | ⏱ {cook_time} мин\n\n"

            button = InlineKeyboardButton(
                f"📖 {title[:30]}",
                callback_data=f"view_{category}_{recipe['recipe_uid']}",
            )
            keyboard.append([button])

        keyboard.append(
            [InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")]
        )

        await query.edit_message_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def show_recipe(self, query, user_id: int, category: str, recipe_uid: str):
        recipe = self.storage.get_recipe_by_uid(user_id, category, recipe_uid)

        if not recipe:
            await query.edit_message_text("❌ Рецепт не найден")
            return

        formatted = format_recipe_for_telegram(recipe)
        if len(formatted) > 4000:
            formatted = f"{formatted[:4000]}\n\n_(текст обрезан)_"

        keyboard = [
            [
                InlineKeyboardButton(
                    "🗑 Удалить", callback_data=f"delete_{category}_{recipe_uid}"
                ),
                InlineKeyboardButton("◀️ Назад", callback_data=f"cat_{category}"),
            ]
        ]

        await query.edit_message_text(
            formatted,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    async def delete_recipe_callback(self, query, user_id: int, category: str, recipe_uid: str):
        if self.storage.delete_recipe_by_uid(user_id, category, recipe_uid):
            keyboard = [[InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")]]
            await query.edit_message_text(
                "✅ Рецепт удален",
                reply_markup=InlineKeyboardMarkup(keyboard),
            )
        else:
            await query.edit_message_text("❌ Не удалось удалить рецепт")

    # ========== ЗАПУСК ==========

    def run(self):
        logger.info("🚀 Запуск приложения...")

        app = (
            Application.builder()
            .token(self.telegram_token)
            .post_init(self.post_init)
            .post_shutdown(self.post_shutdown)
            .build()
        )

        app.add_error_handler(self.global_error_handler)

        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("menu", self.menu_command))
        app.add_handler(CommandHandler("saved", self.saved_command))
        app.add_handler(CommandHandler("help", self.help_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        app.add_handler(CallbackQueryHandler(self.handle_callback))

        logger.info("🤖 Бот готов к работе!")
        app.run_polling(drop_pending_updates=True)

    async def cleanup(self):
        await self.parser.close()
        logger.info("🧹 Ресурсы очищены")
