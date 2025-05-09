from fastapi import APIRouter, Depends, HTTPException
from redis_client import get_all_active_user_sessions
from typing import List, Dict

router = APIRouter(
    prefix="/sessions",
    tags=["sessions"],
)

@router.get("/active", response_model=List[Dict])
def get_active_sessions():
    """
    Returns a list of active user sessions from Redis.
    Each session contains user id, username, email, role, etc.
    """
    sessions = get_all_active_user_sessions()
    # Convert sessions dict to list of dicts
    return list(sessions.values())
