# -*- coding: utf-8 -*-
"""
Модуль расчёта Take Profit и Stop Loss с динамическим управлением риском
Поддерживает расчёт RR (Risk/Reward) и адаптивные уровни на основе ATR
"""

from typing import Dict, Tuple, Optional
from dataclasses import dataclass

from config.settings import logger
from utils.helpers import safe_float


@dataclass
class RiskLevels:
    """Уровни риска для позиции"""
    entry_price: float
    stop_loss: float
    take_profit_1: float
    take_profit_2: float
    take_profit_3: float
    risk_reward_1: float
    risk_reward_2: float
    risk_reward_3: float
    stop_loss_percent: float
    trailing_stop: bool
    position_size_percent: float  # % от депозита


class DynamicRiskCalculator:
    """Динамический расчёт TP/SL на основе ATR и рыночных условий"""

    def __init__(
        self,
        min_rr: float = 1.5,
        default_sl_atr_multiplier: float = 1.5,
        default_tp1_percent: float = 1.5,
        use_trailing_stop: bool = True
    ):
        """
        Инициализация калькулятора

        Параметры:
            min_rr: Минимальный Risk/Reward для входа
            default_sl_atr_multiplier: Множитель ATR для SL (1.5 = 1.5 * ATR)
            default_tp1_percent: Процент для TP1 если нет POC
            use_trailing_stop: Использовать трейлинг-стоп для TP3
        """
        self.min_rr = min_rr
        self.default_sl_atr_multiplier = default_sl_atr_multiplier
        self.default_tp1_percent = default_tp1_percent
        self.use_trailing_stop = use_trailing_stop

        logger.info(
            f"✅ DynamicRiskCalculator инициализирован "
            f"(min_rr: {min_rr}, sl_atr: {default_sl_atr_multiplier})"
        )

    def calculate_risk_levels(
        self,
        entry_price: float,
        side: str,
        atr_value: float,
        market_data: Dict,
        scenario_config: Optional[Dict] = None
    ) -> Optional[RiskLevels]:
        """
        Расчёт всех уровней риска (SL, TP1, TP2, TP3)

        Параметры:
            entry_price: Цена входа
            side: Направление "LONG" или "SHORT"
            atr_value: Значение ATR
            market_data: Рыночные данные (volume_profile, swings)
            scenario_config: Конфигурация сценария (опционально)

        Возвращает:
            RiskLevels или None если RR < min_rr
        """
        try:
            if entry_price <= 0 or atr_value <= 0:
                logger.warning("⚠️ Некорректные входные данные для расчёта риска")
                return None

            # Расчёт Stop Loss
            stop_loss = self._calculate_stop_loss(
                entry_price, side, atr_value, market_data, scenario_config
            )

            # Расчёт Take Profit уровней
            tp1 = self._calculate_tp1(
                entry_price, side, atr_value, market_data, scenario_config
            )

            tp2 = self._calculate_tp2(
                entry_price, side, atr_value, market_data, scenario_config
            )

            tp3 = self._calculate_tp3(
                entry_price, side, atr_value, market_data, scenario_config
            )

            # Расчёт Risk/Reward для каждого уровня
            if side == "LONG":
                risk = entry_price - stop_loss
                rr1 = (tp1 - entry_price) / risk if risk > 0 else 0
                rr2 = (tp2 - entry_price) / risk if risk > 0 else 0
                rr3 = (tp3 - entry_price) / risk if risk > 0 else 0
                sl_percent = (stop_loss / entry_price - 1) * 100
            else:  # SHORT
                risk = stop_loss - entry_price
                rr1 = (entry_price - tp1) / risk if risk > 0 else 0
                rr2 = (entry_price - tp2) / risk if risk > 0 else 0
                rr3 = (entry_price - tp3) / risk if risk > 0 else 0
                sl_percent = (1 - stop_loss / entry_price) * 100

            # Проверка минимального RR
            if rr1 < self.min_rr:
                logger.warning(
                    f"⚠️ RR1 ({rr1:.2f}) < минимального ({self.min_rr}), сигнал отклонён"
                )
                return None

            # Расчёт размера позиции (2% риска от депозита)
            position_size_percent = self._calculate_position_size(
                abs(sl_percent), scenario_config
            )

            risk_levels = RiskLevels(
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit_1=tp1,
                take_profit_2=tp2,
                take_profit_3=tp3,
                risk_reward_1=rr1,
                risk_reward_2=rr2,
                risk_reward_3=rr3,
                stop_loss_percent=abs(sl_percent),
                trailing_stop=self.use_trailing_stop,
                position_size_percent=position_size_percent
            )

            logger.info(
                f"✅ Уровни риска: SL={stop_loss:.2f} ({sl_percent:.2f}%), "
                f"TP1={tp1:.2f} (RR:{rr1:.2f}), "
                f"TP2={tp2:.2f} (RR:{rr2:.2f}), "
                f"TP3={tp3:.2f} (RR:{rr3:.2f})"
            )

            return risk_levels

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта risk levels: {e}")
            return None

    def _calculate_stop_loss(
        self,
        entry_price: float,
        side: str,
        atr_value: float,
        market_data: Dict,
        scenario_config: Optional[Dict]
    ) -> float:
        """
        Расчёт Stop Loss на основе ATR и swing levels

        Логика:
        - Базовый SL = entry ± (ATR * multiplier)
        - Корректируется по ближайшему swing level
        - Ограничен диапазоном 1-2.5%
        """
        try:
            # Получаем множитель из конфигурации или используем дефолтный
            multiplier = self.default_sl_atr_multiplier
            if scenario_config:
                multiplier = scenario_config.get('sl_atr_multiplier', multiplier)

            # Базовый расчёт по ATR
            atr_distance = atr_value * multiplier

            if side == "LONG":
                base_sl = entry_price - atr_distance
            else:  # SHORT
                base_sl = entry_price + atr_distance

            # Корректировка по swing levels
            swings = market_data.get('swing_levels', {})
            if swings:
                if side == "LONG":
                    # Ищем ближайший swing low ниже entry
                    swing_low = swings.get('recent_low', base_sl)
                    if swing_low < entry_price:
                        # Ставим SL немного ниже swing low
                        base_sl = max(base_sl, swing_low * 0.998)
                else:  # SHORT
                    swing_high = swings.get('recent_high', base_sl)
                    if swing_high > entry_price:
                        base_sl = min(base_sl, swing_high * 1.002)

            # Ограничение диапазона 1-2.5%
            if side == "LONG":
                min_sl = entry_price * 0.99  # 1%
                max_sl = entry_price * 0.975  # 2.5%
                stop_loss = max(min_sl, min(max_sl, base_sl))
            else:  # SHORT
                min_sl = entry_price * 1.01  # 1%
                max_sl = entry_price * 1.025  # 2.5%
                stop_loss = min(min_sl, max(max_sl, base_sl))

            return round(stop_loss, 2)

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта stop loss: {e}")
            # Fallback: 1.5% от entry
            return entry_price * 0.985 if side == "LONG" else entry_price * 1.015

    def _calculate_tp1(
        self,
        entry_price: float,
        side: str,
        atr_value: float,
        market_data: Dict,
        scenario_config: Optional[Dict]
    ) -> float:
        """
        Расчёт TP1 на основе POC или фиксированного процента

        Логика:
        - Если POC в зоне 1-2%, используем его
        - Иначе 1.5% от entry
        """
        try:
            volume_profile = market_data.get('volume_profile', {})
            poc_price = safe_float(volume_profile.get('poc_price', 0))

            # Проверяем расстояние до POC
            if poc_price > 0:
                distance_percent = abs(poc_price - entry_price) / entry_price * 100

                # Если POC в зоне 1-2%, используем его
                if 1.0 <= distance_percent <= 2.0:
                    if (side == "LONG" and poc_price > entry_price) or \
                       (side == "SHORT" and poc_price < entry_price):
                        return round(poc_price, 2)

            # Иначе используем фиксированный процент
            tp_percent = self.default_tp1_percent
            if scenario_config:
                tp_percent = scenario_config.get('tp1_percent', tp_percent)

            if side == "LONG":
                tp1 = entry_price * (1 + tp_percent / 100)
            else:  # SHORT
                tp1 = entry_price * (1 - tp_percent / 100)

            return round(tp1, 2)

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта TP1: {e}")
            return entry_price * 1.015 if side == "LONG" else entry_price * 0.985

    def _calculate_tp2(
        self,
        entry_price: float,
        side: str,
        atr_value: float,
        market_data: Dict,
        scenario_config: Optional[Dict]
    ) -> float:
        """
        Расчёт TP2 на основе VAH/VAL или RR > 2.0

        Логика:
        - Если VAH/VAL в зоне 2-4%, используем его
        - Иначе TP2 для RR = 2.5
        """
        try:
            volume_profile = market_data.get('volume_profile', {})

            if side == "LONG":
                target = safe_float(volume_profile.get('value_area_high', 0))
            else:  # SHORT
                target = safe_float(volume_profile.get('value_area_low', 0))

            # Проверяем расстояние до VAH/VAL
            if target > 0:
                distance_percent = abs(target - entry_price) / entry_price * 100

                if 2.0 <= distance_percent <= 4.0:
                    if (side == "LONG" and target > entry_price) or \
                       (side == "SHORT" and target < entry_price):
                        return round(target, 2)

            # Иначе расчёт для RR = 2.5
            # Предполагаем SL ~1.5%, значит TP2 ~3.75% для RR 2.5
            if side == "LONG":
                tp2 = entry_price * 1.0375
            else:  # SHORT
                tp2 = entry_price * 0.9625

            return round(tp2, 2)

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта TP2: {e}")
            return entry_price * 1.03 if side == "LONG" else entry_price * 0.97

    def _calculate_tp3(
        self,
        entry_price: float,
        side: str,
        atr_value: float,
        market_data: Dict,
        scenario_config: Optional[Dict]
    ) -> float:
        """
        Расчёт TP3 с трейлинг-стопом по ATR

        Логика:
        - TP3 = TP2 + (ATR * 2)
        - Или 5-7% от entry
        """
        try:
            # Расчёт на основе ATR
            atr_extension = atr_value * 2

            if side == "LONG":
                tp3 = entry_price * 1.0375 + atr_extension  # TP2 + расширение
                # Ограничение 5-7%
                tp3 = min(tp3, entry_price * 1.07)
                tp3 = max(tp3, entry_price * 1.05)
            else:  # SHORT
                tp3 = entry_price * 0.9625 - atr_extension
                tp3 = max(tp3, entry_price * 0.93)
                tp3 = min(tp3, entry_price * 0.95)

            return round(tp3, 2)

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта TP3: {e}")
            return entry_price * 1.06 if side == "LONG" else entry_price * 0.94

    def _calculate_position_size(
        self,
        sl_percent: float,
        scenario_config: Optional[Dict]
    ) -> float:
        """
        Расчёт размера позиции на основе риска

        Логика: Риск 2% от депозита
        Например: если SL = 1.5%, то позиция = 2% / 1.5% * 100% = 133% депозита (с плечом)
        Без плеча: ограничено 100%
        """
        try:
            risk_percent = 2.0  # Риск 2% от депозита
            if scenario_config:
                risk_percent = scenario_config.get('risk_percent', risk_percent)

            # Расчёт размера позиции
            position_size = (risk_percent / sl_percent) * 100

            # Ограничение 100% (без плеча)
            position_size = min(position_size, 100.0)

            return round(position_size, 2)

        except Exception as e:
            logger.error(f"❌ Ошибка расчёта position size: {e}")
            return 10.0  # Дефолт 10% депозита


# Экспорт
__all__ = ['DynamicRiskCalculator', 'RiskLevels']
