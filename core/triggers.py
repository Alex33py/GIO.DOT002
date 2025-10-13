# -*- coding: utf-8 -*-
"""
Система триггеров для точного определения точек входа
T1: Технический паттерн
T2: Объёмное подтверждение
T3: Подтверждение потока ордеров
"""

from typing import Dict, List, Optional
from datetime import datetime
from config.settings import logger

class TriggerSystem:
    """Система множественных триггеров для входа в позицию"""

    def __init__(self):
        # Настройки чувствительности
        self.t1_sensitivity = 0.7  # Порог для T1
        self.t2_sensitivity = 1.5  # Множитель объёма для T2
        self.t3_sensitivity = 0.6  # Порог для T3

        logger.info("✅ TriggerSystem инициализирована")

    def evaluate_all_triggers(self, direction: str, indicators: Dict,
                              market_data: Dict, candles: List[Dict]) -> Dict:
        """
        Оценка всех триггеров

        Returns:
            {
                't1': {'fired': bool, 'score': float, 'details': str},
                't2': {'fired': bool, 'score': float, 'details': str},
                't3': {'fired': bool, 'score': float, 'details': str},
                'total_fired': int,
                'confidence': float
            }
        """

        t1_result = self.evaluate_t1_technical(direction, indicators, candles)
        t2_result = self.evaluate_t2_volume(direction, market_data)
        t3_result = self.evaluate_t3_orderflow(direction, market_data, indicators)

        total_fired = sum([
            t1_result['fired'],
            t2_result['fired'],
            t3_result['fired']
        ])

        # Итоговая уверенность
        confidence = (
            t1_result['score'] * 0.4 +
            t2_result['score'] * 0.3 +
            t3_result['score'] * 0.3
        )

        logger.debug(f"🎯 Триггеры: T1={t1_result['fired']}, T2={t2_result['fired']}, T3={t3_result['fired']}, confidence={confidence:.2f}")

        return {
            't1': t1_result,
            't2': t2_result,
            't3': t3_result,
            'total_fired': total_fired,
            'confidence': confidence
        }

    def evaluate_t1_technical(self, direction: str, indicators: Dict,
                              candles: List[Dict]) -> Dict:
        """
        T1: Технический триггер
        Проверяет паттерны, индикаторы, пробои уровней
        """
        score = 0.0
        details = []

        # 1. RSI анализ
        rsi = indicators.get('rsi_1h', 50)
        if direction == 'long':
            if 25 < rsi < 45:  # Зона перепроданности
                score += 0.3
                details.append(f"RSI oversold ({rsi:.1f})")
        else:
            if 55 < rsi < 75:  # Зона перекупленности
                score += 0.3
                details.append(f"RSI overbought ({rsi:.1f})")

        # 2. MACD гистограмма
        macd_hist = indicators.get('macd_histogram_1h', 0)
        macd_prev = indicators.get('macd_histogram_1h_prev', 0)

        if direction == 'long' and macd_hist > 0 and macd_hist > macd_prev:
            score += 0.3
            details.append("MACD bullish crossover")
        elif direction == 'short' and macd_hist < 0 and macd_hist < macd_prev:
            score += 0.3
            details.append("MACD bearish crossover")

        # 3. Паттерн свечей (последние 3 свечи)
        if len(candles) >= 3:
            pattern_score = self._detect_candle_pattern(direction, candles[-3:])
            score += pattern_score * 0.2
            if pattern_score > 0.5:
                details.append(f"Bullish pattern" if direction == 'long' else "Bearish pattern")

        # 4. Пробой Moving Average
        price = indicators.get('close', 0)
        ema_20 = indicators.get('ema_20_1h', 0)
        ema_50 = indicators.get('ema_50_1h', 0)

        if direction == 'long' and price > ema_20 > ema_50:
            score += 0.2
            details.append("Price above EMAs (bullish)")
        elif direction == 'short' and price < ema_20 < ema_50:
            score += 0.2
            details.append("Price below EMAs (bearish)")

        fired = score >= self.t1_sensitivity

        return {
            'fired': fired,
            'score': min(score, 1.0),
            'details': ', '.join(details) if details else 'No triggers'
        }

    def _detect_candle_pattern(self, direction: str, candles: List[Dict]) -> float:
        """Определение свечных паттернов"""
        if len(candles) < 3:
            return 0.0

        c1, c2, c3 = candles[-3], candles[-2], candles[-1]

        # Для лонга: ищем бычьи паттерны
        if direction == 'long':
            # Бычье поглощение
            if (c2['close'] < c2['open'] and  # Медвежья свеча
                c3['close'] > c3['open'] and  # Бычья свеча
                c3['close'] > c2['open'] and  # Поглощает предыдущую
                c3['open'] < c2['close']):
                return 1.0

            # Утренняя звезда
            if (c1['close'] < c1['open'] and  # Медвежья
                abs(c2['close'] - c2['open']) < (c2['high'] - c2['low']) * 0.3 and  # Доджи
                c3['close'] > c3['open'] and  # Бычья
                c3['close'] > (c1['open'] + c1['close']) / 2):  # Закрылась выше середины первой
                return 0.9

            # Три белых солдата
            if all(c['close'] > c['open'] for c in [c1, c2, c3]) and \
               c2['close'] > c1['close'] and c3['close'] > c2['close']:
                return 0.8

        # Для шорта: ищем медвежьи паттерны
        else:
            # Медвежье поглощение
            if (c2['close'] > c2['open'] and  # Бычья свеча
                c3['close'] < c3['open'] and  # Медвежья свеча
                c3['close'] < c2['open'] and  # Поглощает предыдущую
                c3['open'] > c2['close']):
                return 1.0

            # Вечерняя звезда
            if (c1['close'] > c1['open'] and  # Бычья
                abs(c2['close'] - c2['open']) < (c2['high'] - c2['low']) * 0.3 and  # Доджи
                c3['close'] < c3['open'] and  # Медвежья
                c3['close'] < (c1['open'] + c1['close']) / 2):  # Закрылась ниже середины первой
                return 0.9

            # Три чёрные вороны
            if all(c['close'] < c['open'] for c in [c1, c2, c3]) and \
               c2['close'] < c1['close'] and c3['close'] < c2['close']:
                return 0.8

        return 0.0

    def evaluate_t2_volume(self, direction: str, market_data: Dict) -> Dict:
        """
        T2: Объёмный триггер
        Проверяет всплески объёма и их направление
        """
        score = 0.0
        details = []

        # Текущий объём vs средний
        volume_ratio = market_data.get('volume_ratio', 1.0)

        if volume_ratio >= 3.0:
            score = 1.0
            details.append(f"Сильный всплеск объёма ({volume_ratio:.1f}x)")
        elif volume_ratio >= 2.0:
            score = 0.8
            details.append(f"Всплеск объёма ({volume_ratio:.1f}x)")
        elif volume_ratio >= self.t2_sensitivity:
            score = 0.6
            details.append(f"Повышенный объём ({volume_ratio:.1f}x)")
        else:
            score = 0.3
            details.append(f"Нормальный объём ({volume_ratio:.1f}x)")

        # Проверяем направление объёма через buy/sell volume
        buy_volume = market_data.get('buy_volume', 0)
        sell_volume = market_data.get('sell_volume', 0)
        total_volume = buy_volume + sell_volume

        if total_volume > 0:
            buy_ratio = buy_volume / total_volume

            if direction == 'long' and buy_ratio > 0.6:
                score = min(score * 1.2, 1.0)
                details.append(f"Доминирование покупок ({buy_ratio:.1%})")
            elif direction == 'short' and buy_ratio < 0.4:
                score = min(score * 1.2, 1.0)
                details.append(f"Доминирование продаж ({1-buy_ratio:.1%})")

        fired = score >= self.t2_sensitivity / 2  # Более мягкий порог

        return {
            'fired': fired,
            'score': min(score, 1.0),
            'details': ', '.join(details) if details else 'Low volume'
        }

    def evaluate_t3_orderflow(self, direction: str, market_data: Dict,
                              indicators: Dict) -> Dict:
        """
        T3: Триггер потока ордеров (CVD + Orderbook)
        """
        score = 0.0
        details = []

        # 1. Cumulative Volume Delta (CVD)
        cvd = market_data.get('cvd', 0)
        cvd_normalized = cvd / 1000000  # Нормализуем к миллионам

        if direction == 'long' and cvd > 0:
            cvd_score = min(abs(cvd_normalized) / 5.0, 1.0)  # Макс 5M = 1.0
            score += cvd_score * 0.5
            details.append(f"Положительный CVD ({cvd:,.0f})")
        elif direction == 'short' and cvd < 0:
            cvd_score = min(abs(cvd_normalized) / 5.0, 1.0)
            score += cvd_score * 0.5
            details.append(f"Отрицательный CVD ({cvd:,.0f})")

        # 2. Orderbook pressure (bid/ask ratio)
        bid_volume = market_data.get('bid_volume', 0)
        ask_volume = market_data.get('ask_volume', 0)
        total_ob_volume = bid_volume + ask_volume

        if total_ob_volume > 0:
            bid_ratio = bid_volume / total_ob_volume

            if direction == 'long' and bid_ratio > 0.6:
                ob_score = (bid_ratio - 0.5) * 2  # 0.6 -> 0.2, 0.8 -> 0.6, 1.0 -> 1.0
                score += ob_score * 0.3
                details.append(f"Давление на покупку ({bid_ratio:.1%})")
            elif direction == 'short' and bid_ratio < 0.4:
                ob_score = (0.5 - bid_ratio) * 2
                score += ob_score * 0.3
                details.append(f"Давление на продажу ({1-bid_ratio:.1%})")

        # 3. Delta momentum (изменение CVD)
        cvd_prev = market_data.get('cvd_prev', 0)
        cvd_change = cvd - cvd_prev

        if direction == 'long' and cvd_change > 0:
            score += 0.2
            details.append("Растущий CVD")
        elif direction == 'short' and cvd_change < 0:
            score += 0.2
            details.append("Падающий CVD")

        fired = score >= self.t3_sensitivity

        return {
            'fired': fired,
            'score': min(score, 1.0),
            'details': ', '.join(details) if details else 'Neutral orderflow'
        }
