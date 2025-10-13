# -*- coding: utf-8 -*-
"""
Binance WebSocket Manager
"""

import asyncio
import json
import websockets
from typing import Dict, Callable, Optional
from config.settings import logger


class BinanceWebSocketManager:
    """Менеджер WebSocket соединений для Binance"""
    
    def __init__(self):
        self.ws_url = "wss://stream.binance.com:9443/ws"
        self.connections = {}
        self.callbacks = {}
        
        logger.info("✅ BinanceWebSocketManager инициализирован")
    
    async def subscribe(self, symbol: str, streams: list, callback: Callable):
        """
        Подписка на потоки данных
        
        Args:
            symbol: Торговая пара (btcusdt)
            streams: Список потоков ['trade', 'depth', 'kline_1m']
            callback: Функция обратного вызова
        """
        try:
            symbol_lower = symbol.lower()
            
            # Формируем URL для подписки
            stream_names = []
            for stream in streams:
                if stream == 'orderbook' or stream == 'depth':
                    stream_names.append(f"{symbol_lower}@depth20@100ms")
                elif stream == 'trades' or stream == 'trade':
                    stream_names.append(f"{symbol_lower}@trade")
                elif stream.startswith('kline'):
                    stream_names.append(f"{symbol_lower}@kline_{stream.split('_')[1]}")
            
            combined_stream = "/".join(stream_names)
            ws_url = f"{self.ws_url}/{combined_stream}"
            
            logger.info(f"🔌 Подключение к Binance WebSocket: {symbol}")
            
            async with websockets.connect(ws_url) as websocket:
                self.connections[symbol] = websocket
                
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    # Вызываем callback с данными
                    await callback(data)
        
        except Exception as e:
            logger.error(f"❌ Binance WebSocket ошибка: {e}")
    
    async def close(self):
        """Закрытие всех соединений"""
        for symbol, ws in self.connections.items():
            try:
                await ws.close()
                logger.info(f"🔌 WebSocket закрыт для {symbol}")
            except Exception as e:
                logger.error(f"❌ Ошибка закрытия WebSocket: {e}")


__all__ = ['BinanceWebSocketManager']
