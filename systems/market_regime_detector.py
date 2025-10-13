# -*- coding: utf-8 -*-
"""
Market Regime Detector - определение текущего рыночного режима
Профессиональная терминология согласно КРИТЕРИЙ 2
"""


from typing import Dict, Optional
from config.settings import logger


class MarketRegimeDetector:
    """
    Определяет текущий рыночный режим на основе технических индикаторов

    Режимы (Market Regimes):
    - TRENDING: сильное направленное движение
    - RANGING: боковое движение в диапазоне
    - SQUEEZING: сжатие волатильности (перед прорывом)
    - EXPANDING: расширение волатильности (активный рынок)
    - NEUTRAL: смешанные сигналы
    """

    def __init__(self):
        self.current_regime = "NEUTRAL"
        self.regime_confidence = 0.0

        logger.info("✅ MarketRegimeDetector инициализирован")

    def detect(self, market_data: Dict) -> str:
        """
        Определить текущий режим рынка (простой метод - возвращает только строку)

        Args:
            market_data: Словарь с рыночными данными и индикаторами

        Returns:
            Название режима: TRENDING, RANGING, SQUEEZING, EXPANDING, NEUTRAL
        """
        try:
            # Извлекаем ключевые метрики
            adx = market_data.get("adx", 0)
            volume_ratio = market_data.get("volume", 1) / max(
                market_data.get("volume_ma20", 1), 1
            )
            bb_width_percentile = market_data.get("bb_width_percentile", 50)
            atr_percentile = market_data.get("atr_percentile", 50)

            # Детекция режима
            regime = self._detect_regime_logic(
                adx, volume_ratio, bb_width_percentile, atr_percentile
            )

            # Обновляем состояние
            self.current_regime = regime

            return regime

        except Exception as e:
            logger.error(f"❌ Ошибка определения режима рынка: {e}")
            return "NEUTRAL"

    def detect_regime(self, market_data: Dict) -> Dict:
        """
        Определить текущий режим рынка (расширенный метод - возвращает Dict)

        Этот метод используется в market_dashboard.py

        Args:
            market_data: Словарь с рыночными данными

        Returns:
            Dict с полной информацией о режиме:
            {
                "regime": "RANGING",        # Текущий режим (UPPERCASE)
                "confidence": 0.75,         # Уверенность (0.0-1.0)
                "description": "..."        # Описание режима
            }
        """
        try:
            # Получаем базовые метрики
            price = market_data.get("price", 0)
            volume = market_data.get("volume", 0)
            high_24h = market_data.get("high_24h", price)
            low_24h = market_data.get("low_24h", price)

            # Рассчитываем дополнительные метрики
            price_range = high_24h - low_24h if high_24h > low_24h else 0
            price_position = (price - low_24h) / price_range if price_range > 0 else 0.5

            # Определяем режим на основе имеющихся данных
            regime = self._detect_regime_simple(
                price, volume, high_24h, low_24h, price_position
            )

            # Рассчитываем confidence
            confidence = self._calculate_confidence(regime, market_data)

            # Получаем описание
            description = self.get_regime_description(regime)

            result = {
                "regime": regime,
                "confidence": confidence,
                "description": description,
            }

            # Обновляем состояние
            self.current_regime = regime
            self.regime_confidence = confidence

            logger.debug(f"✅ Режим определён: {regime} (confidence={confidence:.2f})")

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка detect_regime: {e}", exc_info=True)
            return {
                "regime": "NEUTRAL",
                "confidence": 0.5,
                "description": "Смешанные сигналы, нет чёткого направления",
            }

    def _detect_regime_logic(
        self,
        adx: float,
        volume_ratio: float,
        bb_width_percentile: float,
        atr_percentile: float,
    ) -> str:
        """Логика определения режима (полная версия с индикаторами)"""

        # 1. TRENDING: сильный ADX + высокий объём
        if adx > 30 and volume_ratio > 1.5:
            return "TRENDING"

        # 2. SQUEEZING: низкий ADX + узкие полосы + низкий объём
        elif adx < 20 and bb_width_percentile < 30 and volume_ratio < 0.8:
            return "SQUEEZING"

        # 3. EXPANDING: широкие полосы + высокий объём
        elif bb_width_percentile > 60 and volume_ratio > 1.8:
            return "EXPANDING"

        # 4. RANGING: низкий ADX + средние полосы + низкий объём
        elif adx < 20 and 30 <= bb_width_percentile <= 60 and volume_ratio < 0.9:
            return "RANGING"

        # 5. NEUTRAL: всё остальное
        else:
            return "NEUTRAL"

    def _detect_regime_simple(
        self,
        price: float,
        volume: float,
        high_24h: float,
        low_24h: float,
        price_position: float,
    ) -> str:
        """
        Упрощённая логика определения режима (без сложных индикаторов)
        Используется когда нет ADX/BB данных
        """

        # Рассчитываем волатильность
        price_range = high_24h - low_24h
        volatility_pct = (price_range / price) * 100 if price > 0 else 0

        # 1. TRENDING: высокая волатильность + цена у границ
        if volatility_pct > 5 and (price_position > 0.7 or price_position < 0.3):
            return "TRENDING"

        # 2. RANGING: низкая волатильность + цена в середине
        elif volatility_pct < 3 and 0.4 <= price_position <= 0.6:
            return "RANGING"

        # 3. EXPANDING: высокая волатильность + цена в середине
        elif volatility_pct > 4 and 0.3 <= price_position <= 0.7:
            return "EXPANDING"

        # 4. SQUEEZING: очень низкая волатильность
        elif volatility_pct < 2:
            return "SQUEEZING"

        # 5. NEUTRAL: всё остальное
        else:
            return "NEUTRAL"

    def _calculate_confidence(self, regime: str, market_data: Dict) -> float:
        """
        Рассчитать уверенность в определении режима

        Returns:
            float от 0.0 до 1.0
        """
        try:
            # Базовая confidence в зависимости от режима
            base_confidence = {
                "TRENDING": 0.7,
                "RANGING": 0.65,
                "SQUEEZING": 0.6,
                "EXPANDING": 0.65,
                "NEUTRAL": 0.5,
            }

            confidence = base_confidence.get(regime, 0.5)

            # Увеличиваем confidence если есть подтверждающие данные
            volume = market_data.get("volume", 0)
            if volume > 0:
                confidence += 0.1  # Есть объём данных

            # Ограничиваем диапазон
            confidence = max(0.0, min(1.0, confidence))

            return confidence

        except Exception as e:
            logger.debug(f"⚠️ Ошибка расчёта confidence: {e}")
            return 0.5

    def get_regime_description(self, regime: Optional[str] = None) -> str:
        """Получить описание режима"""

        if regime is None:
            regime = self.current_regime

        descriptions = {
            "TRENDING": "Сильное направленное движение с высоким объёмом",
            "RANGING": "Боковое движение в определённом диапазоне",
            "SQUEEZING": "Сжатие волатильности, возможен скорый прорыв",
            "EXPANDING": "Расширение волатильности, активное движение",
            "NEUTRAL": "Смешанные сигналы, нет чёткого направления",
        }

        return descriptions.get(regime, "Неизвестный режим")

    def get_recommended_strategies(self, regime: Optional[str] = None) -> list:
        """Получить рекомендуемые стратегии для режима"""

        if regime is None:
            regime = self.current_regime

        strategy_map = {
            "TRENDING": ["momentum", "breakout"],
            "RANGING": ["mean_reversion", "counter_trend"],
            "SQUEEZING": ["squeeze", "breakout"],
            "EXPANDING": ["momentum", "squeeze"],
            "NEUTRAL": ["mean_reversion", "counter_trend", "squeeze"],
        }

        return strategy_map.get(regime, ["mean_reversion"])


# Экспорт
__all__ = ["MarketRegimeDetector"]
