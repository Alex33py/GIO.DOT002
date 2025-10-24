# -*- coding: utf-8 -*-
"""
Health Check Server для Railway
Простой HTTP-сервер для мониторинга состояния бота
"""

import asyncio
import logging
from aiohttp import web
import time

logger = logging.getLogger("gio_bot.health_server")

# Глобальная ссылка на сервер
_health_server_runner = None


async def health_check_handler(request):
    """Обработчик health check запроса"""
    return web.json_response(
        {"status": "healthy", "service": "gio-crypto-bot", "timestamp": time.time()}
    )


async def start_health_server(port: int = 8080):
    """
    Запустить Health Check Server

    Args:
        port: Порт для HTTP-сервера (по умолчанию 8080)

    Returns:
        web.AppRunner instance
    """
    global _health_server_runner

    try:
        app = web.Application()
        app.router.add_get("/health", health_check_handler)

        runner = web.AppRunner(app)
        await runner.setup()

        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()

        _health_server_runner = runner

        logger.info(f"✅ Health Check Server запущен на порту {port}")
        logger.info(f"   • Endpoint: http://0.0.0.0:{port}/health")

        return runner

    except Exception as e:
        logger.error(f"❌ Не удалось запустить Health Check Server: {e}", exc_info=True)
        raise


async def stop_health_server():
    """Остановить Health Check Server"""
    global _health_server_runner

    if _health_server_runner:
        try:
            await _health_server_runner.cleanup()
            logger.info("✅ Health Check Server остановлен")
        except Exception as e:
            logger.error(f"❌ Ошибка при остановке Health Check Server: {e}")
        finally:
            _health_server_runner = None
