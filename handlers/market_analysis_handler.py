#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Market Analysis Handler для GIO Bot
Основной обработчик анализа рынка с интеграцией всех модулей
"""

import sqlite3
import logging
from typing import Dict, Optional
from handlers.support_resistance_detector import AdvancedSupportResistanceDetector
from config.settings import DATA_DIR

logger = logging.getLogger(__name__)


class MarketAnalysisHandler:
    """Обработчик комплексного анализа рынка"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or f"{DATA_DIR}/gio.db"

        # ✅ Инициализация детекторов
        self.sr_detector = AdvancedSupportResistanceDetector(
            atr_multiplier=0.5,
            volume_threshold=1.5
        )

        logger.info("✅ MarketAnalysisHandler инициализирован")

    def analyze_symbol(self, symbol: str) -> Dict:
        """
        Комплексный анализ символа

        Args:
            symbol: Торговая пара (например, BTCUSDT)

        Returns:
            Dict с полным анализом
        """
        try:
            logger.info(f"🔍 Начинаем анализ {symbol}")

            # 1. Получаем базовые данные
            market_data = self._get_market_data(symbol)

            if not market_data:
                logger.warning(f"⚠️ Нет данных для {symbol}")
                return {"error": "Нет данных"}

            # 2. Формируем features для анализа
            features_dict = self._prepare_features(symbol, market_data)

            # 3. Расчёт Volume Profile
            volume_profile = self._calculate_volume_profile(symbol)
            features_dict.update(volume_profile)

            # 4. ✅ SUPPORT/RESISTANCE DETECTION
            sr_levels = self.sr_detector.detect_support_resistance(features_dict)
            features_dict['sr_levels'] = sr_levels

            logger.info(f"✅ SR Levels для {symbol}: {sr_levels.get('summary', 'N/A')}")

            return features_dict

        except Exception as e:
            logger.error(f"❌ Ошибка анализа {symbol}: {e}", exc_info=True)
            return {"error": str(e)}

    def _get_market_data(self, symbol: str) -> Optional[Dict]:
        """Получение данных из БД"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = """
            SELECT price, volume, high, low, atr
            FROM market_data
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """
            cursor.execute(query, (symbol,))
            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            return {
                "price": row[0],
                "volume": row[1],
                "high": row[2],
                "low": row[3],
                "atr": row[4]
            }
        except Exception as e:
            logger.error(f"DB error: {e}")
            return None

    def _prepare_features(self, symbol: str, market_data: Dict) -> Dict:
        """Подготовка features для анализа"""
        features = market_data.copy()

        # Добавляем дополнительные поля
        features['symbol'] = symbol
        features['order_book_bids'] = 0  # Заглушка
        features['order_book_asks'] = 0  # Заглушка
        features['cvd_slope'] = 0  # Заглушка
        features['cvd_value'] = 0  # Заглушка

        return features

    def _calculate_volume_profile(self, symbol: str) -> Dict:
        """Упрощённый Volume Profile на основе последних 100 свечей"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            query = """
            SELECT price, volume FROM market_data
            WHERE symbol = ?
            ORDER BY timestamp DESC
            LIMIT 100
            """
            cursor.execute(query, (symbol,))
            rows = cursor.fetchall()
            conn.close()

            if not rows or len(rows) < 10:
                logger.warning(f"Volume Profile: недостаточно данных для {symbol}")
                return {"poc": 0, "vah": 0, "val": 0}

            prices = [row[0] for row in rows if row[0] > 0]
            volumes = [row[1] for row in rows if row[1] > 0]

            if not prices or not volumes:
                return {"poc": 0, "vah": 0, "val": 0}

            # POC = цена с максимальным объёмом
            max_vol_idx = volumes.index(max(volumes))
            poc = prices[max_vol_idx]

            # VAH/VAL = топ 30% и низ 30% по объёму
            sorted_data = sorted(zip(prices, volumes), key=lambda x: x[1], reverse=True)
            top_30_count = max(1, len(sorted_data) // 3)
            top_30 = sorted_data[:top_30_count]

            if top_30:
                vah = max([p for p, v in top_30])
                val = min([p for p, v in top_30])
            else:
                vah = max(prices)
                val = min(prices)

            logger.info(f"Volume Profile для {symbol}: POC={poc:.2f}, VAH={vah:.2f}, VAL={val:.2f}")
            return {"poc": poc, "vah": vah, "val": val}

        except Exception as e:
            logger.error(f"Volume Profile calculation error: {e}", exc_info=True)
            return {"poc": 0, "vah": 0, "val": 0}


# ✅ Экспортируем для использования в других модулях
if __name__ == "__main__":
    # Тестирование
    handler = MarketAnalysisHandler()
    result = handler.analyze_symbol("BTCUSDT")
    print(f"Результат: {result}")
