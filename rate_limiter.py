from fastapi import FastAPI, Request, Response, Depends, HTTPException, status
import redis.asyncio as redis
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
import os
from dotenv import load_dotenv
import asyncio
from typing import Optional

# Загружаем переменные окружения
load_dotenv()

# Получаем URL Redis из переменных окружения
# Для Render.com проверяем как REDIS_URL, так и RENDER_REDIS_URL
REDIS_URL = os.getenv("REDIS_URL") or os.getenv("RENDER_REDIS_URL")

# Проверяем, настроено ли ограничение запросов или нет
RATE_LIMIT_ENABLED = os.getenv("RATE_LIMIT_ENABLED", "True").lower() in ("true", "1", "t")

# Флаг для проверки успешности подключения к Redis
redis_connected = False

async def init_limiter():
    """
    Инициализация rate limiter при запуске приложения
    """
    global redis_connected
    
    # Если ограничение запросов отключено или Redis URL не задан, пропускаем инициализацию
    if not RATE_LIMIT_ENABLED:
        print("Rate limiter отключен в настройках")
        return
    
    if not REDIS_URL:
        print("REDIS_URL не задан. Rate limiter будет работать без ограничений.")
        return
    
    try:
        print(f"Попытка подключения к Redis по адресу: {REDIS_URL}")
        redis_instance = redis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
        await FastAPILimiter.init(redis_instance)
        redis_connected = True
        print("Rate limiter успешно инициализирован с Redis")
    except Exception as e:
        print(f"Ошибка при инициализации rate limiter: {e}")
        print("Приложение продолжит работу без ограничения запросов")
        redis_connected = False

# Создаем зависимости для разных типов ограничения
# Ограничение: 5 запросов в минуту
rate_limit_me_endpoint = RateLimiter(times=25, seconds=60)

# Функция для создания зависимости с обработкой случая отсутствия соединения с Redis
async def check_rate_limit_me(request: Request, response: Response):
    """
    Проверяет ограничение скорости для маршрута /me
    """
    if not redis_connected or not RATE_LIMIT_ENABLED:
        # Если Redis не подключен или ограничение выключено, пропускаем ограничение
        return
    
    # Используем стандартный rate limiter
    await rate_limit_me_endpoint(request, response)