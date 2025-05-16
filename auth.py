from fastapi import Depends, HTTPException, status, Cookie, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from typing import Optional
from datetime import datetime, timedelta
from database import SessionLocal
from crud import get_user_by_username, get_user_by_email
import os
import uuid
from dotenv import load_dotenv
from passlib.context import CryptContext

load_dotenv()

# Создаём контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Конфигурация JWT
SECRET_KEY = os.getenv("SECRET_KEY", "default_secret_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15  # Уменьшаем время жизни access_token
REFRESH_TOKEN_EXPIRE_DAYS = 30    # Время жизни refresh_token в днях

# Схема OAuth2 для получения токена из заголовка Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token", auto_error=False)  # Changed to auto_error=False

# Модель данных пользователя для JWT
class TokenData:
    def __init__(self, email: Optional[str] = None, user_id: Optional[int] = None):
        self.email = email
        self.user_id = user_id

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(user_id: int):
    """Создает refresh_token для пользователя"""
    expires = datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    refresh_token = str(uuid.uuid4())
    
    # Данные для сохранения в Redis будут добавлены в redis_client.py
    return refresh_token, expires

# Вспомогательная функция для получения токена из разных источников
async def get_token_from_request(
    request: Request, 
    token: Optional[str] = Depends(oauth2_scheme),
    access_token: Optional[str] = Cookie(None)
):
    # Сначала проверяем токен из OAuth2 (заголовок Authorization)
    if token:
        print(f"Получен токен из заголовка Authorization: {token[:10]}...")
        return token
    
    # Затем проверяем токен из Cookie
    if access_token:
        # Токен должен быть без префикса Bearer
        token_value = access_token
        if token_value.startswith("Bearer "):
            token_value = token_value[7:]  # Убираем префикс "Bearer "
        print(f"Получен токен из cookie: {token_value[:10]}...")
        return token_value
    
    # В крайнем случае пытаемся получить токен из заголовка вручную
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token_value = auth_header[7:]  # Убираем префикс "Bearer "
        print(f"Получен токен из заголовка вручную: {token_value[:10]}...")
        return token_value
    
    # Проверяем куки напрямую из запроса
    cookies = request.cookies
    if 'access_token' in cookies:
        cookie_token = cookies['access_token']
        if cookie_token.startswith("Bearer "):
            cookie_token = cookie_token[7:]
        print(f"Получен токен из request.cookies: {cookie_token[:10]}...")
        return cookie_token
    
    print("Токен не найден")
    return None

async def get_refresh_token_from_request(request: Request, refresh_token: Optional[str] = Cookie(None)):
    """Получает refresh_token из запроса"""
    if refresh_token:
        return refresh_token
    
    # Проверяем куки напрямую из запроса
    cookies = request.cookies
    if 'refresh_token' in cookies:
        return cookies['refresh_token']
    
    return None

async def get_current_user(request: Request, token: Optional[str] = Depends(get_token_from_request)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось проверить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    # Если токена нет, возвращаем ошибку авторизации
    if not token:
        print("Ошибка авторизации: Токен отсутствует")
        raise credentials_exception
    
    try:
        print(f"Попытка декодирования токена: {token[:10]}...")
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(f"Токен декодирован успешно. Содержимое: {payload}")
        email: str = payload.get("email")
        user_id: int = payload.get("id")
        user_role: str = payload.get("role")
        print(f"Извлеченные данные: email={email}, id={user_id}, role={user_role}")
        
        if email is None:
            print("Ошибка: отсутствует поле 'email' в токене")
            raise credentials_exception
            
        token_data = TokenData(email=email, user_id=user_id)
    except JWTError as e:
        print(f"Ошибка при декодировании JWT: {e}")
        raise credentials_exception
    
    db = SessionLocal()
    try:
        user = get_user_by_email(db, email=token_data.email)
        if user is None:
            print(f"Пользователь с email={token_data.email} не найден в БД")
            
            # Особый случай для суперадмина
            if "superadmin" in token_data.email:
                print("Создание объекта пользователя для суперадмина")
                from models import User
                return User(
                    id=user_id or -1,
                    username="superadmin",
                    email=email,
                    role="superadmin"
                )
            
            raise credentials_exception
        
        print(f"Пользователь найден: id={user.id}, role={user.role}")
        return user
    finally:
        db.close()

# Вспомогательная функция для проверки прав доступа к контактам других пользователей
def check_contact_access(user, contact_user_id):
    """
    Проверяет, имеет ли пользователь доступ к контакту другого пользователя
    
    Args:
        user: Объект пользователя 
        contact_user_id: ID пользователя, которому принадлежит контакт
        
    Returns:
        bool: True если доступ разрешен, иначе False
    """
    # Супер-админ имеет доступ ко всем контактам
    if user.role == "superadmin":
        return True
    # Админ имеет доступ ко всем контактам, кроме контактов супер-админа
    elif user.role == "admin":
        # Если бы у супер-админа были контакты, здесь была бы дополнительная проверка
        return True
    # Обычный пользователь имеет доступ только к своим контактам
    else:
        return user.id == contact_user_id