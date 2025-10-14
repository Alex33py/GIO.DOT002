# GIO.BOT

Мониторинг крипторынка с сохранением данных в SQLite и выводом аналитики в реальном времени.
Поддержка источников:
Bybit: OHLCV, индикаторы (RSI, ATR), Volume Profile (VPoC, VAH, VAL)
Binance: цена, объём, open interest, funding rate, long/short ratio, ликвидации через WebSocket
CryptoPanic: новости с тональностью (bullish / bearish / neutral)

Установите Python ≥ 3.10
Создайте виртуальное окружение:
python -m venv venv

Активируйте виртуальное окружение:

Windows:
venv\Scripts\activate

macOS/Linux:
source venv/bin/activate

Установите зависимости:
pip install -r requirements.txt
