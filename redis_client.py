import os
import redis
from dotenv import load_dotenv

load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

redis_client = redis.StrictRedis.from_url(REDIS_URL, decode_responses=True)

def set_user_session(user_id, data, ttl=1800):
    """Set user session data in Redis with a TTL (in seconds)."""
    key = f"user_session:{user_id}"
    redis_client.hmset(key, data)
    redis_client.expire(key, ttl)

def get_user_session(user_id):
    """Get user session data from Redis."""
    key = f"user_session:{user_id}"
    return redis_client.hgetall(key)

def delete_user_session(user_id):
    key = f"user_session:{user_id}"
    redis_client.delete(key)

def get_all_active_user_sessions():
    """Return a dict of user_id to session data for all active sessions."""
    sessions = {}
    for key in redis_client.scan_iter("user_session:*"):
        user_id = key.split(":", 1)[1]
        sessions[user_id] = redis_client.hgetall(key)
    return sessions
