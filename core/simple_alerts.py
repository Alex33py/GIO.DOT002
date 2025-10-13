#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Simple Alerts - Простые алерты (ликвидации, всплески объёмов, дисбалансы)
ВЕРСИЯ С АНТИСПАМОМ
"""

from typing import Dict, List
from datetime import datetime
import time
from config.settings import logger


class SimpleAlertsSystem:
    """Система простых алертов для критических рыночных событий"""

    def __init__(self, bot_instance):
        """
        Args:
            bot_instance: Основной экземпляр GIOCryptoBot
        """
        self.bot = bot_instance

        # Пороги для алертов (УВЕЛИЧЕНЫ ДЛЯ АНТИСПАМА!)
        self.volume_surge_threshold = 3.0  # 3x
        self.liquidation_threshold = 10_000_000  # $10M
        self.imbalance_threshold = 0.75  # 75%

        # История алертов (чтобы не спамить)
        self.recent_alerts = {}
        self.alert_cooldown = 300  # 5 минут между одинаковыми алертами

        # Глобальный лимит
        self.max_alerts_per_hour = 20
        self.alert_history = []  # [(timestamp, alert_type, symbol), ...]

        logger.info("✅ SimpleAlertsSystem инициализирована (АНТИСПАМ)")
        logger.info(f"   📊 Volume Surge: ≥{self.volume_surge_threshold}x")
        logger.info(f"   💰 Liquidations: ≥${self.liquidation_threshold:,.0f}")
        logger.info(f"   ⚖️ Imbalance: ≥{self.imbalance_threshold*100:.0f}%")


    async def check_alerts(self, symbol: str, market_data: Dict):
        """
        Проверка всех типов алертов

        Args:
            symbol: Торговая пара
            market_data: Текущие рыночные данные
        """
        try:
            # 1. Проверка всплесков объёма
            await self._check_volume_surge(symbol, market_data)

            # 2. Проверка крупных ликвидаций
            await self._check_large_liquidations(symbol, market_data)

            # 3. Проверка дисбалансов
            await self._check_order_imbalance(symbol, market_data)

        except Exception as e:
            logger.error(f"❌ Ошибка check_alerts: {e}")


    async def _check_volume_surge(self, symbol: str, market_data: Dict):
        """Проверка всплеска объёма"""
        try:
            current_volume = market_data.get("volume_24h", 0)
            avg_volume = market_data.get("avg_volume", current_volume)

            if avg_volume == 0:
                return

            volume_ratio = current_volume / avg_volume

            if volume_ratio >= self.volume_surge_threshold:
                # Проверяем cooldown
                if self._should_send_alert(symbol, "volume_surge"):
                    await self._send_alert(
                        alert_type="volume_surge",
                        symbol=symbol,
                        message=(
                            f"⚡ *ВСПЛЕСК ОБЪЁМА {symbol}*\n\n"
                            f"📊 Текущий объём: {current_volume:,.0f}\n"
                            f"📊 Средний объём: {avg_volume:,.0f}\n"
                            f"📈 Соотношение: *{volume_ratio:.2f}x*\n\n"
                            f"💡 Возможна сильная волатильность!"
                        )
                    )

                    self._record_alert(symbol, "volume_surge")

        except Exception as e:
            logger.error(f"❌ Ошибка _check_volume_surge: {e}")


    async def _check_large_liquidations(self, symbol: str, market_data: Dict):
        """Проверка крупных ликвидаций"""
        try:
            # Получаем данные ликвидаций
            liquidations = market_data.get("liquidations", {})

            long_liquidations = liquidations.get("long", 0)
            short_liquidations = liquidations.get("short", 0)
            total_liquidations = long_liquidations + short_liquidations

            if total_liquidations >= self.liquidation_threshold:
                # Определяем направление
                if long_liquidations > short_liquidations * 2:
                    direction = "LONG"
                    emoji = "📉"
                elif short_liquidations > long_liquidations * 2:
                    direction = "SHORT"
                    emoji = "📈"
                else:
                    direction = "MIXED"
                    emoji = "⚖️"

                if self._should_send_alert(symbol, "liquidations"):
                    await self._send_alert(
                        alert_type="liquidations",
                        symbol=symbol,
                        message=(
                            f"{emoji} *КРУПНЫЕ ЛИКВИДАЦИИ {symbol}*\n\n"
                            f"💰 Всего: ${total_liquidations:,.0f}\n"
                            f"📉 Long: ${long_liquidations:,.0f}\n"
                            f"📈 Short: ${short_liquidations:,.0f}\n"
                            f"🎯 Направление: *{direction}*\n\n"
                            f"⚠️ Возможен сильный импульс!"
                        )
                    )

                    self._record_alert(symbol, "liquidations")

        except Exception as e:
            logger.error(f"❌ Ошибка _check_large_liquidations: {e}")


    async def _check_order_imbalance(self, symbol: str, market_data: Dict):
        """Проверка дисбаланса стакана"""
        try:
            orderbook = market_data.get("orderbook", {})

            bid_volume = orderbook.get("bid_volume", 0)
            ask_volume = orderbook.get("ask_volume", 0)
            total_volume = bid_volume + ask_volume

            if total_volume == 0:
                return

            bid_ratio = bid_volume / total_volume
            ask_ratio = ask_volume / total_volume

            # Сильный дисбаланс в покупки
            if bid_ratio >= self.imbalance_threshold:
                if self._should_send_alert(symbol, "imbalance_buy"):
                    await self._send_alert(
                        alert_type="imbalance",
                        symbol=symbol,
                        message=(
                            f"🟢 *ДИСБАЛАНС В ПОКУПКИ {symbol}*\n\n"
                            f"📊 Bid: {bid_ratio*100:.1f}%\n"
                            f"📊 Ask: {ask_ratio*100:.1f}%\n\n"
                            f"💡 Сильное давление покупателей!\n"
                            f"⚡ Возможен рост цены"
                        )
                    )

                    self._record_alert(symbol, "imbalance_buy")

            # Сильный дисбаланс в продажи
            elif ask_ratio >= self.imbalance_threshold:
                if self._should_send_alert(symbol, "imbalance_sell"):
                    await self._send_alert(
                        alert_type="imbalance",
                        symbol=symbol,
                        message=(
                            f"🔴 *ДИСБАЛАНС В ПРОДАЖИ {symbol}*\n\n"
                            f"📊 Bid: {bid_ratio*100:.1f}%\n"
                            f"📊 Ask: {ask_ratio*100:.1f}%\n\n"
                            f"💡 Сильное давление продавцов!\n"
                            f"⚡ Возможно падение цены"
                        )
                    )

                    self._record_alert(symbol, "imbalance_sell")

        except Exception as e:
            logger.error(f"❌ Ошибка _check_order_imbalance: {e}")


    def _should_send_alert(self, symbol: str, alert_type: str) -> bool:
        """Проверка cooldown для алерта"""
        key = f"{symbol}:{alert_type}"

        if key not in self.recent_alerts:
            return True

        last_alert_time = self.recent_alerts[key]
        time_passed = (datetime.now() - last_alert_time).total_seconds()

        return time_passed >= self.alert_cooldown


    def _record_alert(self, symbol: str, alert_type: str):
        """Запись времени последнего алерта"""
        key = f"{symbol}:{alert_type}"
        self.recent_alerts[key] = datetime.now()


    async def _send_alert(self, alert_type: str, symbol: str, message: str):
        """Отправка алерта в Telegram с АНТИСПАМ защитой"""
        try:
            # Проверка глобального лимита
            now = time.time()
            hour_ago = now - 3600

            # Удаляем старые записи
            self.alert_history = [
                (ts, atype, sym) for ts, atype, sym in self.alert_history
                if ts > hour_ago
            ]

            # Проверяем лимит
            if len(self.alert_history) >= self.max_alerts_per_hour:
                logger.warning(f"⚠️ Достигнут лимит алертов: {self.max_alerts_per_hour}/час")
                return

            # Отправляем
            if self.bot.telegram_handler:
                await self.bot.telegram_handler.application.bot.send_message(
                    chat_id=self.bot.telegram_handler.chat_id,
                    text=message,
                    parse_mode='Markdown'
                )

                # Регистрируем отправку
                self.alert_history.append((now, alert_type, symbol))

                logger.info(f"✅ Алерт отправлен: {alert_type} для {symbol}")
            else:
                logger.warning("⚠️ telegram_handler не найден")

        except Exception as e:
            logger.error(f"❌ Ошибка отправки алерта: {e}")
