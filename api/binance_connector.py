# -*- coding: utf-8 -*-
"""
Binance API коннектор для диверсификации данных
"""

import aiohttp
import asyncio
import hmac
import hashlib
import time
from typing import Dict, List, Optional
from config.settings import logger

class EnhancedBinanceConnector:
    """Расширенный коннектор для Binance API"""
    
    BASE_URL = "https://api.binance.com"
    FAPI_URL = "https://fapi.binance.com"  # Futures
    
    def __init__(self):
        self.api_key = ''
        self.api_secret = ''
        self.session = None
        self.testnet = True
        
        if self.testnet:
            self.BASE_URL = "https://testnet.binance.vision"
            self.FAPI_URL = "https://testnet.binancefuture.com"
        
        logger.info("✅ EnhancedBinanceConnector инициализирован")
    
    async def ensure_session(self):
        """Создание HTTP сессии"""
        if self.session is None or self.session.closed:
            headers = {'X-MBX-APIKEY': self.api_key} if self.api_key else {}
            self.session = aiohttp.ClientSession(headers=headers)
    
    def _generate_signature(self, params: Dict) -> str:
        """Генерация HMAC SHA256 подписи"""
        query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    async def get_klines(self, symbol: str, interval: str = '1h', limit: int = 500) -> List[Dict]:
        """Получение исторических свечей"""
        await self.ensure_session()
        
        endpoint = f"{self.BASE_URL}/api/v3/klines"
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        
        try:
            async with self.session.get(endpoint, params=params, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    candles = []
                    for candle in data:
                        candles.append({
                            'timestamp': candle[0],
                            'open': float(candle[1]),
                            'high': float(candle[2]),
                            'low': float(candle[3]),
                            'close': float(candle[4]),
                            'volume': float(candle[5]),
                            'close_time': candle[6],
                            'quote_volume': float(candle[7]),
                            'trades': int(candle[8])
                        })
                    
                    logger.debug(f"📊 Binance: Загружено {len(candles)} свечей {symbol} {interval}")
                    return candles
                else:
                    logger.error(f"❌ Binance API ошибка: {response.status}")
                    return []
        
        except Exception as e:
            logger.error(f"❌ Ошибка получения свечей Binance: {e}")
            return []
    
    async def get_ticker_24h(self, symbol: str) -> Optional[Dict]:
        """Получение 24h тикера"""
        await self.ensure_session()
        
        endpoint = f"{self.BASE_URL}/api/v3/ticker/24hr"
        params = {'symbol': symbol}
        
        try:
            async with self.session.get(endpoint, params=params, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        'symbol': data['symbol'],
                        'price': float(data['lastPrice']),
                        'volume': float(data['volume']),
                        'quote_volume': float(data['quoteVolume']),
                        'price_change_percent': float(data['priceChangePercent']),
                        'high': float(data['highPrice']),
                        'low': float(data['lowPrice'])
                    }
        except Exception as e:
            logger.error(f"❌ Ошибка получения тикера Binance: {e}")
            return None
    
    async def get_orderbook(self, symbol: str, limit: int = 100) -> Optional[Dict]:
        """Получение стакана ордеров"""
        await self.ensure_session()
        
        endpoint = f"{self.BASE_URL}/api/v3/depth"
        params = {'symbol': symbol, 'limit': limit}
        
        try:
            async with self.session.get(endpoint, params=params, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    bids = [[float(price), float(qty)] for price, qty in data['bids']]
                    asks = [[float(price), float(qty)] for price, qty in data['asks']]
                    
                    return {
                        'bids': bids,
                        'asks': asks,
                        'timestamp': data.get('lastUpdateId', int(time.time() * 1000))
                    }
        except Exception as e:
            logger.error(f"❌ Ошибка получения стакана Binance: {e}")
            return None
    
    async def get_agg_trades(self, symbol: str, limit: int = 1000) -> List[Dict]:
        """Получение агрегированных сделок"""
        await self.ensure_session()
        
        endpoint = f"{self.BASE_URL}/api/v3/aggTrades"
        params = {'symbol': symbol, 'limit': limit}
        
        try:
            async with self.session.get(endpoint, params=params, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    trades = []
                    for trade in data:
                        trades.append({
                            'id': trade['a'],
                            'price': float(trade['p']),
                            'qty': float(trade['q']),
                            'timestamp': trade['T'],
                            'is_buyer_maker': trade['m']
                        })
                    
                    return trades
        except Exception as e:
            logger.error(f"❌ Ошибка получения сделок Binance: {e}")
            return []
    
    async def get_funding_rate(self, symbol: str) -> Optional[Dict]:
        """Получение ставки фондирования (futures)"""
        await self.ensure_session()
        
        endpoint = f"{self.FAPI_URL}/fapi/v1/fundingRate"
        params = {'symbol': symbol, 'limit': 1}
        
        try:
            async with self.session.get(endpoint, params=params, timeout=30) as response:
                if response.status == 200:
                    data = await response.json()
                    if data:
                        return {
                            'symbol': data[0]['symbol'],
                            'funding_rate': float(data[0]['fundingRate']),
                            'funding_time': data[0]['fundingTime']
                        }
        except Exception as e:
            logger.error(f"❌ Ошибка получения funding rate Binance: {e}")
            return None
    
    async def close(self):
        """Закрытие сессии"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("🌐 Binance сессия закрыта")
