# Заменим метод run() на webhook
def run(self):
    logger.info("🚀 Запуск приложения через Webhook...")
    
    app = Application.builder().token(self.telegram_token).post_init(self.post_init).build()
    
    app.add_handler(CommandHandler("start", self.start_command))
    app.add_handler(CommandHandler("menu", self.menu_command))
    app.add_handler(CommandHandler("saved", self.saved_command))
    app.add_handler(CommandHandler("help", self.help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
    app.add_handler(CallbackQueryHandler(self.handle_callback))
    app.add_error_handler(self.error_handler)
    
    # Получаем публичный URL Railway
    railway_url = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
    if not railway_url:
        railway_url = "localhost"
    
    webhook_url = f"https://{railway_url}/webhook"
    port = int(os.environ.get("PORT", 8443))
    
    logger.info(f"🌐 Webhook URL: {webhook_url}")
    
    app.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path="webhook",
        webhook_url=webhook_url,
        drop_pending_updates=True
    )
