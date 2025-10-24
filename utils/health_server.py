# -*- coding: utf-8 -*-
"""
Health Check HTTP Server для Railway
Работает параллельно с Telegram ботом
"""

import asyncio
import logging
import os
from aiohttp import web

logger = logging.getLogger("gio_bot.health_server")


class HealthCheckServer:
    """HTTP-сервер для health check endpoint"""

    def __init__(self, port: int = 8080):
        self.port = port
        self.app = web.Application()
        self.runner = None
        self.site = None
        self._setup_routes()

    def _setup_routes(self):
        """Настройка маршрутов"""
        self.app.router.add_get("/", self.root_handler)
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/status", self.status_handler)

    async def root_handler(self, request):
        """Обработчик корневого маршрута"""
        return web.Response(
            text="🤖 GIO Crypto Bot is running",
            status=200,
            content_type="text/plain"
        )

    async def health_handler(self, request):
        """Health check endpoint для Railway"""
        return web.json_response(
            {
                "status": "healthy",
                "service": "gio-crypto-bot",
                "timestamp": asyncio.get_event_loop().time()
            },
            status=200
        )

    async def status_handler(self, request):
        """Расширенный статус с метриками"""
        return web.json_response(
            {
                "status": "running",
                "service": "gio-crypto-bot",
                "version": "1.0.0",
                "environment": os.getenv("ENVIRONMENT", "DEVELOPMENT"),
                "uptime": asyncio.get_event_loop().time()
            },
            status=200
        )

    async def start(self):
        """Запуск HTTP-сервера"""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, "0.0.0.0", self.port)
            await self.site.start()
            logger.info(f"✅ Health Check Server запущен на порту {self.port}")
        except Exception as e:
            logger.error(f"❌ Ошибка запуска Health Check Server: {e}")
            raise

    async def stop(self):
        """Остановка HTTP-сервера"""
        if self.runner:
            await self.runner.cleanup()
            logger.info("🛑 Health Check Server остановлен")


# Глобальный экземпляр сервера
_health_server = None


async def start_health_server(port: int = 8080):
    """Запуск Health Check сервера"""
    global _health_server
    _health_server = HealthCheckServer(port)
    await _health_server.start()
    return _health_server


async def stop_health_server():
    """Остановка Health Check сервера"""
    global _health_server
    if _health_server:
        await _health_server.stop()
