#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GIO Crypto Bot - Webhook Mode для Railway.app
"""

import os
import asyncio
import logging
import sys
from telegram.ext import Application
from config.settings import TELEGRAM_BOT_TOKEN
from core.bot import GIOBot

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    stream=sys.stdout,
)

logger = logging.getLogger(__name__)


async def main():
    """Запуск бота в режиме Webhook"""
    try:
        logger.info("=" * 60)
        logger.info("🚀 Starting GIO Crypto Bot (Webhook Mode)")
        logger.info("=" * 60)

        # ✅ ИНИЦИАЛИЗАЦИЯ БОТА
        bot = GIOBot()
        await bot.initialize()
        logger.info("✅ Bot initialized successfully")

        # ✅ СОЗДАНИЕ TELEGRAM APPLICATION
        application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
        logger.info("✅ Telegram Application created")

        # ✅ РЕГИСТРАЦИЯ HANDLERS
        await bot.setup_handlers(application)
        logger.info("✅ Handlers registered successfully")

        # ✅ ПОЛУЧИТЬ RAILWAY URL И PORT
        port = int(os.getenv("PORT", 8080))
        railway_domain = os.getenv("RAILWAY_PUBLIC_DOMAIN")

        if not railway_domain:
            logger.error("❌ RAILWAY_PUBLIC_DOMAIN not set!")
            sys.exit(1)

        webhook_url = f"https://{railway_domain}/telegram"

        logger.info(f"🌐 Webhook URL: {webhook_url}")
        logger.info(f"🔌 Listening on port: {port}")

        # ✅ УСТАНОВИТЬ WEBHOOK
        webhook_info = await application.bot.get_webhook_info()
        if webhook_info.url != webhook_url:
            await application.bot.set_webhook(
                url=webhook_url, drop_pending_updates=True
            )
            logger.info("✅ Webhook set successfully")
        else:
            logger.info("✅ Webhook already set")

        # ✅ ЗАПУСК WEBHOOK СЕРВЕРА
        logger.info("🤖 Starting webhook server...")
        logger.info("🌐 Bot is now running 24/7 on Railway.app")

        await application.run_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="/telegram",
            webhook_url=webhook_url,
            drop_pending_updates=True,
        )

    except Exception as e:
        logger.error(f"❌ Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Shutting down...")
