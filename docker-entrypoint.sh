#!/bin/bash
set -e

# Функция для проверки доступности PostgreSQL
postgres_ready() {
    pg_isready -h ${DB_HOST:-db} -p ${DB_PORT:-5432} -U ${DB_USER:-postgres}
}

# Функция для проверки доступности Redis
redis_ready() {
    # Проверяем наличие redis-cli
    if command -v redis-cli > /dev/null; then
        redis-cli -h ${REDIS_HOST:-redis} -p ${REDIS_PORT:-6379} ping | grep -q PONG
    else
        echo "Warning: redis-cli not found, skipping Redis connection check"
        # Возвращаем true, чтобы не блокировать запуск приложения
        return 0
    fi
}

# Ожидаем доступности PostgreSQL
echo "Waiting for PostgreSQL to be ready..."
while ! postgres_ready; do
    echo "PostgreSQL is unavailable - sleeping"
    sleep 2
done
echo "PostgreSQL is ready!"

# Ожидаем доступности Redis (если используется)
if [ -n "$REDIS_URL" ]; then
    echo "Waiting for Redis to be ready..."
    retry_count=0
    max_retries=10
    
    while ! redis_ready && [ $retry_count -lt $max_retries ]; do
        echo "Redis is unavailable - sleeping (attempt $((retry_count+1))/$max_retries)"
        retry_count=$((retry_count+1))
        sleep 2
    done
    
    if [ $retry_count -lt $max_retries ]; then
        echo "Redis is ready!"
    else
        echo "Warning: Redis connection check failed after $max_retries attempts. Proceeding anyway..."
    fi
fi

# Запускаем команду, переданную в CMD
exec "$@"