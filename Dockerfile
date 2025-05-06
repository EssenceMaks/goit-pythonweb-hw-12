FROM python:3.11-slim

WORKDIR /app

# Установка зависимостей для PostgreSQL и Redis
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    libpq-dev \
    redis-tools \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Установка переменных окружения
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DOCKER_ENV=true

# Установка зависимостей
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование проекта
COPY . .

# Скрипт для ожидания запуска базы данных
COPY ./docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
