# Используем официальный python 3.12 slim образ
FROM python:3.12-slim

# Обновляем пакеты и устанавливаем libsqlite3
RUN apt-get update && apt-get install -y libsqlite3-0

# Устанавливаем рабочую директорию в контейнере
WORKDIR /app

# Копируем файл зависимостей
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код приложения
COPY . .

# Запускаем приложение
CMD ["python", "main.py"]
