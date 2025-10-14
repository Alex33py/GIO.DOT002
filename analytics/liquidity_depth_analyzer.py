#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Liquidity Depth Analyzer
Analyzes orderbook depth for support/resistance and whale walls
"""

import asyncio
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from config.settings import logger


class LiquidityDepthAnalyzer:
    """
    Liquidity Depth Analyzer

    Analyzes orderbook depth to identify:
    - Bid/Ask walls
    - Support/Resistance levels based on liquidity
    - Whale walls (large orders)
    - Liquidity imbalances
    """

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.cache_duration = 60  # 1 minute cache
        self._cache = {}
        self._cache_timestamp = {}

        # Thresholds
        self.whale_threshold_usd = 1_000_000  # $1M+ считается whale wall
        self.significant_level_threshold = 500_000  # $500K+ significant

        logger.info("✅ LiquidityDepthAnalyzer инициализирован")

    async def analyze_liquidity(self, symbol: str) -> Dict:
        """
        Analyze liquidity depth for symbol

        Returns:
            {
                "symbol": "BTCUSDT",
                "price": 112145.90,
                "timestamp": datetime,
                "total_bid_usd": 45200000,
                "total_ask_usd": 41000000,
                "imbalance": 4200000,
                "imbalance_pct": 4.2,
                "bid_walls": [...],
                "ask_walls": [...],
                "key_levels": {...}
            }
        """
        try:
            # Check cache
            cache_key = f"liq_{symbol}"
            if self._is_cached(cache_key):
                return self._cache[cache_key]

            # Get current price
            ticker = await self.bot.bybit_connector.get_ticker(symbol)
            if not ticker:
                return self._empty_result(symbol)

            current_price = float(ticker.get("lastPrice", 0))

            # Get orderbook (L2 depth)
            orderbook = await self._get_orderbook(symbol)
            if not orderbook:
                return self._empty_result(symbol)

            # Analyze bids and asks
            bid_analysis = self._analyze_side(
                orderbook["bids"], current_price, side="bid"
            )
            ask_analysis = self._analyze_side(
                orderbook["asks"], current_price, side="ask"
            )

            # Calculate totals and imbalance
            total_bid = bid_analysis["total_usd"]
            total_ask = ask_analysis["total_usd"]
            imbalance = total_bid - total_ask
            imbalance_pct = (imbalance / (total_bid + total_ask)) * 100 if (total_bid + total_ask) > 0 else 0

            # Find key levels
            key_levels = self._find_key_levels(
                bid_analysis["walls"], ask_analysis["walls"], current_price
            )

            result = {
                "symbol": symbol,
                "price": current_price,
                "timestamp": datetime.now(),
                "total_bid_usd": total_bid,
                "total_ask_usd": total_ask,
                "imbalance": imbalance,
                "imbalance_pct": imbalance_pct,
                "bid_walls": bid_analysis["walls"],
                "ask_walls": ask_analysis["walls"],
                "key_levels": key_levels,
            }

            # Cache result
            self._cache[cache_key] = result
            self._cache_timestamp[cache_key] = datetime.now()

            return result

        except Exception as e:
            logger.error(f"analyze_liquidity error: {e}", exc_info=True)
            return self._empty_result(symbol)

    async def _get_orderbook(self, symbol: str, limit: int = 50) -> Optional[Dict]:
        """Get L2 orderbook from exchange"""
        try:
            # Try Bybit first
            orderbook = await self.bot.bybit_connector.get_orderbook(symbol, limit=limit)
            if orderbook and "bids" in orderbook and "asks" in orderbook:
                return orderbook

            # Fallback to Binance if needed
            # orderbook = await self.bot.binance_connector.get_orderbook(symbol, limit=limit)

            return None

        except Exception as e:
            logger.error(f"_get_orderbook error: {e}")
            return None

    def _analyze_side(
        self, orders: List[List], current_price: float, side: str
    ) -> Dict:
        """
        Analyze one side of orderbook (bids or asks)

        Returns:
            {
                "total_usd": 45200000,
                "walls": [
                    {"price": 111800, "size_usd": 2400000, "is_whale": True},
                    ...
                ]
            }
        """
        try:
            total_usd = 0
            walls = []

            for order in orders:
                price = float(order[0])
                size = float(order[1])
                size_usd = price * size

                total_usd += size_usd

                # Check if significant level
                if size_usd >= self.significant_level_threshold:
                    is_whale = size_usd >= self.whale_threshold_usd

                    walls.append({
                        "price": price,
                        "size_usd": size_usd,
                        "is_whale": is_whale,
                        "distance_pct": ((price - current_price) / current_price) * 100,
                    })

            # Sort walls by size (descending)
            walls.sort(key=lambda x: x["size_usd"], reverse=True)

            return {
                "total_usd": total_usd,
                "walls": walls[:10],  # Top 10 walls
            }

        except Exception as e:
            logger.error(f"_analyze_side error: {e}")
            return {"total_usd": 0, "walls": []}

    def _find_key_levels(
        self, bid_walls: List[Dict], ask_walls: List[Dict], current_price: float
    ) -> Dict:
        """Find strongest support/resistance levels"""
        try:
            strongest_support = None
            strongest_resistance = None
            nearest_support = None
            nearest_resistance = None

            # Find strongest support (largest bid wall)
            if bid_walls:
                strongest_support = bid_walls[0]  # Already sorted by size

                # Find nearest support
                for wall in bid_walls:
                    if wall["price"] < current_price:
                        nearest_support = wall
                        break

            # Find strongest resistance (largest ask wall)
            if ask_walls:
                strongest_resistance = ask_walls[0]

                # Find nearest resistance
                for wall in ask_walls:
                    if wall["price"] > current_price:
                        nearest_resistance = wall
                        break

            return {
                "strongest_support": strongest_support,
                "strongest_resistance": strongest_resistance,
                "nearest_support": nearest_support,
                "nearest_resistance": nearest_resistance,
            }

        except Exception as e:
            logger.error(f"_find_key_levels error: {e}")
            return {}

    def format_liquidity_analysis(self, result: Dict) -> str:
        """Format liquidity analysis for Telegram"""
        try:
            symbol = result["symbol"].replace("USDT", "")
            price = result["price"]
            total_bid = result["total_bid_usd"] / 1_000_000  # Convert to millions
            total_ask = result["total_ask_usd"] / 1_000_000
            imbalance = result["imbalance"] / 1_000_000
            imbalance_pct = result["imbalance_pct"]

            lines = []
            lines.append(f"💧 LIQUIDITY DEPTH ANALYSIS — {symbol}")
            lines.append("━━━━━━━━━━━━━━━━━━━━━━")
            lines.append("")
            lines.append(f"💰 Current Price: ${price:,.2f}")
            lines.append("")

            # Orderbook summary
            bid_pct = (total_bid / (total_bid + total_ask)) * 100 if (total_bid + total_ask) > 0 else 0
            ask_pct = 100 - bid_pct

            imbalance_emoji = "🟢" if imbalance > 0 else "🔴" if imbalance < 0 else "⚪"
            pressure = "BUY" if imbalance > 0 else "SELL" if imbalance < 0 else "NEUTRAL"

            lines.append("📊 ORDERBOOK SUMMARY")
            lines.append(f"├─ Total BID: ${total_bid:.1f}M ({bid_pct:.1f}%)")
            lines.append(f"├─ Total ASK: ${total_ask:.1f}M ({ask_pct:.1f}%)")
            lines.append(f"└─ Imbalance: {imbalance:+.1f}M ({pressure} pressure) {imbalance_emoji}")
            lines.append("")

            # Bid walls (support)
            bid_walls = result.get("bid_walls", [])[:5]  # Top 5
            if bid_walls:
                lines.append("🧱 MAJOR BID WALLS (Support)")
                for wall in bid_walls:
                    whale = " (🐋 WHALE)" if wall["is_whale"] else ""
                    lines.append(
                        f"├─ ${wall['price']:,.0f}: ${wall['size_usd']/1_000_000:.1f}M{whale}"
                    )
                lines.append("")

            # Ask walls (resistance)
            ask_walls = result.get("ask_walls", [])[:5]
            if ask_walls:
                lines.append("🧱 MAJOR ASK WALLS (Resistance)")
                for wall in ask_walls:
                    whale = " (🐋 WHALE)" if wall["is_whale"] else ""
                    lines.append(
                        f"├─ ${wall['price']:,.0f}: ${wall['size_usd']/1_000_000:.1f}M{whale}"
                    )
                lines.append("")

            # Key levels
            key_levels = result.get("key_levels", {})
            if key_levels:
                lines.append("🎯 KEY LEVELS")

                strongest_support = key_levels.get("strongest_support")
                if strongest_support:
                    lines.append(
                        f"├─ Strongest Support: ${strongest_support['price']:,.0f} "
                        f"(${strongest_support['size_usd']/1_000_000:.1f}M)"
                    )

                strongest_resistance = key_levels.get("strongest_resistance")
                if strongest_resistance:
                    lines.append(
                        f"├─ Strongest Resistance: ${strongest_resistance['price']:,.0f} "
                        f"(${strongest_resistance['size_usd']/1_000_000:.1f}M)"
                    )

                nearest_support = key_levels.get("nearest_support")
                if nearest_support:
                    lines.append(
                        f"└─ Nearest Support: ${nearest_support['price']:,.0f} "
                        f"({nearest_support['distance_pct']:+.2f}%)"
                    )

                lines.append("")

            # Interpretation
            lines.append("💡 INTERPRETATION:")
            if imbalance_pct > 5:
                lines.append("• Strong BUY pressure (BID >> ASK)")
            elif imbalance_pct < -5:
                lines.append("• Strong SELL pressure (ASK >> BID)")
            else:
                lines.append("• Balanced orderbook")

            if bid_walls and bid_walls[0]["is_whale"]:
                lines.append(f"• Strong support at ${bid_walls[0]['price']:,.0f}")

            if ask_walls and ask_walls[0]["is_whale"]:
                lines.append(f"• Strong resistance at ${ask_walls[0]['price']:,.0f}")

            return "\n".join(lines)

        except Exception as e:
            logger.error(f"format_liquidity_analysis error: {e}")
            return "⚠️ Ошибка форматирования"

    def _is_cached(self, key: str) -> bool:
        """Check if result is cached and valid"""
        if key not in self._cache:
            return False

        timestamp = self._cache_timestamp.get(key)
        if not timestamp:
            return False

        age = (datetime.now() - timestamp).total_seconds()
        return age < self.cache_duration

    def _empty_result(self, symbol: str) -> Dict:
        """Return empty result"""
        return {
            "symbol": symbol,
            "price": 0,
            "timestamp": datetime.now(),
            "total_bid_usd": 0,
            "total_ask_usd": 0,
            "imbalance": 0,
            "imbalance_pct": 0,
            "bid_walls": [],
            "ask_walls": [],
            "key_levels": {},
        }
