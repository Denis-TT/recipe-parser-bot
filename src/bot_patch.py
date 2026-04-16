# Найти и заменить handle_callback
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        user_id = update.effective_user.id
        data = query.data
        
        logger.info(f"🔥 CALLBACK ПОЛУЧЕН: '{data}' от user {user_id}")
        print(f"🔥 CALLBACK ПОЛУЧЕН: '{data}' от user {user_id}")
        
        try:
            if data.startswith("save_"):
                recipe_id = data.replace("save_", "")
                logger.info(f"💾 Сохраняем рецепт {recipe_id}")
                await self.save_recipe_callback(query, user_id, recipe_id)
            elif data == "dont_save":
                logger.info("❌ Отмена сохранения")
                await query.edit_message_text("👌 *Рецепт не сохранен*", parse_mode=ParseMode.MARKDOWN)
                if user_id in self.temp_recipes:
                    del self.temp_recipes[user_id]
            # ... остальные условия ...
        except Exception as e:
            logger.error(f"❌ Ошибка в callback: {e}", exc_info=True)
            await query.edit_message_text(f"❌ Ошибка: {e}")
