#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Batch processor для обработки больших объёмов данных
"""

import asyncio
from typing import List, Callable, Any


class BatchProcessor:
    """Обработка данных батчами"""

    def __init__(self, batch_size: int = 100):
        self.batch_size = batch_size

    async def process_in_batches(
        self,
        items: List[Any],
        process_func: Callable,
        max_concurrent: int = 5
    ):
        """
        Обработка items батчами

        Args:
            items: Список элементов для обработки
            process_func: Async функция обработки
            max_concurrent: Максимум одновременных задач
        """
        results = []

        # Разбиваем на батчи
        for i in range(0, len(items), self.batch_size):
            batch = items[i:i + self.batch_size]

            # Обрабатываем батч параллельно
            tasks = [process_func(item) for item in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            results.extend(batch_results)

            # Небольшая пауза между батчами
            await asyncio.sleep(0.1)

        return results
