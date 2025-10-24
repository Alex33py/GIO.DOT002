#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Webhook Server для Telegram Bot на Railway
"""

import os
import asyncio
import logging
from aiohttp import web

logger = logging.getLogger(__name__)


class WebhookServer:
    """Webhook server для Railway"""

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.app = None
        self.runner = None

    async def webhook_handler(self, request):
        """Обработка webhook от Telegram"""
        try:
            data = await request.json()
            logger.info(f"📥 Webhook update: {data.get('update_id')}")

            # Передаём update в Telegram handler
            if hasattr(self.bot, 'telegram_handler'):
                await self.bot.telegram_handler.process_webhook_update(data)

            return web.Response(text="OK")
        except Exception as e:
            logger.error(f"❌ Webhook error: {e}")
            return web.Response(text="ERROR", status=500)

    async def health_check(self, request):
        """Health check для Railway"""
        return web.json_response({
            "status": "healthy",
            "bot": "GIO Bot v3.0",
            "mode": "webhook"
        })

    async def start(self):
        """Запуск webhook сервера"""
        token = os.getenv('TELEGRAM_BOT_TOKEN')
        webhook_host = os.getenv('WEBHOOK_HOST')
        port = int(os.getenv('PORT', 8080))

        if not token or not webhook_host:
            logger.error("❌ TELEGRAM_BOT_TOKEN or WEBHOOK_HOST not set!")
            return

        # Создаём aiohttp app
        self.app = web.Application()
        self.app.router.add_post(f'/webhook/{token}', self.webhook_handler)
        self.app.router.add_get('/health', self.health_check)
        self.app.router.add_get('/', self.health_check)

        # Запускаем сервер
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '0.0.0.0', port)
        await site.start()

        # Устанавливаем webhook
        webhook_url = f"{webhook_host}/webhook/{token}"
        if hasattr(self.bot, 'telegram_handler'):
            await self.bot.telegram_handler.set_webhook(webhook_url)

        logger.info(f"✅ Webhook server started on port {port}")
        logger.info(f"✅ Webhook URL: {webhook_url}")

        # Держим сервер активным
        while True:
            await asyncio.sleep(3600)

    async def stop(self):
        """Остановка сервера"""
        if hasattr(self.bot, 'telegram_handler'):
            await self.bot.telegram_handler.delete_webhook()
        if self.runner:
            await self.runner.cleanup()


async def run_webhook_server(bot):
    """Главная функция запуска webhook"""
    server = WebhookServer(bot)
    await server.start()
