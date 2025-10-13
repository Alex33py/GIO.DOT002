# -*- coding: utf-8 -*-
"""
Coinbase Advanced Trade API коннектор
"""

import aiohttp
import asyncio
import hmac
import hashlib
import time
import json
from typing import Dict, List, Optional
from config.settings import logger

class EnhancedCoinbaseConnector:
    """Расширенный коннектор для Coinbase Advanced Trade API"""
    
    BASE_URL = "https://api.coinbase.com"
    
    def __init__(self):
        self.api_key = ''
        self.api_secret = ''
        self.session = None
        
        logger.info("✅ EnhancedCoinbaseConnector инициализирован")
    
    async def ensure_session(self):
        """Создание HTTP сессии"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
        """Генерация CB-ACCESS-SIGN подписи"""
        message = timestamp + method + request_path + body
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _get_headers(self, method: str, request_path: str, body: str = '') -> Dict:
        """Генерация заголовков для аутентифицированных запросов"""
        timestamp = str(int(time.time()))
        
        headers = {
            'CB-ACCESS-KEY': self.api_key,
            'CB-ACCESS-SIGN': self._generate_signature(timestamp, method, request_path, body),
            'CB-ACCESS-TIMESTAMP': timestamp,
            'Content-Type': 'application/json'
        }
        
        return headers
    
    async def get_ticker(self, product_id: str = 'BTC-USD') -> Optional[Dict]:
        """Получение тикера"""
        await self.ensure_session()
        
        endpoint = f"/api/v3/brokerage/products/{product_id}/ticker"
        url = f"{self.BASE_URL}{endpoint}"
        
        try:
            async with self.session.get(url, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    return {
                        'product_id': data.get('product_id'),
                        'price': float(data.get('price', 0)),
                        'volume_24h': float(data.get('volume_24h', 0)),
                        'price_percent_change_24h': float(data.get('price_percent_change_24h', 0)),
                        'best_bid': float(data.get('best_bid', 0)),
                        'best_ask': float(data.get('best_ask', 0))
                    }
                else:
                    logger.error(f"❌ Coinbase API HTTP error: {response.status}")
        
        except Exception as e:
            logger.error(f"❌ Ошибка получения тикера Coinbase: {e}")
        
        return None
    
    async def get_candles(self, product_id: str = 'BTC-USD', granularity: str = 'ONE_HOUR', limit: int = 300) -> List[Dict]:
        """Получение свечей"""
        await self.ensure_session()
        
        endpoint = f"/api/v3/brokerage/products/{product_id}/candles"
        url = f"{self.BASE_URL}{endpoint}"
        
        granularity_seconds = {
            'ONE_MINUTE': 60,
            'FIVE_MINUTE': 300,
            'FIFTEEN_MINUTE': 900,
            'THIRTY_MINUTE': 1800,
            'ONE_HOUR': 3600,
            'TWO_HOUR': 7200,
            'SIX_HOUR': 21600,
            'ONE_DAY': 86400
        }
        
        seconds = granularity_seconds.get(granularity, 3600)
        end_time = int(time.time())
        start_time = end_time - (seconds * limit)
        
        params = {
            'start': str(start_time),
            'end': str(end_time),
            'granularity': granularity
        }
        
        try:
            async with self.session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    candles = []
                    for candle in data.get('candles', []):
                        candles.append({
                            'timestamp': int(candle['start']),
                            'open': float(candle['open']),
                            'high': float(candle['high']),
                            'low': float(candle['low']),
                            'close': float(candle['close']),
                            'volume': float(candle['volume'])
                        })
                    
                    logger.debug(f"📊 Coinbase: Загружено {len(candles)} свечей {product_id} {granularity}")
                    return candles
                else:
                    logger.error(f"❌ Coinbase API error: {response.status}")
        
        except Exception as e:
            logger.error(f"❌ Ошибка получения свечей Coinbase: {e}")
        
        return []
    
    async def get_orderbook(self, product_id: str = 'BTC-USD', level: int = 2) -> Optional[Dict]:
        """Получение стакана ордеров"""
        await self.ensure_session()
        
        endpoint = f"/api/v3/brokerage/product_book"
        url = f"{self.BASE_URL}{endpoint}"
        params = {
            'product_id': product_id,
            'level': str(level)
        }
        
        try:
            async with self.session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    pricebook = data.get('pricebook', {})
                    
                    bids = [[float(bid['price']), float(bid['size'])] for bid in pricebook.get('bids', [])]
                    asks = [[float(ask['price']), float(ask['size'])] for ask in pricebook.get('asks', [])]
                    
                    return {
                        'product_id': pricebook.get('product_id'),
                        'bids': bids,
                        'asks': asks,
                        'time': pricebook.get('time')
                    }
        
        except Exception as e:
            logger.error(f"❌ Ошибка получения стакана Coinbase: {e}")
        
        return None
    
    async def close(self):
        """Закрытие сессии"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("🌐 Coinbase сессия закрыта")
