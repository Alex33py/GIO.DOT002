# -*- coding: utf-8 -*-
"""
Патч для UnifiedNewsConnector - добавление метода get_news_by_symbol
"""

# ДОБАВЬТЕ ЭТОТ МЕТОД В КЛАСС UnifiedNewsConnector В ФАЙЛЕ news_connector.py
# (перед закрывающей скобкой класса и перед __all__)

    async def get_news_by_symbol(self, symbol: str, limit: int = 10) -> List[Dict]:
        """
        Получить новости для конкретного символа с фильтрацией
        
        Args:
            symbol: Символ (BTC, ETH, BNB, SOL, etc)
            limit: Количество новостей (по умолчанию 10)
        
        Returns:
            Список отфильтрованных новостей
        """
        try:
            # Получаем все новости (больше чем limit для лучшей фильтрации)
            all_news = await self.get_aggregated_news(limit=50)
            
            if not all_news:
                logger.warning(f"⚠️ Нет новостей для фильтрации по {symbol}")
                return []
            
            # Словарь ключевых слов для каждого символа
            symbol_keywords = {
                'BTC': ['bitcoin', 'btc', 'btcusd', 'btcusdt', 'xbt'],
                'ETH': ['ethereum', 'eth', 'ether', 'vitalik', 'ethusdt'],
                'BNB': ['binance', 'bnb', 'cz', 'bnbusdt'],
                'SOL': ['solana', 'sol', 'solusdt', 'anatoly'],
                'XRP': ['ripple', 'xrp', 'xrpusdt'],
                'ADA': ['cardano', 'ada', 'adausdt', 'charles'],
                'DOGE': ['dogecoin', 'doge', 'dogeusdt', 'shiba'],
                'MATIC': ['polygon', 'matic', 'maticusdt'],
                'DOT': ['polkadot', 'dot', 'dotusdt'],
                'AVAX': ['avalanche', 'avax', 'avaxusdt'],
                'LINK': ['chainlink', 'link', 'linkusdt'],
                'UNI': ['uniswap', 'uni', 'uniusdt'],
                'ATOM': ['cosmos', 'atom', 'atomusdt'],
                'LTC': ['litecoin', 'ltc', 'ltcusdt'],
                'BCH': ['bitcoin cash', 'bch', 'bchusdt'],
                'ALT': ['altcoin', 'alt', 'crypto', 'cryptocurrency', 'defi', 'nft', 'web3']
            }
            
            # Убираем суффикс USDT если есть
            clean_symbol = symbol.replace('USDT', '').replace('USD', '').upper()
            
            # Получаем ключевые слова для символа
            keywords = symbol_keywords.get(clean_symbol, [clean_symbol.lower()])
            
            # Фильтруем новости
            filtered_news = []
            for news in all_news:
                title = news.get('title', '').lower()
                body = news.get('body', '').lower()
                tags = ' '.join(news.get('tags', [])).lower() if news.get('tags') else ''
                
                # Объединяем все текстовые поля
                text = f"{title} {body} {tags}"
                
                # Проверяем наличие хотя бы одного ключевого слова
                if any(keyword in text for keyword in keywords):
                    # Добавляем информацию о matched символе
                    news['matched_symbol'] = clean_symbol
                    news['matched_keywords'] = [kw for kw in keywords if kw in text]
                    filtered_news.append(news)
                
                # Прекращаем если набрали достаточно
                if len(filtered_news) >= limit:
                    break
            
            logger.info(
                f"📰 Отфильтровано {len(filtered_news)}/{len(all_news)} "
                f"новостей для {clean_symbol}"
            )
            
            return filtered_news[:limit]
            
        except Exception as e:
            logger.error(f"❌ Ошибка получения новостей для {symbol}: {e}", exc_info=True)
            return []
