# -*- coding: utf-8 -*-
"""
Google Gemini 2.0 Flash AI Interpreter
100% БЕСПЛАТНО — 60 RPM (86,400 запросов/день)
"""

import aiohttp
import json
from typing import Dict, Optional
from config.settings import logger


class GeminiInterpreter:
    """AI интерпретатор на базе Google Gemini 2.0 Flash"""

    def __init__(self, api_key: str):
        print("🔄 GeminiInterpreter.__init__ ВЫЗВАН")
        print(f"🔑 API key length: {len(api_key)}")

        self.api_key = api_key
        self.base_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash-exp:generateContent"
        self.session = None
        self.request_count = 0

        print("✅ GeminiInterpreter инициализирован (Gemini 2.0 Flash)")
        logger.info("✅ GeminiInterpreter инициализирован (Gemini 2.0 Flash)")

    # ✅ ДОБАВЛЕНО: Context manager support
    async def __aenter__(self):
        """Context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - автоматически закрывает сессию"""
        await self.close()

    async def get_session(self):
        """Получение HTTP сессии"""
        if not self.session or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session

    async def interpret_metrics(self, metrics: Dict) -> Optional[str]:
        """
        Интерпретация метрик через Gemini 2.0 Flash

        Args:
            metrics: Словарь с метриками (scenario, cvd, funding_rate, oi, ls_ratio, etc)

        Returns:
            Интерпретация (2-3 строки) или fallback при ошибке
        """
        try:
            if not self.api_key:
                logger.warning("⚠️ Gemini API key не найден, возврат fallback")
                return self._get_fallback_interpretation(metrics)

            # Создаём prompt
            prompt = self._create_prompt(metrics)

            # Подготавливаем запрос
            session = await self.get_session()
            url = f"{self.base_url}?key={self.api_key}"

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,  # Меньше креатива, больше точности
                    "maxOutputTokens": 150,  # Ограничение для краткости
                    "topK": 40,
                    "topP": 0.95,
                },
            }

            # Выполняем запрос
            async with session.post(url, json=payload, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()

                    # Извлекаем текст из ответа
                    if "candidates" in data and len(data["candidates"]) > 0:
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        interpretation = text.strip()

                        self.request_count += 1
                        logger.debug(
                            f"✅ Gemini интерпретация получена ({len(interpretation)} символов, запрос #{self.request_count})"
                        )

                        return interpretation
                    else:
                        logger.warning("⚠️ Gemini: пустой ответ, возврат fallback")
                        return self._get_fallback_interpretation(metrics)

                elif response.status == 429:
                    logger.warning(
                        "⚠️ Gemini API: Rate limit exceeded (60 RPM), возврат fallback"
                    )
                    return self._get_fallback_interpretation(metrics)

                else:
                    error_text = await response.text()
                    logger.error(
                        f"❌ Gemini API error {response.status}: {error_text}, возврат fallback"
                    )
                    return self._get_fallback_interpretation(metrics)

        except aiohttp.ClientError as e:
            logger.error(f"❌ Gemini connection error: {e}, возврат fallback")
            return self._get_fallback_interpretation(metrics)

        except Exception as e:
            logger.error(f"❌ Gemini interpretation error: {e}, возврат fallback")
            return self._get_fallback_interpretation(metrics)

    async def interpret_text(self, prompt: str) -> Optional[str]:
        """
        Интерпретация текстового prompt через Gemini 2.0 Flash

        Args:
            prompt: Текстовый prompt для AI

        Returns:
            Ответ AI (строка) или None при ошибке
        """
        try:
            if not self.api_key:
                logger.warning("⚠️ Gemini API key не найден")
                return None

            # Подготавливаем запрос
            session = await self.get_session()
            url = f"{self.base_url}?key={self.api_key}"

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.3,
                    "maxOutputTokens": 50,  # Короткий ответ для sentiment
                    "topK": 40,
                    "topP": 0.95,
                },
            }

            # Выполняем запрос
            async with session.post(url, json=payload, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()

                    # Извлекаем текст из ответа
                    if "candidates" in data and len(data["candidates"]) > 0:
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        result = text.strip()

                        self.request_count += 1
                        logger.debug(
                            f"✅ Gemini sentiment получен ({len(result)} символов, запрос #{self.request_count})"
                        )

                        return result
                    else:
                        logger.warning("⚠️ Gemini: пустой ответ")
                        return None

                elif response.status == 429:
                    logger.warning("⚠️ Gemini API: Rate limit exceeded (60 RPM)")
                    return None

                else:
                    error_text = await response.text()
                    logger.error(f"❌ Gemini API error {response.status}: {error_text}")
                    return None

        except Exception as e:
            logger.error(f"❌ Gemini sentiment error: {e}")
            return None

    async def analyze_text(self, prompt: str) -> str:
        """
        Анализ текста через Gemini 2.0 Flash
        Используется для /news AI интерпретации

        Args:
            prompt: Текстовый prompt для анализа

        Returns:
            str: Ответ от Gemini AI
        """
        try:
            if not self.api_key:
                logger.warning("⚠️ Gemini API key не найден")
                return ""

            # Подготавливаем запрос
            session = await self.get_session()
            url = f"{self.base_url}?key={self.api_key}"

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 500,  # Больше токенов для детального анализа новостей
                    "topK": 40,
                    "topP": 0.95,
                },
            }

            # Выполняем запрос
            async with session.post(url, json=payload, timeout=20) as response:
                if response.status == 200:
                    data = await response.json()

                    # Извлекаем текст из ответа
                    if "candidates" in data and len(data["candidates"]) > 0:
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
                        result = text.strip()

                        self.request_count += 1
                        logger.debug(
                            f"✅ Gemini analyze_text получен ({len(result)} символов, запрос #{self.request_count})"
                        )

                        return result
                    else:
                        logger.warning("⚠️ Gemini analyze_text: пустой ответ")
                        return ""

                elif response.status == 429:
                    logger.warning("⚠️ Gemini API: Rate limit exceeded (60 RPM)")
                    return ""

                else:
                    error_text = await response.text()
                    logger.error(f"❌ Gemini API error {response.status}: {error_text}")
                    return ""

        except Exception as e:
            logger.error(f"❌ Gemini analyze_text error: {e}")
            return ""


    def _create_prompt(self, metrics: Dict) -> str:
        """Создание prompt для Gemini"""
        scenario = metrics.get("scenario", "UNKNOWN")
        symbol = metrics.get("symbol", "UNKNOWN")
        cvd = metrics.get("cvd", 0)
        funding_rate = metrics.get("funding_rate", 0)
        oi = metrics.get("open_interest", 0)
        ls_ratio = metrics.get("ls_ratio", 1.0)
        orderbook_pressure = metrics.get("orderbook_pressure", 0)
        whale_count = len(metrics.get("whale_activity", []))

        prompt = f"""Ты опытный криптотрейдер. Проанализируй метрики для {symbol} и дай краткую интерпретацию (2-3 строки) с эмодзи.

🚀 MM СЦЕНАРИЙ: {scenario}

📊 МЕТРИКИ:
• CVD (Cumulative Volume Delta): {cvd:+.2f}%
• Funding Rate: {funding_rate:+.4f}%
• Open Interest: ${oi/1e9:.2f}B
• Long/Short Ratio: {ls_ratio:.2f}
• Orderbook Pressure: {orderbook_pressure:+.1f}% {'📈 BUY' if orderbook_pressure > 0 else '📉 SELL'}
• Whale Activity: {whale_count} крупных сделок за 15 минут

ИНТЕРПРЕТАЦИЯ (2-3 строки):
Что происходит на рынке и что это значит для трейдера? Используй эмодзи для наглядности."""

        return prompt

    def _get_fallback_interpretation(self, metrics: Dict) -> str:
        """
        Дефолтная интерпретация, если Gemini недоступен
        """
        scenario = metrics.get("scenario", "UNKNOWN")
        cvd = metrics.get("cvd", 0)
        funding = metrics.get("funding_rate", 0)
        ls_ratio = metrics.get("ls_ratio", 1.0)
        oi = metrics.get("open_interest", 0)

        # ✅ АНАЛИЗ CVD
        if abs(cvd) > 50:
            cvd_text = f"🔥 Сильная активность {'покупателей' if cvd > 0 else 'продавцов'} (CVD {cvd:+.1f}%)."
        elif cvd > 0:
            cvd_text = f"🟢 Умеренная активность покупателей (CVD {cvd:+.1f}%)."
        elif cvd < 0:
            cvd_text = f"🔴 Умеренная активность продавцов (CVD {cvd:+.1f}%)."
        else:
            cvd_text = f"⚪ Нейтральная активность (CVD {cvd:+.1f}%)."

        # ✅ АНАЛИЗ FUNDING
        funding_pct = funding * 100
        if abs(funding_pct) < 0.01:
            funding_text = (
                f"⚪ Нейтральный Funding ({funding_pct:+.2f}%) — рынок сбалансирован."
            )
        elif funding_pct > 0:
            funding_text = (
                f"🟢 Позитивный Funding ({funding_pct:+.2f}%) — преобладают лонги."
            )
        else:
            funding_text = (
                f"🔴 Негативный Funding ({funding_pct:+.2f}%) — преобладают шорты."
            )

        # ✅ АНАЛИЗ L/S RATIO
        if ls_ratio > 1.2:
            ls_text = f"📊 L/S Ratio {ls_ratio:.1f} — преобладают лонги."
        elif ls_ratio < 0.8:
            ls_text = f"📊 L/S Ratio {ls_ratio:.1f} — преобладают шорты."
        else:
            ls_text = f"📊 L/S Ratio {ls_ratio:.1f} — паритет сил."

        # ✅ РЕКОМЕНДАЦИЯ ПО СЦЕНАРИЮ
        if scenario == "Impulse":
            if cvd > 0:
                recommendation = (
                    "💡 РЕКОМЕНДАЦИЯ: 🚀 Следуй тренду вверх, цели — новые хаи."
                )
            else:
                recommendation = (
                    "💡 РЕКОМЕНДАЦИЯ: ⏸️ Ожидание подтверждения перед открытием позиций."
                )

        elif scenario == "Accumulation":
            recommendation = (
                "💡 РЕКОМЕНДАЦИЯ: 📈 Готовься к импульсу вверх после накопления."
            )

        elif scenario == "Distribution":
            recommendation = (
                "💡 РЕКОМЕНДАЦИЯ: 🔻 Избегай лонгов, крупные игроки выходят."
            )

        elif scenario == "Manipulation":
            recommendation = "💡 РЕКОМЕНДАЦИЯ: ⚠️ Fake-out возможен, жди подтверждения."

        elif scenario == "Equilibrium":
            recommendation = (
                "💡 РЕКОМЕНДАЦИЯ: ⏸️ Ожидание подтверждения перед открытием позиций."
            )

        else:
            recommendation = (
                "💡 РЕКОМЕНДАЦИЯ: ⏸️ Ожидание подтверждения перед открытием позиций."
            )

        # ✅ ФОРМИРУЕМ ИТОГОВОЕ СООБЩЕНИЕ
        return f"{cvd_text} {funding_text} {ls_text}   {recommendation}"

    async def close(self):
        """Закрытие сессии"""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info(
                f"🌐 Gemini session closed (всего запросов: {self.request_count})"
            )


# Экспорт
__all__ = ["GeminiInterpreter"]
