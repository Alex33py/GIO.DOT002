# -*- coding: utf-8 -*-
"""
Продвинутая оптимизация производительности для больших объёмов данных
Поддержка 100k+ свечей, батчинг, кэширование
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Optional, Callable, Any
from functools import lru_cache
import hashlib
import pickle
from pathlib import Path
from config.settings import logger, DATA_DIR


class AdvancedPerformanceOptimizer:
    """Продвинутый оптимизатор производительности"""

    def __init__(self, cache_dir: Optional[Path] = None):
        self.cache_dir = cache_dir or Path(DATA_DIR) / "cache" / "performance"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # Статистика
        self.stats = {
            'cache_hits': 0,
            'cache_misses': 0,
            'batches_processed': 0,
            'items_processed': 0
        }

        logger.info(f"✅ AdvancedPerformanceOptimizer инициализирован (cache: {self.cache_dir})")

    def batch_process_candles(self,
                              candles: List[Dict],
                              batch_size: int = 10000,
                              processor_func: Callable = None) -> List[Any]:
        """
        Батч-обработка свечей для больших объёмов (100k+)

        Args:
            candles: Список свечей
            batch_size: Размер батча (по умолчанию 10k)
            processor_func: Функция обработки батча

        Returns:
            Список результатов обработки
        """
        try:
            if not candles:
                return []

            total_candles = len(candles)

            if total_candles <= batch_size:
                # Если свечей мало - обрабатываем сразу
                logger.debug(f"📊 Обработка {total_candles} свечей (без батчинга)")
                return [processor_func(candles)] if processor_func else [candles]

            # Батч-обработка
            logger.info(f"📊 Батч-обработка {total_candles} свечей (батч: {batch_size})")

            results = []
            num_batches = (total_candles + batch_size - 1) // batch_size

            for i in range(0, total_candles, batch_size):
                batch = candles[i:i + batch_size]
                batch_num = i // batch_size + 1

                logger.debug(f"  Батч {batch_num}/{num_batches}: {len(batch)} свечей")

                if processor_func:
                    result = processor_func(batch)
                    results.append(result)
                else:
                    results.append(batch)

                self.stats['batches_processed'] += 1
                self.stats['items_processed'] += len(batch)

            logger.info(f"✅ Обработано {num_batches} батчей ({total_candles} свечей)")

            return results

        except Exception as e:
            logger.error(f"❌ Ошибка батч-обработки: {e}")
            return []

    def compute_indicators_chunked(self,
                                   df: pd.DataFrame,
                                   chunk_size: int = 50000) -> pd.DataFrame:
        """
        Вычисление индикаторов по частям для больших датафреймов

        Args:
            df: DataFrame со свечами
            chunk_size: Размер чанка

        Returns:
            DataFrame с индикаторами
        """
        try:
            if len(df) <= chunk_size:
                # Маленький датафрейм - считаем сразу
                return self._compute_indicators(df)

            logger.info(f"📊 Chunked расчёт индикаторов для {len(df)} строк (chunk: {chunk_size})")

            # Разбиваем на чанки с перекрытием (для корректного расчёта индикаторов)
            overlap = 200  # Перекрытие для корректного расчёта MA, RSI, etc
            chunks = []

            for start in range(0, len(df), chunk_size):
                end = min(start + chunk_size + overlap, len(df))
                chunk_df = df.iloc[start:end].copy()

                # Вычисляем индикаторы для чанка
                chunk_with_indicators = self._compute_indicators(chunk_df)

                # Убираем перекрытие (кроме последнего чанка)
                if end < len(df):
                    chunk_with_indicators = chunk_with_indicators.iloc[:-overlap]

                chunks.append(chunk_with_indicators)

            # Объединяем чанки
            result = pd.concat(chunks, ignore_index=True)

            logger.info(f"✅ Chunked расчёт завершён: {len(result)} строк")

            return result

        except Exception as e:
            logger.error(f"❌ Ошибка chunked расчёта: {e}")
            return df

    def _compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Вычисление индикаторов для датафрейма
        (это заглушка - заменить на реальные вычисления)
        """
        try:
            # RSI
            if 'close' in df.columns:
                delta = df['close'].diff()
                gain = delta.where(delta > 0, 0.0)
                loss = -delta.where(delta < 0, 0.0)

                avg_gain = gain.rolling(window=14).mean()
                avg_loss = loss.rolling(window=14).mean()

                rs = avg_gain / avg_loss
                df['rsi'] = 100 - (100 / (1 + rs))

            # EMA
            if 'close' in df.columns:
                df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
                df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()

            return df

        except Exception as e:
            logger.error(f"❌ Ошибка вычисления индикаторов: {e}")
            return df

    def cache_result(self, key: str, data: Any, ttl_seconds: int = 3600) -> None:
        """
        Кэширование результата на диск

        Args:
            key: Ключ кэша
            data: Данные для кэширования
            ttl_seconds: Time-to-live в секундах
        """
        try:
            # Генерируем хэш ключа
            key_hash = hashlib.md5(key.encode()).hexdigest()
            cache_file = self.cache_dir / f"{key_hash}.pkl"

            # Сохраняем с metadata
            cache_data = {
                'data': data,
                'timestamp': pd.Timestamp.now().timestamp(),
                'ttl': ttl_seconds,
                'key': key
            }

            with open(cache_file, 'wb') as f:
                pickle.dump(cache_data, f)

            logger.debug(f"💾 Результат закэширован: {key[:50]}...")

        except Exception as e:
            logger.error(f"❌ Ошибка кэширования: {e}")

    def get_cached_result(self, key: str) -> Optional[Any]:
        """
        Получение результата из кэша

        Args:
            key: Ключ кэша

        Returns:
            Данные из кэша или None
        """
        try:
            key_hash = hashlib.md5(key.encode()).hexdigest()
            cache_file = self.cache_dir / f"{key_hash}.pkl"

            if not cache_file.exists():
                self.stats['cache_misses'] += 1
                return None

            # Читаем кэш
            with open(cache_file, 'rb') as f:
                cache_data = pickle.load(f)

            # Проверяем TTL
            age = pd.Timestamp.now().timestamp() - cache_data['timestamp']
            if age > cache_data['ttl']:
                logger.debug(f"⏰ Кэш устарел: {key[:50]}... (age: {age:.0f}s)")
                cache_file.unlink()
                self.stats['cache_misses'] += 1
                return None

            logger.debug(f"✅ Кэш найден: {key[:50]}... (age: {age:.0f}s)")
            self.stats['cache_hits'] += 1

            return cache_data['data']

        except Exception as e:
            logger.error(f"❌ Ошибка чтения кэша: {e}")
            self.stats['cache_misses'] += 1
            return None

    def optimize_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Оптимизация памяти датафрейма (downcast типов)

        Args:
            df: DataFrame для оптимизации

        Returns:
            Оптимизированный DataFrame
        """
        try:
            initial_memory = df.memory_usage(deep=True).sum() / 1024**2

            # Оптимизация числовых столбцов
            for col in df.select_dtypes(include=['float64']).columns:
                df[col] = pd.to_numeric(df[col], downcast='float')

            for col in df.select_dtypes(include=['int64']).columns:
                df[col] = pd.to_numeric(df[col], downcast='integer')

            final_memory = df.memory_usage(deep=True).sum() / 1024**2
            saved = initial_memory - final_memory

            if saved > 0:
                logger.info(
                    f"📉 DataFrame оптимизирован: {initial_memory:.2f} MB → {final_memory:.2f} MB "
                    f"(сэкономлено: {saved:.2f} MB)"
                )

            return df

        except Exception as e:
            logger.error(f"❌ Ошибка оптимизации DataFrame: {e}")
            return df

    def clear_cache(self, older_than_seconds: Optional[int] = None) -> int:
        """
        Очистка кэша

        Args:
            older_than_seconds: Удалить файлы старше N секунд (None = все)

        Returns:
            Количество удалённых файлов
        """
        try:
            deleted = 0
            now = pd.Timestamp.now().timestamp()

            for cache_file in self.cache_dir.glob("*.pkl"):
                try:
                    if older_than_seconds is None:
                        cache_file.unlink()
                        deleted += 1
                    else:
                        # Проверяем возраст файла
                        with open(cache_file, 'rb') as f:
                            cache_data = pickle.load(f)

                        age = now - cache_data['timestamp']
                        if age > older_than_seconds:
                            cache_file.unlink()
                            deleted += 1

                except Exception:
                    # Если файл повреждён - удаляем
                    cache_file.unlink()
                    deleted += 1

            if deleted > 0:
                logger.info(f"🗑️ Очищено {deleted} файлов кэша")

            return deleted

        except Exception as e:
            logger.error(f"❌ Ошибка очистки кэша: {e}")
            return 0

    def get_stats(self) -> Dict:
        """
        Получить статистику работы оптимизатора

        Returns:
            Словарь со статистикой
        """
        total_requests = self.stats['cache_hits'] + self.stats['cache_misses']
        hit_rate = (self.stats['cache_hits'] / total_requests * 100) if total_requests > 0 else 0.0

        return {
            **self.stats,
            'cache_hit_rate': hit_rate,
            'total_cache_requests': total_requests
        }

    def get_ai_interpretation(self) -> str:
        """
        AI интерпретация статистики оптимизатора

        Returns:
            Строка с AI интерпретацией
        """
        try:
            stats = self.get_stats()
            interpretation = []

            # 1. Cache Hit Rate
            hit_rate = stats.get('cache_hit_rate', 0)

            if hit_rate > 70:
                interpretation.append(f"✅ **Кэш работает отлично!** Hit rate {hit_rate:.1f}% — большинство данных берётся из кэша.")
            elif hit_rate > 40:
                interpretation.append(f"📊 **Кэш работает нормально**. Hit rate {hit_rate:.1f}% — можно улучшить.")
            elif hit_rate > 0:
                interpretation.append(f"⚠️ **Кэш работает слабо**. Hit rate {hit_rate:.1f}% — много запросов пропускают кэш.")
            else:
                interpretation.append("❌ **Кэш не используется** — все данные загружаются заново.")

            # 2. Батч-обработка
            batches = stats.get('batches_processed', 0)
            items = stats.get('items_processed', 0)

            if batches > 0:
                avg_batch_size = items / batches
                interpretation.append(f"📦 **Обработано {batches} батчей** ({items:,} элементов, среднее {avg_batch_size:.1f} элементов/батч).")
            else:
                interpretation.append("📊 **Батч-обработка не использовалась** — все данные обрабатываются целиком.")

            # 3. Кэш статистика
            hits = stats.get('cache_hits', 0)
            misses = stats.get('cache_misses', 0)

            if hits + misses > 0:
                interpretation.append(f"💾 **Кэш статистика:** {hits} попаданий, {misses} промахов.")

            # 4. Рекомендация
            if hit_rate < 50 and batches > 10:
                interpretation.append("\n💡 **РЕКОМЕНДАЦИЯ:** Увеличь TTL кэша (время хранения) для лучшей эффективности.")
            elif hit_rate > 70:
                interpretation.append("\n💡 **РЕКОМЕНДАЦИЯ:** Кэш работает отлично, продолжай в том же духе!")
            elif batches == 0 and items == 0:
                interpretation.append("\n💡 **РЕКОМЕНДАЦИЯ:** Оптимизатор пока не использовался — начни обрабатывать большие датасеты для получения статистики.")
            else:
                interpretation.append("\n💡 **РЕКОМЕНДАЦИЯ:** Оптимизация работает нормально. Следи за hit rate кэша.")

            return " ".join(interpretation)

        except Exception as e:
            logger.error(f"❌ Ошибка AI интерпретации оптимизатора: {e}")
            return "⚠️ Ошибка генерации AI интерпретации."

# Экспорт
__all__ = ['AdvancedPerformanceOptimizer']
