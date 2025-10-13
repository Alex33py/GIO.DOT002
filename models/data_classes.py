from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
import time

def current_epoch_ms() -> int:
    """Получить текущий timestamp в миллисекундах"""
    return int(time.time() * 1000)


class TrendDirectionEnum(Enum):
    """Направления тренда"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class SignalStatusEnum(Enum):
    """Статусы торговых сигналов"""
    DEAL = "deal"
    RISKY_ENTRY = "risky_entry"
    OBSERVATION = "observation"
    VETOED = "vetoed"
    EXPIRED = "expired"


class SignalLevelEnum(Enum):
    """Уровни торговых сигналов"""
    T1 = "T1"  # Высший уровень
    T2 = "T2"  # Средний уровень
    T3 = "T3"  # Низший уровень


class VetoReasonEnum(Enum):
    """Причины вето для торговых сигналов"""
    HIGH_FUNDING_RATE = "high_funding_rate"
    EXTREME_VOLUME_ANOMALY = "extreme_volume_anomaly"
    WIDE_SPREAD = "wide_spread"
    LIQUIDATION_CASCADE = "liquidation_cascade"
    MARKET_INSTABILITY = "market_instability"
    ORDERBOOK_MANIPULATION = "orderbook_manipulation"
    LOW_LIQUIDITY = "low_liquidity"
    NEWS_CONFLICT = "news_conflict"


class AlertTypeEnum(Enum):
    """Типы системных алертов"""
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_VETOED = "signal_vetoed"
    MARKET_ANOMALY = "market_anomaly"
    SYSTEM_HEALTH = "system_health"
    DATA_QUALITY = "data_quality"
    API_ERROR = "api_error"
    DATABASE_ERROR = "database_error"


@dataclass
class TradingSignal:
    """Базовый торговый сигнал"""
    symbol: str
    side: str  # "BUY" или "SELL"
    scenario_id: str
    status: SignalStatusEnum
    level: SignalLevelEnum
    price_entry: float
    sl: float
    tp1: float
    tp2: float
    tp3: float
    rr1: float  # Risk/Reward ratio для TP1
    rr2: float  # Risk/Reward ratio для TP2
    rr3: float  # Risk/Reward ratio для TP3
    timestamp: int = field(default_factory=current_epoch_ms)
    reason: str = ""


@dataclass
class EnhancedTradingSignal(TradingSignal):
    """Расширенный торговый сигнал с дополнительным контекстом"""
    indicators: Dict[str, Any] = field(default_factory=dict)
    confidence_score: float = 0.0
    market_conditions: Dict[str, Any] = field(default_factory=dict)
    news_impact: Dict[str, Any] = field(default_factory=dict)
    volume_profile_context: Dict[str, Any] = field(default_factory=dict)
    veto_reasons: List[VetoReasonEnum] = field(default_factory=list)


@dataclass
class Alert:
    """Системный алерт"""
    alert_type: AlertTypeEnum
    symbol: str
    message: str
    severity: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    timestamp: int = field(default_factory=current_epoch_ms)
    data: Dict[str, Any] = field(default_factory=dict)
    resolved: bool = False


# Остальные dataclass'ы...
