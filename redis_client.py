import os
import redis
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True)

# Константы для ключей в Redis
REFRESH_TOKEN_PREFIX = "refresh_token:"
USER_CACHE_PREFIX = "user_cache:"
ACTIVE_USER_PREFIX = "active_user:"

# Функции для работы с refresh_token
def store_refresh_token(user_id, refresh_token, expires_at, user_data=None):
    """Сохраняет refresh_token в Redis с привязкой к пользователю"""
    key = f"{REFRESH_TOKEN_PREFIX}{user_id}"
    
    # Сохраняем токен и время истечения
    data = {
        "token": refresh_token,
        "expires_at": expires_at.isoformat(),
    }
    
    # Если предоставлены данные пользователя, сохраняем их тоже
    if user_data:
        data.update({"user_data": json.dumps(user_data)})
    
    # Вычисляем TTL в секундах
    ttl = int((expires_at - datetime.utcnow()).total_seconds())
    
    # Сохраняем в Redis
    redis_client.hmset(key, data)
    redis_client.expire(key, ttl)
    
    # Сохраняем обратное соответствие для поиска user_id по токену
    token_key = f"token_to_user:{refresh_token}"
    redis_client.set(token_key, str(user_id))
    redis_client.expire(token_key, ttl)
    
    # Устанавливаем этого пользователя как активного
    set_active_user(user_id)
    
    return True

def get_user_by_refresh_token(refresh_token):
    """Получает user_id по refresh_token"""
    token_key = f"token_to_user:{refresh_token}"
    user_id = redis_client.get(token_key)
    
    if not user_id:
        return None
        
    return user_id

def get_refresh_token(user_id):
    """Получает refresh_token по user_id"""
    key = f"{REFRESH_TOKEN_PREFIX}{user_id}"
    data = redis_client.hgetall(key)
    
    if not data:
        return None
        
    return data.get("token"), data.get("expires_at")

def delete_refresh_token(user_id):
    """Удаляет refresh_token пользователя"""
    key = f"{REFRESH_TOKEN_PREFIX}{user_id}"
    
    # Получаем токен перед удалением
    data = redis_client.hgetall(key)
    if data and "token" in data:
        # Удаляем обратное соответствие
        token_key = f"token_to_user:{data['token']}"
        redis_client.delete(token_key)
    
    # Удаляем основной ключ
    return redis_client.delete(key)

# Функции для кеширования данных пользователя
def cache_user_data(user_id, user_data, ttl=3600):
    """Кеширует данные пользователя"""
    key = f"{USER_CACHE_PREFIX}{user_id}"
    
    # Преобразуем словарь в строку JSON
    if isinstance(user_data, dict):
        user_data = json.dumps(user_data)
        
    redis_client.set(key, user_data)
    redis_client.expire(key, ttl)
    
    return True

def get_cached_user_data(user_id):
    """Получает кешированные данные пользователя"""
    key = f"{USER_CACHE_PREFIX}{user_id}"
    data = redis_client.get(key)
    
    if not data:
        return None
        
    # Преобразуем строку JSON обратно в словарь
    try:
        return json.loads(data)
    except:
        return data

def invalidate_user_cache(user_id):
    """Инвалидирует кеш пользователя"""
    key = f"{USER_CACHE_PREFIX}{user_id}"
    return redis_client.delete(key)

# Функции для отслеживания активных пользователей
def set_active_user(user_id, ttl=86400):  # 24 часа по умолчанию
    """Отмечает пользователя как активного"""
    key = f"{ACTIVE_USER_PREFIX}{user_id}"
    redis_client.set(key, datetime.utcnow().isoformat())
    redis_client.expire(key, ttl)
    
    return True

def is_user_active(user_id):
    """Проверяет, активен ли пользователь"""
    key = f"{ACTIVE_USER_PREFIX}{user_id}"
    return redis_client.exists(key)

def get_all_active_users():
    """Возвращает список всех активных пользователей"""
    active_users = []
    for key in redis_client.scan_iter(f"{ACTIVE_USER_PREFIX}*"):
        user_id = key.split(":", 1)[1]
        active_users.append(user_id)
    
    return active_users

# Оставляем для обратной совместимости
def set_user_session(user_id, data, ttl=1800):
    """Set user session data in Redis with a TTL (in seconds)."""
    key = f"user_session:{user_id}"
    redis_client.hmset(key, data)
    redis_client.expire(key, ttl)
    
    # Также кешируем данные пользователя
    cache_user_data(user_id, data, ttl)

def get_user_session(user_id):
    """Get user session data from Redis."""
    key = f"user_session:{user_id}"
    return redis_client.hgetall(key)

def delete_user_session(user_id):
    key = f"user_session:{user_id}"
    redis_client.delete(key)
    
    # Также инвалидируем кеш пользователя
    invalidate_user_cache(user_id)

def get_all_active_user_sessions():
    """Return a dict of user_id to session data for all active sessions."""
    sessions = {}
    for key in redis_client.scan_iter("user_session:*"):
        user_id = key.split(":", 1)[1]
        sessions[user_id] = redis_client.hgetall(key)
    return sessions
