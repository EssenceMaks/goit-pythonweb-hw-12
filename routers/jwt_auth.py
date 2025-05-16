from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, timedelta
import json

from database import get_db
from models import User
from auth import create_access_token, create_refresh_token, ACCESS_TOKEN_EXPIRE_MINUTES
from redis_client import (
    store_refresh_token, 
    get_refresh_token, 
    delete_refresh_token, 
    get_user_by_refresh_token,
    set_active_user,
    is_user_active
)
from crud import get_user_by_email, get_user_by_id

router = APIRouter(
    prefix="/auth",
    tags=["authentication"],
)

@router.post("/token")
async def login_for_access_token(
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Получение JWT токенов (access_token и refresh_token)
    """
    # Проверяем, является ли ввод email или username
    if '@' in form_data.username:
        # Поиск по email
        user = get_user_by_email(db, email=form_data.username)
    else:
        # Поиск по username
        user = get_user_by_email(db, email=form_data.username)
        if not user:
            # Пробуем найти по username и получить email
            from crud import get_user_by_username
            user_by_username = get_user_by_username(db, username=form_data.username)
            if user_by_username:
                user = user_by_username
    
    if not user or not user.verify_password(form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверные учетные данные",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Проверка, подтвержден ли email
    if not user.is_verified:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пожалуйста, подтвердите ваш email перед входом",
        )
    
    # Создаем access_token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"email": user.email, "id": user.id, "role": user.role or "user"}, 
        expires_delta=access_token_expires
    )
    
    # Создаем refresh_token
    refresh_token, refresh_expires = create_refresh_token(user.id)
    
    # Сохраняем refresh_token в Redis
    user_data = {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role or "user"
    }
    store_refresh_token(user.id, refresh_token, refresh_expires, user_data)
    
    # Устанавливаем токены в cookie
    response.set_cookie(
        key="access_token",
        value=access_token,  # Без префикса "Bearer "
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        samesite="lax"
    )
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=60 * 60 * 24 * 30,  # 30 дней
        path="/",
        samesite="lax"
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role
    }

@router.post("/refresh")
async def refresh_token(
    response: Response,
    refresh_token: Optional[str] = Cookie(None),
    request: Request = None
):
    """
    Обновление access_token с помощью refresh_token
    """
    if not refresh_token and request:
        # Пытаемся получить refresh_token из тела запроса
        try:
            body = await request.json()
            refresh_token = body.get("refresh_token")
        except:
            pass
    
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token не предоставлен",
        )
    
    # Получаем user_id по refresh_token
    user_id = get_user_by_refresh_token(refresh_token)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный refresh token",
        )
    
    # Получаем данные пользователя из базы данных
    db = next(get_db())
    user = get_user_by_id(db, int(user_id))
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Пользователь не найден",
        )
    
    # Создаем новый access_token
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"email": user.email, "id": user.id, "role": user.role or "user"}, 
        expires_delta=access_token_expires
    )
    
    # Обновляем статус активного пользователя
    set_active_user(user.id)
    
    # Устанавливаем новый access_token в cookie
    response.set_cookie(
        key="access_token",
        value=access_token,  # Без префикса "Bearer "
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        samesite="lax"
    )
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user_id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role
    }

@router.post("/logout")
async def logout(
    response: Response,
    user_id: Optional[int] = None,
    refresh_token: Optional[str] = Cookie(None)
):
    """
    Выход из системы и удаление refresh_token
    """
    if refresh_token:
        # Получаем user_id по refresh_token
        if not user_id:
            user_id = get_user_by_refresh_token(refresh_token)
        
        if user_id:
            # Удаляем refresh_token из Redis
            delete_refresh_token(int(user_id))
    
    # Удаляем токены из cookie
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    
    return {"message": "Успешный выход из системы"}

@router.get("/status")
async def token_status(
    refresh_token: Optional[str] = Cookie(None),
    user_id: Optional[int] = None
):
    """
    Проверка статуса токенов для указанного пользователя
    """
    if not user_id and refresh_token:
        # Получаем user_id по refresh_token
        user_id = get_user_by_refresh_token(refresh_token)
    
    if not user_id:
        return {
            "status": "unknown",
            "message": "Не удалось определить пользователя"
        }
    
    # Проверяем наличие refresh_token
    token_data = get_refresh_token(int(user_id))
    
    if token_data:
        # Проверяем, активен ли пользователь
        is_active = is_user_active(int(user_id))
        
        if is_active:
            return {
                "status": "active",
                "message": "Пользователь активен, токены действительны",
                "user_id": user_id
            }
        else:
            return {
                "status": "inactive",
                "message": "Токены действительны, но пользователь неактивен",
                "user_id": user_id
            }
    else:
        return {
            "status": "expired",
            "message": "Refresh token истек или отсутствует",
            "user_id": user_id
        }

@router.post("/switch/{target_user_id}")
async def switch_account(
    response: Response,
    target_user_id: int,
    current_refresh_token: Optional[str] = Cookie(None),
    db: Session = Depends(get_db)
):
    """
    Переключение между аккаунтами
    """
    # Получаем текущего пользователя по refresh_token
    current_user_id = None
    if current_refresh_token:
        current_user_id = get_user_by_refresh_token(current_refresh_token)
    
    # Получаем целевого пользователя
    target_user = get_user_by_id(db, target_user_id)
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Целевой пользователь не найден",
        )
    
    # Если есть текущий пользователь, удаляем его refresh_token
    if current_user_id:
        delete_refresh_token(int(current_user_id))
    
    # Проверяем, есть ли у целевого пользователя действующий refresh_token
    target_token_data = get_refresh_token(target_user_id)
    
    # Создаем новый access_token для целевого пользователя
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"email": target_user.email, "id": target_user.id, "role": target_user.role or "user"}, 
        expires_delta=access_token_expires
    )
    
    # Создаем новый refresh_token для целевого пользователя
    refresh_token, refresh_expires = create_refresh_token(target_user.id)
    
    # Сохраняем refresh_token в Redis
    user_data = {
        "id": target_user.id,
        "username": target_user.username,
        "email": target_user.email,
        "role": target_user.role or "user"
    }
    store_refresh_token(target_user.id, refresh_token, refresh_expires, user_data)
    
    # Устанавливаем токены в cookie
    response.set_cookie(
        key="access_token",
        value=access_token,  # Без префикса "Bearer "
        httponly=True,
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        samesite="lax"
    )
    
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=60 * 60 * 24 * 30,  # 30 дней
        path="/",
        samesite="lax"
    )
    
    return {
        "message": f"Успешное переключение на аккаунт {target_user.username}",
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "user_id": target_user.id,
        "username": target_user.username,
        "email": target_user.email,
        "role": target_user.role
    }

@router.get("/accounts/status")
async def accounts_status(
    user_ids: str,
    db: Session = Depends(get_db)
):
    """
    Получение статуса аккаунтов по списку ID
    """
    try:
        # Преобразуем строку с ID в список
        ids = [int(id) for id in user_ids.split(",")]
    except:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат списка ID",
        )
    
    result = {}
    for user_id in ids:
        # Проверяем существование пользователя
        user = get_user_by_id(db, user_id)
        if not user:
            result[user_id] = {
                "status": "not_found",
                "message": "Пользователь не найден"
            }
            continue
        
        # Проверяем наличие refresh_token
        token_data = get_refresh_token(user_id)
        
        if token_data:
            refresh_token, expires_at = token_data
            # Проверяем, активен ли пользователь
            is_active = is_user_active(user_id)
            
            if is_active:
                result[user_id] = {
                    "status": "active",
                    "message": "Пользователь активен, токены действительны",
                    "username": user.username,
                    "email": user.email,
                    "role": user.role
                }
            else:
                result[user_id] = {
                    "status": "inactive",
                    "message": "Токены действительны, но пользователь неактивен",
                    "username": user.username,
                    "email": user.email,
                    "role": user.role
                }
        else:
            result[user_id] = {
                "status": "expired",
                "message": "Refresh token истек или отсутствует",
                "username": user.username,
                "email": user.email,
                "role": user.role
            }
    
    return result
