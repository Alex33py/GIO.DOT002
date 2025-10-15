# -*- coding: utf-8 -*-
"""
WebSocket Manager
Robust WebSocket connection with automatic reconnection and health monitoring
"""

import asyncio
import json
import websockets
from typing import Callable, Optional, Dict, Any
from datetime import datetime
from config.settings import logger


class WebSocketManager:
    """
    Управление WebSocket соединением с:
    - Автоматическим переподключением
    - Health monitoring
    - Exponential backoff
    - Connection pooling
    """

    def __init__(
        self,
        url: str,
        on_message: Callable,
        on_connect: Optional[Callable] = None,
        on_disconnect: Optional[Callable] = None,
        ping_interval: int = 20,
        ping_timeout: int = 15,
        reconnect_delay: int = 5,
        max_reconnect_attempts: int = 10,
        name: str = "WebSocket",
    ):
        self.url = url
        self.on_message = on_message
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.ping_interval = ping_interval
        self.ping_timeout = ping_timeout
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts
        self.name = name

        # State
        self.running = False
        self.ws: Optional[websockets.WebSocketClientProtocol] = None
        self.reconnect_count = 0
        self.last_message_time: Optional[datetime] = None
        self.connection_start_time: Optional[datetime] = None
        self.total_messages = 0

    async def start(self):
        """Запуск WebSocket с автореконнектом"""
        self.running = True
        logger.info(f"🚀 {self.name}: Запуск WebSocket Manager")

        while self.running:
            try:
                await self._connect()
            except websockets.exceptions.ConnectionClosed:
                logger.warning(f"⚠️ {self.name}: Соединение закрыто")
                await self._handle_disconnect()
            except Exception as e:
                logger.error(f"❌ {self.name}: WebSocket error: {e}")
                await self._handle_disconnect()

    async def _connect(self):
        """Подключение к WebSocket"""
        try:
            logger.info(f"🔌 {self.name}: Подключение к {self.url}")

            async with websockets.connect(
                self.url,
                ping_interval=self.ping_interval,
                ping_timeout=self.ping_timeout,
                close_timeout=5,
                max_size=10_000_000,  # 10MB max message size
            ) as ws:
                self.ws = ws
                self.reconnect_count = 0
                self.connection_start_time = datetime.now()
                logger.info(f"✅ {self.name}: WebSocket подключён")

                # Callback on connect
                if self.on_connect:
                    await self.on_connect()

                # Message loop
                async for message in ws:
                    if not self.running:
                        break

                    self.last_message_time = datetime.now()
                    self.total_messages += 1

                    try:
                        data = json.loads(message)
                        await self.on_message(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"❌ {self.name}: JSON decode error: {e}")
                    except Exception as e:
                        logger.error(f"❌ {self.name}: Message processing error: {e}")

        except Exception as e:
            logger.error(f"❌ {self.name}: Connection error: {e}")
            raise

    async def _handle_disconnect(self):
        """Обработка отключения"""
        if self.on_disconnect:
            await self.on_disconnect()

        self.reconnect_count += 1

        if self.reconnect_count >= self.max_reconnect_attempts:
            logger.error(
                f"⛔ {self.name}: Превышен лимит переподключений "
                f"({self.max_reconnect_attempts}), остановка"
            )
            self.running = False
            return

        # Exponential backoff
        delay = min(self.reconnect_delay * (2 ** (self.reconnect_count - 1)), 300)
        logger.info(
            f"🔄 {self.name}: Переподключение #{self.reconnect_count} "
            f"через {delay}s..."
        )
        await asyncio.sleep(delay)

    async def stop(self):
        """Остановка WebSocket"""
        logger.info(f"🛑 {self.name}: Остановка WebSocket")
        self.running = False

        if self.ws and not self.ws.closed:
            await self.ws.close()
            logger.info(f"🔌 {self.name}: WebSocket закрыт")

    async def send(self, message: Dict[Any, Any]):
        """Отправка сообщения"""
        if self.ws and not self.ws.closed:
            try:
                await self.ws.send(json.dumps(message))
            except Exception as e:
                logger.error(f"❌ {self.name}: Send error: {e}")
        else:
            logger.warning(f"⚠️ {self.name}: WebSocket не подключён")

    def get_stats(self) -> Dict:
        """Получить статистику соединения"""
        if self.connection_start_time:
            uptime = (datetime.now() - self.connection_start_time).total_seconds()
        else:
            uptime = 0

        return {
            "name": self.name,
            "connected": self.ws is not None and not self.ws.closed,
            "total_messages": self.total_messages,
            "reconnect_count": self.reconnect_count,
            "uptime_seconds": uptime,
            "last_message": (
                self.last_message_time.isoformat() if self.last_message_time else None
            ),
        }

    def is_healthy(self) -> bool:
        """Проверка здоровья соединения"""
        if not self.ws or self.ws.closed:
            return False

        # Проверка: получали ли сообщения в последние 60 секунд
        if self.last_message_time:
            time_since_last = (datetime.now() - self.last_message_time).total_seconds()
            return time_since_last < 60

        return True
