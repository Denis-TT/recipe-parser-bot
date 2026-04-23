import asyncio
import logging
import time
from typing import Any, Dict

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
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.backend.repository import RecipeRepository
from app.parser.normalizer import GitHubModelNormalizer
from app.parser.recipe_parser import RecipeParser
from app.shared.config import Settings
from app.shared.constants import MEAL_TYPE_NAMES_RU
from app.shared.utils import format_recipe_for_telegram, validate_url

logger = logging.getLogger(__name__)


class RecipeBot:
    TEMP_TTL_SECONDS = 20 * 60

    def __init__(self, settings: Settings, repository: RecipeRepository) -> None:
        self._settings = settings
        self._repository = repository
        self._parser = RecipeParser()
        self._normalizer = GitHubModelNormalizer(settings.github_token)
        self._pending: Dict[int, Dict[str, Any]] = {}
        self._last_request_at: Dict[int, float] = {}
        logger.info("RecipeBot initialized. webapp_url=%s", settings.webapp_url)

    def _log_ux(self, user_id: int, event: str, **meta: Any) -> None:
        logger.info("UX event user_id=%s event=%s meta=%s", user_id, event, meta)

    def _main_keyboard(self) -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup([[KeyboardButton("📋 Меню")]], resize_keyboard=True)

    def _save_keyboard(self) -> ReplyKeyboardMarkup:
        return ReplyKeyboardMarkup(
            [[KeyboardButton("✅ Да, сохранить"), KeyboardButton("❌ Нет")]],
            one_time_keyboard=True,
            resize_keyboard=True,
        )

    async def start_command(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id if update.effective_user else 0
        self._log_ux(user_id, "start_command")
        await update.message.reply_text(
            "👨‍🍳 Send me a recipe URL and I will parse it.",
            reply_markup=self._main_keyboard(),
        )

    async def menu_command(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        user_id = update.effective_user.id if update.effective_user else 0
        self._log_ux(user_id, "menu_open")
        keyboard = [
            [InlineKeyboardButton("📚 Сохраненные рецепты", web_app=WebAppInfo(self._settings.webapp_url))]
        ]
        await update.message.reply_text(
            "📋 Main menu",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    def _cleanup_pending(self) -> None:
        now = time.time()
        expired = [user_id for user_id, p in self._pending.items() if now - p["created_at"] > self.TEMP_TTL_SECONDS]
        for user_id in expired:
            self._pending.pop(user_id, None)
            self._log_ux(user_id, "pending_recipe_expired")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = (update.message.text or "").strip()
        user_id = update.effective_user.id
        self._cleanup_pending()
        self._log_ux(user_id, "incoming_message", text_preview=text[:100])

        if text == "📋 Меню":
            self._log_ux(user_id, "menu_button_click")
            await self.menu_command(update, context)
            return
        if text == "✅ Да, сохранить":
            self._log_ux(user_id, "save_confirm_click")
            await self._confirm_save(update, user_id)
            return
        if text == "❌ Нет":
            self._pending.pop(user_id, None)
            self._log_ux(user_id, "save_cancel_click")
            await update.message.reply_text("Recipe discarded.", reply_markup=ReplyKeyboardRemove())
            return

        if not validate_url(text):
            self._log_ux(user_id, "invalid_url")
            await update.message.reply_text("Send a valid URL.", reply_markup=self._main_keyboard())
            return

        if self._is_rate_limited(user_id):
            self._log_ux(user_id, "rate_limited")
            await update.message.reply_text("Please wait 1 second before next request.")
            return

        self._log_ux(user_id, "url_processing_started", url=text)
        status = await update.message.reply_text("🔍 Parsing page...")
        try:
            raw_text = await self._parser.parse_recipe(text)
            self._log_ux(user_id, "page_parsed", chars=len(raw_text))
            await status.edit_text("🤖 Normalizing recipe...")
            recipe = await self._normalizer.normalize(raw_text)
            if recipe.get("error"):
                self._log_ux(
                    user_id,
                    "normalization_failed",
                    url=text,
                    error=recipe.get("error", "unknown"),
                )
                self._pending.pop(user_id, None)
                await status.edit_text(
                    "❌ Failed to normalize recipe. Check URL or AI token settings."
                )
                return
            recipe["source_url"] = text
            self._pending[user_id] = {"recipe": recipe, "created_at": time.time()}
            self._log_ux(user_id, "normalization_succeeded", title=recipe.get("title", "untitled"))
            await status.delete()
            await update.message.reply_text(
                format_recipe_for_telegram(recipe),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
            )
            await update.message.reply_text("💾 Save this recipe?", reply_markup=self._save_keyboard())
            self._log_ux(user_id, "save_prompt_shown")
        except Exception as error:
            logger.error("Failed to process URL: %s", error, exc_info=True)
            self._log_ux(user_id, "url_processing_failed", error=str(error)[:200], url=text)
            self._pending.pop(user_id, None)
            await status.edit_text("❌ Failed to process recipe. Try another URL.")

    def _is_rate_limited(self, user_id: int) -> bool:
        now = time.time()
        previous = self._last_request_at.get(user_id)
        self._last_request_at[user_id] = now
        return previous is not None and now - previous < 1

    async def _confirm_save(self, update: Update, user_id: int) -> None:
        payload = self._pending.get(user_id)
        if not payload:
            self._log_ux(user_id, "save_without_pending_recipe")
            await update.message.reply_text("No pending recipe.", reply_markup=self._main_keyboard())
            return
        try:
            saved = self._repository.save_recipe(user_id, payload["recipe"])
            self._log_ux(user_id, "recipe_saved", recipe_id=saved.get("id"), title=saved.get("title"))
            await update.message.reply_text(
                f"✅ Saved: {saved.get('title', 'Untitled')}", reply_markup=ReplyKeyboardRemove()
            )
        except Exception as error:
            logger.error("Failed to save recipe for user_id=%s: %s", user_id, error, exc_info=True)
            self._log_ux(user_id, "recipe_save_failed", error=str(error)[:200])
            await update.message.reply_text(
                "❌ Failed to save recipe. Please try again later.",
                reply_markup=self._main_keyboard(),
            )
        finally:
            self._pending.pop(user_id, None)

    async def callback_handler(self, update: Update, _context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        await query.answer()
        user_id = update.effective_user.id
        self._log_ux(user_id, "callback_received", callback_data=query.data)
        categories = self._repository.get_categories(user_id)
        lines = [
            f"{MEAL_TYPE_NAMES_RU.get(cat.get('key', 'other'), '📦 Другое')}: {cat.get('count', 0)}"
            for cat in categories
        ]
        self._log_ux(user_id, "categories_rendered", count=len(categories))
        await query.edit_message_text("\n".join(lines) if lines else "No saved recipes yet.")

    async def cleanup(self) -> None:
        await self._parser.close()
        logger.info("RecipeBot cleanup completed.")

    def run(self) -> None:
        app = Application.builder().token(self._settings.telegram_bot_token).build()
        app.add_handler(CommandHandler("start", self.start_command))
        app.add_handler(CommandHandler("menu", self.menu_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        app.add_handler(CallbackQueryHandler(self.callback_handler))
        app.run_polling(drop_pending_updates=True)
