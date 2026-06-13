# Образ приложения Blinds Tracker
FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей (отдельный слой для кэширования)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копирование исходного кода приложения
COPY app/ ./app/

# Создание администратора и тестовых менеджеров
RUN python -m app.create_admin

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
