# -*- coding: utf-8 -*-
"""
OKX API коннектор для диверсификации данных
"""

import aiohttp
import asyncio
import hmac
import hashlib
import base64
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional
from config.settings import logger

class EnhancedOKXConnector:
    """Расширенный коннектор для OKX API"""
    
    BASE_URL = "https://www.okx.com"
    
    def __init__(self):
        self.api_key = ''
        self.api_secret = ''
        self.passphrase = ''
        self.session = None
        self.testnet = True
        
        logger.info("✅ EnhancedOKXConnector инициализирован")
    
    async def ensure_session(self):
        """Создание HTTP сессии"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
    
    def _generate_signature(self, timestamp: str, method: str, request_path: str, body: str = '') -> str:
        """Генерация подписи для OKX API"""
        message = timestamp + method + request_path + body
        mac = hmac.new(
            bytes(self.api_secret, encoding='utf8'),
            bytes(message, encoding='utf-8'),
            digestmod=hashlib.sha256
        )
        return base64.b64encode(mac.digest()).decode()
    
    def _get_headers(self, method: str, request_path: str, body: str = '') -> Dict:
        """Генерация заголовков для аутентифицированных запросов"""
        timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')
        
        headers = {
            'OK-ACCESS-KEY': self.api_key,
            'OK-ACCESS-SIGN': self._generate_signature(timestamp, method, request_path, body),
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': self.passphrase,
            'Content-Type': 'application/json'
        }
        
        return headers
    
    async def get_ticker(self, inst_id: str = 'BTC-USDT') -> Optional[Dict]:
        """Получение тикера"""
        await self.ensure_session()
        
        endpoint = f"/api/v5/market/ticker"
        url = f"{self.BASE_URL}{endpoint}"
        params = {'instId': inst_id}
        
        try:
            async with self.session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data['code'] == '0' and data['data']:
                        ticker = data['data'][0]
                        return {
                            'symbol': ticker['instId'],
                            'last': float(ticker['last']),
                            'bid': float(ticker['bidPx']),
                            'ask': float(ticker['askPx']),
                            'high_24h': float(ticker['high24h']),
                            'low_24h': float(ticker['low24h']),
                            'volume_24h': float(ticker['vol24h']),
                            'timestamp': int(ticker['ts'])
                        }
                    else:
                        logger.error(f"❌ OKX API error: {data.get('msg', 'Unknown error')}")
                else:
                    logger.error(f"❌ OKX API HTTP error: {response.status}")
        
        except Exception as e:
            logger.error(f"❌ Ошибка получения тикера OKX: {e}")
        
        return None
    
    async def get_candles(self, inst_id: str = 'BTC-USDT', bar: str = '1H', limit: int = 100) -> List[Dict]:
        """Получение свечей"""
        await self.ensure_session()
        
        endpoint = f"/api/v5/market/candles"
        url = f"{self.BASE_URL}{endpoint}"
        params = {
            'instId': inst_id,
            'bar': bar,
            'limit': str(limit)
        }
        
        try:
            async with self.session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data['code'] == '0' and data['data']:
                        candles = []
                        for candle in data['data']:
                            candles.append({
                                'timestamp': int(candle[0]),
                                'open': float(candle[1]),
                                'high': float(candle[2]),
                                'low': float(candle[3]),
                                'close': float(candle[4]),
                                'volume': float(candle[5]),
                                'volume_currency': float(candle[6]),
                                'volume_currency_quote': float(candle[7]),
                                'confirm': int(candle[8])
                            })
                        
                        logger.debug(f"📊 OKX: Загружено {len(candles)} свечей {inst_id} {bar}")
                        return candles
                    else:
                        logger.error(f"❌ OKX API error: {data.get('msg', 'Unknown error')}")
        
        except Exception as e:
            logger.error(f"❌ Ошибка получения свечей OKX: {e}")
        
        return []
    
    async def get_orderbook(self, inst_id: str = 'BTC-USDT', depth: int = 100) -> Optional[Dict]:
        """Получение стакана ордеров (L2 orderbook)"""
        await self.ensure_session()
        
        endpoint = f"/api/v5/market/books"
        url = f"{self.BASE_URL}{endpoint}"
        params = {
            'instId': inst_id,
            'sz': str(depth)
        }
        
        try:
            async with self.session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data['code'] == '0' and data['data']:
                        ob = data['data'][0]
                        
                        bids = [[float(price), float(qty)] for price, qty, _, _ in ob['bids']]
                        asks = [[float(price), float(qty)] for price, qty, _, _ in ob['asks']]
                        
                        return {
                            'bids': bids,
                            'asks': asks,
                            'timestamp': int(ob['ts'])
                        }
        
        except Exception as e:
            logger.error(f"❌ Ошибка получения стакана OKX: {e}")
        
        return None
    
    async def get_trades(self, inst_id: str = 'BTC-USDT', limit: int = 500) -> List[Dict]:
        """Получение последних сделок"""
        await self.ensure_session()
        
        endpoint = f"/api/v5/market/trades"
        url = f"{self.BASE_URL}{endpoint}"
        params = {
            'instId': inst_id,
            'limit': str(limit)
        }
        
        try:
            async with self.session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    if data['code'] == '0' and data['data']:
                        trades = []
                        for trade in data['data']:
                            trades.append({
                                'id': trade['tradeId'],
                                'price': float(trade['px']),
                                'qty': float(trade['sz']),
                                'side': trade['side'],
                                'timestamp': int(trade['ts'])
                            })
                        
                        return trades
        
        except Exception as e:
            logger.error(f"❌ Ошибка получения сделок OKX: {e}")
        
        return []
    
    async def close(self):
        """Закрытие сессии"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("🌐 OKX сессия закрыта")
