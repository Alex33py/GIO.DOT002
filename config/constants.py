# -*- coding: utf-8 -*-
"""
Константы и перечисления для GIO Crypto Bot
"""

from enum import Enum
from dataclasses import dataclass
from typing import List, Optional, Dict, Any


# ======================= ЦВЕТА ДЛЯ КОНСОЛИ =======================


class Colors:
    """ANSI цветовые коды для консоли"""

    # Основные цвета (исходные)
    SUCCESS = "\033[92m"
    INFO = "\033[94m"
    ALERT = "\033[93m"
    BEARISH = "\033[91m"
    BULLISH = "\033[92m"
    VETO = "\033[95m"
    END = "\033[0m"

    # Расширенные цвета (дополнительные)
    HEADER = "\033[95m"
    OKBLUE = "\033[94m"
    OKCYAN = "\033[96m"
    OKGREEN = "\033[92m"
    WARNING = "\033[93m"
    FAIL = "\033[91m"
    ENDC = "\033[0m"
    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"


# ======================= ENUMERATIONS =======================


class TrendDirectionEnum(Enum):
    """Направление тренда"""

    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UPTREND = "uptrend"  # Алиас для BULLISH
    DOWNTREND = "downtrend"  # Алиас для BEARISH


class SignalStatusEnum(Enum):
    """Статус торгового сигнала"""

    DEAL = "deal"
    RISKY_ENTRY = "risky_entry"
    OBSERVATION = "observation"
    VETOED = "vetoed"


class SignalLevelEnum(Enum):
    """Уровень торгового сигнала"""

    T1 = "t1"
    T2 = "t2"
    T3 = "t3"


class VetoReasonEnum(Enum):
    """Причины системы вето"""

    HIGH_FUNDING_RATE = "high_funding_rate"
    EXTREME_VOLUME_ANOMALY = "extreme_volume_anomaly"
    WIDE_SPREAD = "wide_spread"
    LOW_LIQUIDITY = "low_liquidity"
    LIQUIDATION_CASCADE = "liquidation_cascade"
    MARKET_INSTABILITY = "market_instability"
    NEWS_CONFLICT = "news_conflict"
    ORDERBOOK_MANIPULATION = "orderbook_manipulation"


class AlertTypeEnum(Enum):
    """Типы алертов"""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    SIGNAL = "signal"
    VETO = "veto"


class MarketConditionEnum(Enum):
    """Условия рынка"""

    NORMAL = "normal"
    VOLATILE = "volatile"
    TRENDING = "trending"
    RANGING = "ranging"
    UNSTABLE = "unstable"


class OrderSideEnum(Enum):
    """Сторона ордера"""

    BUY = "Buy"
    SELL = "Sell"


class TimeframeEnum(Enum):
    """Таймфреймы для анализа"""

    M1 = "1"
    M5 = "5"
    M15 = "15"
    M30 = "30"
    H1 = "60"
    H4 = "240"
    D1 = "D"
    W1 = "W"


class VolumeProfileTypeEnum(Enum):
    """Типы volume profile"""

    STANDARD = "standard"
    ENHANCED = "enhanced"
    COMPOSITE = "composite"


class NewsSourceEnum(Enum):
    """Источники новостей"""

    CRYPTOPANIC = "cryptopanic"
    CRYPTOCOMPARE = "cryptocompare"
    COINDESK = "coindesk"
    COINTELEGRAPH = "cointelegraph"


class SignalOriginEnum(Enum):
    """Происхождение сигнала"""

    SCENARIO_MATCH = "scenario_match"
    TECHNICAL_ANALYSIS = "technical_analysis"
    NEWS_DRIVEN = "news_driven"
    VOLUME_PROFILE = "volume_profile"
    MANUAL = "manual"


class ExchangeEnum(Enum):
    """Поддерживаемые биржи"""

    BYBIT = "bybit"
    BINANCE = "binance"
    OKEX = "okex"
    FTX = "ftx"


class MarketStatusEnum(Enum):
    """Статус рынка"""

    ACTIVE = "active"
    MAINTENANCE = "maintenance"
    CLOSED = "closed"
    SUSPENDED = "suspended"


# ======================= API ENDPOINTS =======================

API_ENDPOINTS = {
    "bybit": {
        "base_url": "https://api.bybit.com",
        "websocket": "wss://stream.bybit.com/v5/public/linear",
    },
    "binance": {
        "base_url": "https://api.binance.com",
        "websocket": "wss://stream.binance.com:443",
    },
    "cryptopanic": {"base_url": "https://cryptopanic.com/api/v1", "posts": "/posts/"},
    "cryptocompare": {
        "base_url": "https://min-api.cryptocompare.com/data/v2",
        "news": "/news/",
    },
}


# ======================= ФИЛЬТРЫ СИМВОЛОВ =======================

SYMBOL_FILTERS = {
    "BTC": ["bitcoin", "btc", "₿", "btc-usd", "xbtusd", "Bitcoin", "BTC"],
    "ETH": ["ethereum", "eth", "ether", "eth-usd", "ethusd", "Ethereum", "ETH"],
    "ADA": ["cardano", "ada", "ada-usd", "ADA"],
    "DOT": ["polkadot", "dot", "dot-usd", "DOT"],
    "LINK": ["chainlink", "link", "link-usd", "LINK"],
    "UNI": ["uniswap", "uni", "uni-usd", "UNI"],
    "MATIC": ["polygon", "matic", "matic-usd", "MATIC"],
    "SOL": ["solana", "sol", "sol-usd", "SOL"],
    "AVAX": ["avalanche", "avax", "avax-usd", "AVAX"],
    "ATOM": ["cosmos", "atom", "atom-usd", "ATOM"],
    "ICP": ["internet computer", "icp", "icp-usd", "ICP"],
    "NEAR": ["near protocol", "near", "near-usd", "NEAR"],
    "FTM": ["fantom", "ftm", "ftm-usd", "FTM"],
    "ALGO": ["algorand", "algo", "algo-usd", "ALGO"],
    "XRP": ["ripple", "xrp", "xrp-usd", "XRP"],
    "LTC": ["litecoin", "ltc", "ltc-usd", "LTC"],
    "BCH": ["bitcoin cash", "bch", "bch-usd", "BCH"],
    "XLM": ["stellar", "xlm", "xlm-usd", "XLM"],
    "TRX": ["tron", "trx", "trx-usd", "TRX"],
    "USDT": ["tether", "usdt", "USDT"],
    "BNB": ["binance", "bnb", "BNB"],
}


# ======================= ФОРМАТЫ ВРЕМЕНИ =======================

TIME_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO format with microseconds
    "%Y-%m-%dT%H:%M:%SZ",  # ISO format
    "%Y-%m-%d %H:%M:%S",  # Standard datetime
    "%Y-%m-%dT%H:%M:%S.%f",  # ISO without Z
    "%Y-%m-%dT%H:%M:%S",  # ISO basic
    "%d/%m/%Y %H:%M:%S",  # European format
    "%m/%d/%Y %H:%M:%S",  # US format
]


# ======================= КЛЮЧЕВЫЕ СЛОВА ДЛЯ SENTIMENT =======================

WEIGHTED_KEYWORDS = {
    "critical_impact": {
        "bullish": [
            "massive adoption",
            "institutional investment",
            "regulatory approval",
            "breakthrough",
            "partnership announcement",
            "listing on major exchange",
            "whale accumulation",
            "ETF approval",
            "legal victory",
            "mainstream adoption",
            "moon",
            "pump",
            "surge",
            "breakout",
            "bullish",
            "rally",
            "boom",
        ],
        "bearish": [
            "government ban",
            "major hack",
            "regulatory crackdown",
            "exchange closure",
            "investigation opened",
            "lawsuit filed",
            "massive dump",
            "insider selling",
            "security breach",
            "market manipulation probe",
            "crash",
            "dump",
            "bear",
            "collapse",
            "plummet",
            "liquidation",
            "hack",
            "ban",
            "ponzi",
            "scam",
        ],
        "neutral": [
            "regulatory review",
            "scheduled maintenance",
            "technical analysis",
            "market research",
            "quarterly report",
            "whitepaper release",
        ],
    },
    "high_impact": {
        "bullish": [
            "rally",
            "surge",
            "pump",
            "bull run",
            "new high",
            "breakout",
            "bullish signal",
            "accumulation",
            "volume spike",
            "resistance broken",
            "golden cross",
            "institutional buying",
            "positive news",
            "upgrade",
            "partnership",
            "buy",
            "long",
            "support",
            "whale buying",
            "institutional interest",
        ],
        "bearish": [
            "dump",
            "crash",
            "bear market",
            "selloff",
            "decline",
            "bearish signal",
            "distribution",
            "support broken",
            "death cross",
            "institutional selling",
            "negative news",
            "downgrade",
            "rejection",
            "liquidation",
            "sell",
            "short",
            "whale selling",
            "regulatory concern",
            "technical breakdown",
        ],
        "neutral": [
            "sideways",
            "consolidation",
            "stable",
            "range bound",
            "flat",
            "waiting for catalyst",
            "technical analysis",
            "price discovery",
            "neutral",
        ],
    },
    "medium_impact": {
        "bullish": [
            "up",
            "rise",
            "gain",
            "positive",
            "growth",
            "increase",
            "higher",
            "improvement",
            "bullish",
            "optimistic",
            "confident",
            "strong",
            "good",
            "recovery",
            "upgrade",
            "development",
        ],
        "bearish": [
            "down",
            "fall",
            "loss",
            "negative",
            "decrease",
            "drop",
            "lower",
            "decline",
            "bearish",
            "pessimistic",
            "weak",
            "concerning",
            "bad",
            "downgrade",
            "issue",
            "problem",
        ],
        "neutral": [
            "unchanged",
            "flat",
            "neutral",
            "mixed",
            "uncertain",
            "waiting",
            "monitoring",
            "watching",
            "observing",
            "tracking",
        ],
    },
    "standard_impact": {
        "bullish": [
            "good",
            "success",
            "win",
            "advantage",
            "benefit",
            "positive development",
            "encouraging",
            "promising",
            "hopeful",
            "potential",
            "rising",
            "up",
            "green",
            "gain",
            "profit",
            "improvement",
            "hope",
        ],
        "bearish": [
            "bad",
            "fail",
            "problem",
            "issue",
            "concern",
            "risk",
            "challenging",
            "difficult",
            "problematic",
            "worrying",
            "falling",
            "down",
            "red",
            "loss",
            "drop",
            "fear",
            "uncertainty",
            "doubt",
        ],
        "neutral": [
            "news",
            "update",
            "announcement",
            "statement",
            "report",
            "information",
            "data",
            "analysis",
            "comment",
            "opinion",
            "price",
            "market",
            "trading",
            "volume",
        ],
    },
}


# ======================= МНОЖИТЕЛИ ВЛИЯНИЯ =======================

NEWS_IMPACT_MULTIPLIERS = {
    "critical_impact": 3.0,
    "high_impact": 2.0,
    "medium_impact": 1.5,
    "standard_impact": 1.0,
}


# ======================= НАДЕЖНОСТЬ ИСТОЧНИКОВ =======================

NEWS_SOURCE_RELIABILITY = {
    # Tier 1 - Премиум источники
    "CoinDesk": 0.95,
    "Cointelegraph": 0.90,
    "CoinMarketCap": 0.90,
    "CryptoCompare": 0.90,
    "The Block": 0.95,
    "Decrypt": 0.90,
    "Bloomberg": 0.95,
    "Reuters": 0.95,
    # Tier 2 - Надежные источники
    "CryptoNews": 0.85,
    "Bitcoin.com": 0.85,
    "CryptoBriefing": 0.85,
    "AMBCrypto": 0.80,
    "BeInCrypto": 0.80,
    "Bitcoinist": 0.85,
    "NewsBTC": 0.80,
    # Tier 3 - Средние источники
    "CryptoPanic": 0.80,
    "CryptoSlate": 0.75,
    "CoinJournal": 0.75,
    "Medium": 0.70,
    # Tier 4 - Социальные и неизвестные
    "social_media": 0.60,
    "reddit": 0.55,
    "twitter": 0.60,
    "telegram": 0.50,
    "unknown": 0.70,
    "blog": 0.65,
}


# ======================= РИСК-МЕНЕДЖМЕНТ =======================

RISK_MANAGEMENT = {
    "max_position_size": 0.02,  # 2% от депозита
    "max_daily_loss": 0.05,  # 5% от депозита в день
    "max_open_positions": 3,
    "min_rr_ratio": 1.5,  # Минимальный Risk/Reward
    "stop_loss_buffer": 0.1,  # 10% буфер для SL
    "take_profit_buffer": 0.05,  # 5% буфер для TP
}


# ======================= ЛИМИТЫ API =======================

API_LIMITS = {
    "bybit": {
        "requests_per_second": 10,
        "requests_per_minute": 120,
        "weight_limit": 1200,
    },
    "binance": {
        "requests_per_second": 20,
        "requests_per_minute": 1200,
        "weight_limit": 6000,
    },
    "cryptocompare": {
        "requests_per_second": 1,
        "requests_per_hour": 100000,
        "requests_per_month": 1000000,
    },
    "cryptopanic": {"requests_per_hour": 500, "requests_per_day": 20000},
}


# ======================= ТАЙМАУТЫ И ИНТЕРВАЛЫ =======================

TIMEOUTS = {
    "api_request": 10.0,  # секунд
    "websocket_ping": 20.0,
    "database_query": 5.0,
    "analysis_timeout": 30.0,
}

INTERVALS = {
    "market_data_update": 30,  # секунд
    "news_update": 300,  # 5 минут
    "scenario_analysis": 180,  # 3 минуты
    "volume_profile_update": 60,  # 1 минута
    "status_display": 120,  # 2 минуты
    "health_check": 300,  # 5 минут
    "cleanup": 3600,  # 1 час
}


# ======================= КОНФИГУРАЦИЯ ПО УМОЛЧАНИЮ =======================

DEFAULT_CONFIG = {
    "trading": {
        "auto_trading": False,
        "paper_trading": True,
        "min_confidence": 0.7,
        "max_spread_percent": 0.5,
    },
    "analysis": {
        "min_volume": 100000,
        "min_news_confidence": 0.3,
        "sentiment_threshold": 0.2,
        "rsi_overbought": 70,
        "rsi_oversold": 30,
    },
    "database": {"cleanup_days": 30, "vacuum_interval": 7, "backup_enabled": True},
    "logging": {"level": "INFO", "max_file_size_mb": 10, "backup_count": 5},
}


# ======================= DATA CLASSES =======================


@dataclass
class EnhancedTradingSignal:
    """Расширенный торговый сигнал"""

    symbol: str
    side: str
    scenario_id: str
    status: SignalStatusEnum
    price_entry: float
    sl: float
    tp1: float
    tp2: float = 0.0
    tp3: float = 0.0
    rr1: float = 0.0
    rr2: float = 0.0
    rr3: float = 0.0
    timestamp: int = 0
    indicators: Dict[str, Any] = None
    reason: str = ""
    veto_reasons: List[VetoReasonEnum] = None
    level: SignalLevelEnum = SignalLevelEnum.T3
    confidence_score: float = 0.0
    market_conditions: Dict[str, Any] = None
    news_impact: Dict[str, Any] = None
    volume_profile_context: Dict[str, Any] = None

    def __post_init__(self):
        if self.indicators is None:
            self.indicators = {}
        if self.veto_reasons is None:
            self.veto_reasons = []
        if self.market_conditions is None:
            self.market_conditions = {}
        if self.news_impact is None:
            self.news_impact = {}
        if self.volume_profile_context is None:
            self.volume_profile_context = {}


# ======================= ЭКСПОРТ ВСЕХ КОНСТАНТ =======================

__all__ = [
    # Базовые классы
    "Colors",
    "EnhancedTradingSignal",
    # Enums
    "TrendDirectionEnum",
    "SignalStatusEnum",
    "SignalLevelEnum",
    "VetoReasonEnum",
    "AlertTypeEnum",
    "MarketConditionEnum",
    "OrderSideEnum",
    "TimeframeEnum",
    "VolumeProfileTypeEnum",
    "NewsSourceEnum",
    "SignalOriginEnum",
    "ExchangeEnum",
    "MarketStatusEnum",
    # API и настройки
    "API_ENDPOINTS",
    "SYMBOL_FILTERS",
    "TIME_FORMATS",
    # Анализ новостей
    "WEIGHTED_KEYWORDS",
    "NEWS_IMPACT_MULTIPLIERS",
    "NEWS_SOURCE_RELIABILITY",
    # Конфигурация
    "RISK_MANAGEMENT",
    "API_LIMITS",
    "TIMEOUTS",
    "INTERVALS",
    "DEFAULT_CONFIG",
]


# ======================= ТЕСТИРОВАНИЕ =======================

if __name__ == "__main__":
    """Тестирование констант при прямом запуске"""
    print("🔍 ТЕСТИРОВАНИЕ КОНСТАНТ GIO CRYPTO BOT")
    print("=" * 50)

    # Тестируем Enums
    print("\n📋 ПЕРЕЧИСЛЕНИЯ:")
    print(f"  TrendDirectionEnum: {[e.value for e in TrendDirectionEnum]}")
    print(f"  SignalStatusEnum: {[e.value for e in SignalStatusEnum]}")
    print(f"  VetoReasonEnum: {len(VetoReasonEnum)} причин")
    print(f"  ExchangeEnum: {[e.value for e in ExchangeEnum]}")

    # Тестируем константы новостей
    print("\n📰 КОНСТАНТЫ НОВОСТЕЙ:")
    print(f"  Уровней влияния: {len(WEIGHTED_KEYWORDS)}")
    print(f"  Источников новостей: {len(NEWS_SOURCE_RELIABILITY)}")
    print(f"  Символов для фильтрации: {len(SYMBOL_FILTERS)}")

    # Тестируем Colors
    print(f"\n🎨 ЦВЕТА:")
    print(f"  {Colors.SUCCESS}SUCCESS{Colors.END}")
    print(f"  {Colors.WARNING}WARNING{Colors.END}")
    print(f"  {Colors.FAIL}FAIL{Colors.END}")
    print(f"  {Colors.OKGREEN}OKGREEN{Colors.ENDC}")

    # Тестируем создание EnhancedTradingSignal
    print("\n🎯 ТЕСТИРОВАНИЕ ТОРГОВОГО СИГНАЛА:")
    try:
        test_signal = EnhancedTradingSignal(
            symbol="BTCUSDT",
            side="BUY",
            scenario_id="test_001",
            status=SignalStatusEnum.DEAL,
            price_entry=50000.0,
            sl=48000.0,
            tp1=52000.0,
        )
        print(f"  ✅ Создан тестовый сигнал: {test_signal.symbol} {test_signal.side}")
        print(f"  ✅ Статус: {test_signal.status.value}")
    except Exception as e:
        print(f"  ❌ Ошибка создания сигнала: {e}")

    # Тестируем API endpoints
    print("\n🌐 API ENDPOINTS:")
    for exchange, config in API_ENDPOINTS.items():
        print(f"  {exchange}: {config['base_url']}")

    print("\n🎉 ВСЕ КОНСТАНТЫ ЗАГРУЖЕНЫ УСПЕШНО!")
