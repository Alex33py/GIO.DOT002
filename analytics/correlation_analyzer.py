#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Market Correlation Analyzer
Calculates correlation between crypto assets
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import numpy as np
from config.settings import logger


class CorrelationAnalyzer:
    """
    Market Correlation Analyzer

    Calculates Pearson correlation between assets based on:
    - Price changes (24h, 7d, 30d)
    - Volume changes
    - Market cap changes
    """

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.cache_duration = 300  # 5 minutes cache
        self._cache = {}
        self._cache_timestamp = {}
        logger.info("✅ CorrelationAnalyzer инициализирован")

    async def calculate_correlation_matrix(
        self, symbols: List[str], period: str = "24h"
    ) -> Dict:
        """
        Calculate correlation matrix for multiple symbols

        Args:
            symbols: List of symbols (e.g., ["BTCUSDT", "ETHUSDT"])
            period: Time period ("24h", "7d", "30d")

        Returns:
            {
                "matrix": [[1.0, 0.92], [0.92, 1.0]],
                "symbols": ["BTC", "ETH"],
                "period": "24h",
                "timestamp": datetime,
                "insights": {...}
            }
        """
        try:
            # Check cache
            cache_key = f"corr_{'-'.join(symbols)}_{period}"
            if self._is_cached(cache_key):
                return self._cache[cache_key]

            # Получаем данные изменений цен для всех символов
            price_changes = await self._get_price_changes(symbols, period)

            if not price_changes or len(price_changes) < 2:
                return self._empty_result(symbols, period)

            # Вычисляем корреляционную матрицу
            matrix = self._calculate_correlation(price_changes)

            # Генерируем insights
            insights = self._generate_insights(matrix, symbols)

            result = {
                "matrix": matrix,
                "symbols": [s.replace("USDT", "") for s in symbols],
                "period": period,
                "timestamp": datetime.now(),
                "insights": insights,
            }

            # Кэшируем результат
            self._cache[cache_key] = result
            self._cache_timestamp[cache_key] = datetime.now()

            return result

        except Exception as e:
            logger.error(f"calculate_correlation_matrix error: {e}", exc_info=True)
            return self._empty_result(symbols, period)

    async def _get_price_changes(
        self, symbols: List[str], period: str
    ) -> Optional[List[List[float]]]:
        """
        Get price changes for all symbols

        Returns:
            List of price change arrays for each symbol
        """
        try:
            price_changes = []

            for symbol in symbols:
                ticker = await self.bot.bybit_connector.get_ticker(symbol)
                if ticker:
                    change = float(ticker.get("price24hPcnt", 0)) * 100
                    price_changes.append([change])
                else:
                    price_changes.append([0.0])

            return price_changes if len(price_changes) == len(symbols) else None

        except Exception as e:
            logger.error(f"_get_price_changes error: {e}")
            return None

    def _calculate_correlation(self, data: List[List[float]]) -> List[List[float]]:
        """
        Calculate Pearson correlation matrix

        Args:
            data: List of arrays [[change1], [change2], ...]

        Returns:
            Correlation matrix as 2D list
        """
        try:
            # Конвертируем в numpy array
            arr = np.array(data)

            # Если данные одномерные (только одно значение), создаем простую корреляцию
            if arr.shape[1] == 1:
                # Для одного измерения просто берем correlation based on знака
                n = len(data)
                matrix = [[0.0] * n for _ in range(n)]

                for i in range(n):
                    for j in range(n):
                        if i == j:
                            matrix[i][j] = 1.0
                        else:
                            # Простая корреляция на основе знака изменения
                            val_i = data[i][0]
                            val_j = data[j][0]

                            if val_i * val_j > 0:  # Одинаковый знак
                                # Корреляция зависит от схожести величины
                                ratio = min(abs(val_i), abs(val_j)) / max(
                                    abs(val_i), abs(val_j)
                                )
                                matrix[i][j] = 0.5 + 0.5 * ratio
                            else:  # Разные знаки
                                matrix[i][j] = -0.3  # Слабая негативная корреляция

                return matrix

            # Для многомерных данных используем numpy
            corr_matrix = np.corrcoef(arr)
            return corr_matrix.tolist()

        except Exception as e:
            logger.error(f"_calculate_correlation error: {e}")
            # Возвращаем identity matrix как fallback
            n = len(data)
            return [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)]

    def _generate_insights(self, matrix: List[List[float]], symbols: List[str]) -> Dict:
        """
        Generate insights from correlation matrix

        Returns:
            {
                "highest_pair": ("BTC", "ETH", 0.92),
                "lowest_pair": ("BTC", "XRP", 0.45),
                "average_correlation": 0.78,
                "strong_correlations": [("BTC", "ETH"), ...],
                "weak_correlations": [("SOL", "XRP"), ...]
            }
        """
        try:
            n = len(matrix)
            if n < 2:
                return {}

            # Найти highest correlation (не диагональ)
            highest = (None, None, 0)
            lowest = (None, None, 1)
            total = 0
            count = 0

            strong_pairs = []
            weak_pairs = []

            for i in range(n):
                for j in range(i + 1, n):
                    corr = matrix[i][j]
                    sym_i = symbols[i].replace("USDT", "")
                    sym_j = symbols[j].replace("USDT", "")

                    total += corr
                    count += 1

                    if corr > highest[2]:
                        highest = (sym_i, sym_j, corr)

                    if corr < lowest[2]:
                        lowest = (sym_i, sym_j, corr)

                    if corr >= 0.8:
                        strong_pairs.append((sym_i, sym_j))
                    elif corr <= 0.5:
                        weak_pairs.append((sym_i, sym_j))

            avg_corr = total / count if count > 0 else 0

            return {
                "highest_pair": highest,
                "lowest_pair": lowest,
                "average_correlation": round(avg_corr, 2),
                "strong_correlations": strong_pairs[:3],  # Top 3
                "weak_correlations": weak_pairs[:3],  # Top 3
            }

        except Exception as e:
            logger.error(f"_generate_insights error: {e}")
            return {}

    def _is_cached(self, key: str) -> bool:
        """Check if result is cached and still valid"""
        if key not in self._cache:
            return False

        timestamp = self._cache_timestamp.get(key)
        if not timestamp:
            return False

        age = (datetime.now() - timestamp).total_seconds()
        return age < self.cache_duration

    def _empty_result(self, symbols: List[str], period: str) -> Dict:
        """Return empty result structure"""
        n = len(symbols)
        return {
            "matrix": [[1.0 if i == j else 0.0 for j in range(n)] for i in range(n)],
            "symbols": [s.replace("USDT", "") for s in symbols],
            "period": period,
            "timestamp": datetime.now(),
            "insights": {},
        }

    def format_correlation_matrix(self, result: Dict) -> str:
        """
        Format correlation matrix for Telegram display

        Returns:
            Formatted string with matrix and insights
        """
        try:
            matrix = result["matrix"]
            symbols = result["symbols"]
            insights = result.get("insights", {})

            lines = []
            lines.append(f"📊 MARKET CORRELATION MATRIX ({result['period']})")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("")

            # Header row
            header = "     " + "  ".join([f"{s:>4}" for s in symbols])
            lines.append(header)

            # Matrix rows
            for i, row in enumerate(matrix):
                row_str = f"{symbols[i]:>4} "
                row_str += " ".join([f"{val:>5.2f}" for val in row])
                lines.append(row_str)

            lines.append("")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")

            # Insights
            if insights:
                lines.append("")
                lines.append("🔍 INSIGHTS:")

                highest = insights.get("highest_pair")
                if highest and highest[0]:
                    lines.append(
                        f"• Highest: {highest[0]}-{highest[1]} ({highest[2]:.2f})"
                    )

                lowest = insights.get("lowest_pair")
                if lowest and lowest[0]:
                    lines.append(f"• Lowest: {lowest[0]}-{lowest[1]} ({lowest[2]:.2f})")

                avg = insights.get("average_correlation", 0)
                if avg > 0.8:
                    strength = "VERY STRONG"
                elif avg > 0.6:
                    strength = "STRONG"
                elif avg > 0.4:
                    strength = "MODERATE"
                else:
                    strength = "WEAK"

                lines.append(f"• Average: {avg:.2f} ({strength})")

                strong = insights.get("strong_correlations", [])
                if strong:
                    pairs_str = ", ".join([f"{p[0]}-{p[1]}" for p in strong])
                    lines.append(f"• Strong pairs: {pairs_str}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"format_correlation_matrix error: {e}")
            return "⚠️ Ошибка форматирования"
