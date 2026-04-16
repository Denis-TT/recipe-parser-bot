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
            
            # ВАЖНО: кнопки прикреплены к сообщению с рецептом
            await update.message.reply_text(
                formatted_text + "\n\n💾 *Сохранить этот рецепт?*",
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True,
                reply_markup=self.get_save_keyboard(recipe_id)
            )
            
        except Exception as e:
            logger.error(f"❌ Ошибка обработки URL: {e}", exc_info=True)
            await status_message.edit_text(f"❌ Ошибка: {str(e)[:200]}")
