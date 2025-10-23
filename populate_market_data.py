import sqlite3
import asyncio
import requests
from datetime import datetime


async def populate_market_data():
    conn = sqlite3.connect("data/gio_crypto_bot.db")
    cursor = conn.cursor()
    symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
    base_url = "https://api.binance.com/api/v3/klines"

    for symbol in symbols:
        print(f"📊 Загрузка данных для {symbol}...")
        try:
            params = {"symbol": symbol, "interval": "5m", "limit": 2000}
            response = requests.get(base_url, params=params, timeout=10)
            if response.status_code != 200:
                print(f"❌ Ошибка API для {symbol}: {response.status_code}")
                continue
            klines = response.json()
            if not klines:
                print(f"⚠️ Нет данных для {symbol}")
                continue
            for kline in klines:
                timestamp_ms = int(kline[0])
                timestamp = datetime.fromtimestamp(timestamp_ms / 1000).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                open_price = float(kline[1])
                high_price = float(kline[2])
                low_price = float(kline[3])
                close_price = float(kline[4])
                volume = float(kline[5])
                cursor.execute(
                    """INSERT OR IGNORE INTO market_data (symbol, timestamp, price, volume, high, low, open, close) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        symbol,
                        timestamp,
                        close_price,
                        volume,
                        high_price,
                        low_price,
                        open_price,
                        close_price,
                    ),
                )
            conn.commit()
            print(f"✅ {symbol}: загружено {len(klines)} свечей")
        except Exception as e:
            print(f"❌ Ошибка загрузки {symbol}: {e}")
    conn.close()
    print("\n🎉 Заполнение market_data завершено!")


if __name__ == "__main__":
    asyncio.run(populate_market_data())
