from fastapi import FastAPI, Request, HTTPException, Form, Depends, status, Cookie, Body, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware import Middleware
from starlette.middleware.sessions import SessionMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from typing import Optional
from datetime import timedelta, datetime
from jose import JWTError, jwt
import secrets
import uuid
import logging
import time
import sqlalchemy.exc
from pydantic import EmailStr
import psycopg2
import re

# Добавляем импорт роутеров
from routers import contacts, groups, db_utils, email_verification, users
from routers.users_sessions import router as sessions_router
from routers.jwt_auth import router as auth_router
from database import SessionLocal, engine, Base, is_render_environment, is_docker_environment
from crud import get_user_by_username, update_user_role, get_user_by_id
import models
import os
from dotenv import load_dotenv
# Redis session utility
from redis_client import set_user_session
# Импортируем функции из auth.py
from auth import pwd_context, create_access_token, create_refresh_token, ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM
# Добавляем импорт нашей новой функции отправки email
from utils_email_verif import send_verification_email, send_password_reset_email
# Импортируем функции для rate limiting
from rate_limiter import init_limiter

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Функция для очистки Redis и валидации токенов при запуске
def clear_redis_on_startup():
    # Импортируем функции для работы с Redis
    from redis_client import clear_redis_keys, set_redis_version
    
    # Очищаем все ключи в Redis при запуске
    print("\n\nОчистка Redis при запуске приложения...")
    success = clear_redis_keys()
    if success:
        print("Все ключи Redis успешно очищены. Токены в браузере будут сброшены при следующем запросе.")
    else:
        print("Ошибка при очистке ключей Redis.")
    
    # Устанавливаем новую версию Redis
    # Это позволит отклонять токены, созданные до перезапуска Redis
    redis_version = set_redis_version()
    print(f"Установлена новая версия Redis: {redis_version}")
    print("Теперь все токены, созданные до перезапуска, будут считаться недействительными.")
    print("\n")

# Функция для создания базы данных, если она не существует
def ensure_database_exists():
    # Получаем данные подключения из переменных окружения
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        # Исправляем URL для совместимости с SQLAlchemy
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        # Извлекаем параметры из строки подключения
        pattern = r"postgresql://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:/]+)(?::(?P<port>\d+))?/(?P<dbname>[^?]+)"
        match = re.search(pattern, database_url)
        
        if match:
            host = match.group("host")
            user = match.group("user") 
            password = match.group("password")
            db_name = match.group("dbname")
            port = match.group("port") or "5432"
            
            logger.info(f"Проверка существования базы данных '{db_name}' на сервере {host}...")
            
            try:
                # Подключаемся к postgres для проверки и создания базы
                conn = psycopg2.connect(
                    dbname='postgres',
                    user=user,
                    password=password,
                    host=host,
                    port=port,
                    connect_timeout=10
                )
                conn.autocommit = True
                cur = conn.cursor()
                
                # Проверяем существование базы данных
                cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,))
                exists = cur.fetchone()
                
                if not exists:
                    logger.info(f"База данных '{db_name}' не существует. Создаю...")
                    cur.execute(f"CREATE DATABASE {db_name}")
                    logger.info(f"База данных '{db_name}' успешно создана!")
                else:
                    logger.info(f"База данных '{db_name}' уже существует.")
                
                cur.close()
                conn.close()
                return True
            except Exception as e:
                logger.error(f"Ошибка при проверке/создании базы данных: {str(e)}")
                # В Docker контейнере PostgreSQL может быть недоступен сразу после запуска
                # поэтому продолжаем выполнение, даже если сейчас не удалось создать БД
                return False
    else:
        logger.warning("DATABASE_URL не задан в переменных окружения")
        return False

# Инициализация приложения
app = FastAPI(title="Contacts API")

# Register routers with explicit prefixes
app.include_router(contacts.router)
app.include_router(groups.router)
app.include_router(db_utils.router)
app.include_router(users.router)
app.include_router(email_verification.router)
app.include_router(sessions_router)
app.include_router(auth_router)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# (Роутеры уже зарегистрированы выше с префиксами, повторная регистрация не требуется)

# Создаем таблицы базы данных при запуске приложения
@app.on_event("startup")
async def startup_db_and_tables():
    logger.info("Инициализация приложения...")
    
    # Добавляем задержку при запуске на Render.com или в Docker,
    # чтобы дать БД время инициализироваться
    if is_render_environment() or is_docker_environment():
        logger.info("Обнаружено окружение Render.com или Docker, ожидаем инициализацию внешних сервисов...")
        time.sleep(5)  # Даем время для инициализации внешних сервисов
    
    # Очищаем Redis при запуске, чтобы избежать несоответствия токенов
    logger.info("Очистка Redis при запуске...")
    clear_redis_on_startup()
    
    # Сначала проверяем существование базы данных и создаем её при необходимости
    logger.info("Проверка наличия базы данных...")
    database_created = ensure_database_exists()
    
    if database_created:
        logger.info("База данных доступна. Продолжаем инициализацию...")
    else:
        logger.warning("Не удалось создать базу данных сейчас. Попытаемся создать таблицы позже...")
    
    # Пытаемся установить соединение с базой данных с повторными попытками
    max_retries = 10 if (is_render_environment() or is_docker_environment()) else 5
    retry_delay = 3  # Секунды между попытками
    
    for attempt in range(max_retries):
        try:
            # Пытаемся создать таблицы в базе данных
            Base.metadata.create_all(bind=engine)
            logger.info(f"Таблицы базы данных успешно созданы (попытка {attempt+1})")
            break
        except sqlalchemy.exc.OperationalError as e:
            logger.error(f"Ошибка подключения к базе данных (попытка {attempt+1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                logger.info(f"Повторная попытка через {retry_delay} секунд...")
                time.sleep(retry_delay)
                # Попробуем создать БД снова
                if attempt == max_retries // 2:
                    ensure_database_exists()
            else:
                logger.error("Все попытки подключения к базе данных исчерпаны")
                logger.error("Приложение продолжит работу, но функции, требующие базу данных, будут недоступны")
                # Не завершаем приложение, позволяя ему продолжить работать с ограниченной функциональностью
        except Exception as e:
            logger.error(f"Непредвиденная ошибка при инициализации базы данных: {e}")
            break
    
    # Пытаемся создать супер-админа
    try:
        # Создаем супер-админа, если он не существует
        db = SessionLocal()
        try:
            superadmin_username = os.getenv("SUPERADMIN_USERNAME")
            superadmin_password = os.getenv("SUPERADMIN_PASSWORD")
            superadmin_email = os.getenv("SUPER_ADMIN_EMAIL", superadmin_username)

            # Validate email format using Pydantic's EmailStr
            from pydantic import ValidationError
            valid_email = None
            try:
                # If not present or not valid, fallback to username@example.com
                if not superadmin_email or '@' not in superadmin_email:
                    superadmin_email = f"{superadmin_username}@example.com"
                valid_email = EmailStr(superadmin_email)
            except ValidationError:
                logger.warning(f"SUPER_ADMIN_EMAIL '{superadmin_email}' is invalid. Using default.")
                valid_email = EmailStr(f"{superadmin_username}@example.com")
                superadmin_email = str(valid_email)

            if superadmin_username and superadmin_password:
                # Проверяем, существует ли уже супер-админ
                existing_admin = get_user_by_username(db, superadmin_username)

                if not existing_admin:
                    logger.info(f"Создаем учетную запись супер-админа: {superadmin_username}")
                    # Создаем запись супер-админа в базе данных
                    hashed_password = models.User.get_password_hash(superadmin_password)
                    superadmin = models.User(
                        username=superadmin_username,
                        email=str(valid_email),
                        hashed_password=hashed_password,
                        role="superadmin",
                        is_verified=True  # Супер-админ не требует верификации
                    )
                    db.add(superadmin)
                    db.commit()
                    logger.info("Учетная запись супер-админа успешно создана")
                else:
                    # Check if existing superadmin has invalid email
                    try:
                        EmailStr(existing_admin.email)
                    except ValidationError:
                        logger.warning(f"Существующий супер-админ имеет некорректный email: {existing_admin.email}. Исправляем на {valid_email}.")
                        existing_admin.email = str(valid_email)
                        db.commit()
                        logger.info("Email супер-админа обновлен на валидный.")
                    logger.info("Учетная запись супер-админа уже существует")
        except Exception as e:
            logger.error(f"Ошибка при создании супер-админа: {e}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Ошибка при работе с базой данных: {e}")
    
    # Очистка Redis при запуске
    try:
        from redis_client import clear_redis_keys
        clear_redis_keys()
        logger.info("Ключи Redis успешно очищены")
    except Exception as e:
        logger.error(f"Ошибка при очистке ключей Redis: {e}")
    
    # Инициализация rate limiter
    try:
        await init_limiter()
    except Exception as e:
        logger.error(f"Ошибка при инициализации rate limiter: {e}")
        logger.info("Приложение продолжит работу без ограничения запросов (rate limiting)")
    

# JWT аутентификация используется вместо сессий

# Настройка шаблонов
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Функция для очистки имени пользователя для URL
def clean_username_for_url(username: str) -> str:
    """Очищает имя пользователя для использования в URL"""
    # Если это email, удаляем домен
    if '@' in username:
        username = username.split('@')[0]
    
    # Удаляем специальные символы
    import re
    username = re.sub(r'[^\w\d]', '', username)
    
    return username



# Функция для получения токена из cookie
async def get_token_from_cookie(access_token: Optional[str] = Cookie(None)):
    # Проверяем наличие токена
    if access_token:
        # Если токен начинается с "Bearer ", убираем этот префикс
        if access_token.startswith("Bearer "):
            return access_token[7:]
        # Иначе возвращаем токен как есть
        return access_token
    return None

# Обновление редиректов для использования относительных URL
from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
async def root(request: Request, token: Optional[str] = Depends(get_token_from_cookie)):
    try:
        logger.info("[ROOT] Accessed / endpoint.")
        logger.info(f"[ROOT] Request cookies: {request.cookies}")
        
        # Если токен есть, декодируем его для получения данных пользователя
        if token:
            try:
                # Декодируем JWT токен
                payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
                email = payload.get("email")
                user_id = payload.get("id")
                role = payload.get("role", "user")
                
                if email:
                    # Получаем username из email для URL
                    clean_username = clean_username_for_url(email)
                    logger.info(f"[ROOT] Authenticated user found: {email} with role {role}")
                    return RedirectResponse(url=f"/{clean_username}_{role}/", status_code=303)
            except JWTError:
                # Если токен невалидный, перенаправляем на страницу входа
                logger.info("[ROOT] Invalid token, redirecting to login")
                pass
        
        logger.info("[ROOT] No authenticated user, returning login.html")
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "password_reset_success": False
            }
        )
    except Exception as exc:
        logger.error(f"[ROOT] Exception: {exc}")
        return HTMLResponse("Internal Server Error", status_code=500)



from fastapi.responses import HTMLResponse

@app.get("/login", response_class=HTMLResponse)
async def login(request: Request, email: str = None, password_reset_success: bool = False):
    try:
        logger.info("[LOGIN] Accessed /login endpoint.")
        logger.info(f"[LOGIN] Request cookies: {request.cookies}")
        
        # Проверяем наличие параметра в URL вместо использования сессии
        logger.info(f"[LOGIN] password_reset_success: {password_reset_success}")
        
        return templates.TemplateResponse(
            "login.html",
            {
                "request": request,
                "password_reset_success": password_reset_success,
                "email": email
            }
        )
    except Exception as exc:
        logger.error(f"[LOGIN] Exception: {exc}")
        return HTMLResponse("Internal Server Error", status_code=500)


@app.post("/login")
async def login_post(request: Request, username: str = Form(...), password: str = Form(...)):
    db = SessionLocal()
    try:
        # Проверяем, является ли ввод email или username
        if '@' in username:
            # Поиск по email
            user = db.query(models.User).filter(models.User.email == username).first()
        else:
            # Поиск по username
            user = get_user_by_username(db, username)
        
        # Проверка для суперадмина
        if username == os.getenv("SUPERADMIN_USERNAME") and password == os.getenv("SUPERADMIN_PASSWORD"):
            # Проверяем, существует ли суперадмин в базе данных
            superadmin_user = get_user_by_username(db, username)
            
            # Генерируем уникальный ID для суперадмина если он не найден в БД
            superadmin_id = superadmin_user.id if superadmin_user else -1
            
            # Данные пользователя для токена
            user_data = {
                "id": superadmin_id,
                "username": username,
                "email": username,
                "role": "superadmin"
            }
            
            # Создаем access_token для JWT-аутентификации
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"id": superadmin_id, "role": "superadmin", "email": username}, 
                expires_delta=access_token_expires
            )
            
            # Создаем refresh_token
            refresh_token, refresh_expires = create_refresh_token(superadmin_id)
            
            # Сохраняем refresh_token в Redis
            from redis_client import store_refresh_token
            store_refresh_token(superadmin_id, refresh_token, refresh_expires, user_data)
            
            # Удаляем домен из email для URL
            clean_username = clean_username_for_url(username)
            response = RedirectResponse(url=f"/{clean_username}_superadmin/", status_code=303)
            
            # Устанавливаем cookie с токенами
            response.set_cookie(
                key="access_token",
                value=access_token,
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
            
            return response
        
        # Проверка для обычных пользователей
        elif user and pwd_context.verify(password, user.hashed_password):
            # Проверка, подтвержден ли email
            if not user.is_verified:
                return templates.TemplateResponse("login.html", {"request": request, "error": "Пожалуйста, подтвердите ваш email перед входом"})
            
            # Данные пользователя для токена
            user_data = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "role": user.role or "user"
            }
            
            # Создаем access_token для JWT-аутентификации
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"id": user.id, "role": user.role or "user", "email": user.email}, 
                expires_delta=access_token_expires
            )
            
            # Создаем refresh_token
            refresh_token, refresh_expires = create_refresh_token(user.id)
            
            # Сохраняем refresh_token в Redis
            from redis_client import store_refresh_token, track_user_login
            store_refresh_token(user.id, refresh_token, refresh_expires, user_data)
            
            # Отслеживаем логин пользователя (сохраняем на 6 часов)
            track_user_login(user.id, user_data)
            
            # Удаляем домен из email для URL если username это email
            clean_username = clean_username_for_url(user.username)
            response = RedirectResponse(url=f"/{clean_username}_{user.role or 'user'}/", status_code=303)
            
            # Устанавливаем cookie с токенами
            response.set_cookie(
                key="access_token",
                value=access_token,
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
            
            return response
        else:
            return templates.TemplateResponse("login.html", {"request": request, "error": "Неверное имя пользователя или пароль"})
    finally:
        db.close()

@app.get("/signup", response_class=HTMLResponse)
def signup_get(request: Request):
    return templates.TemplateResponse("signup.html", {"request": request})

@app.post("/signup", response_class=HTMLResponse)
def signup_post(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    # TODO: Зарегистрировать пользователя в БД
    db = SessionLocal()
    try:
        # Создаем нового пользователя
        from crud import create_user
        new_user = create_user(db, username=username, email=email, password=password)
        
        if new_user:
            # Создаем access_token для JWT-аутентификации
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"id": new_user.id, "role": "user", "email": email}, 
                expires_delta=access_token_expires
            )
            
            # Создаем refresh_token
            refresh_token, refresh_expires = create_refresh_token(new_user.id)
            
            # Сохраняем refresh_token в Redis
            user_data = {
                "id": new_user.id,
                "username": username,
                "email": email,
                "role": "user"
            }
            from redis_client import store_refresh_token
            store_refresh_token(new_user.id, refresh_token, refresh_expires, user_data)
            
            # Перенаправляем на страницу пользователя
            response = RedirectResponse(f"/{username}_user/", status_code=303)
            
            # Устанавливаем cookie с токенами
            response.set_cookie(
                key="access_token",
                value=access_token,
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
            
            return response
        else:
            return templates.TemplateResponse("signup.html", {"request": request, "error": "Ошибка при регистрации пользователя"})
    finally:
        db.close()

@app.get("/{username}_{role}/", response_class=HTMLResponse)
def user_dashboard(
    request: Request, 
    username: str, 
    role: str,
    access_token: Optional[str] = Cookie(None)
):
    # Проверяем наличие токена в cookie
    if not access_token:
        logger.error(f"[USER_DASHBOARD] No access_token in cookies")
        return RedirectResponse("/login")
    
    try:
        # Декодируем JWT токен
        payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
        user_email = payload.get("email")
        user_id = payload.get("id")
        user_role = payload.get("role", "user")
        
        logger.info(f"[USER_DASHBOARD] Decoded token: email={user_email}, id={user_id}, role={user_role}")
        
        if not user_email:
            logger.error(f"[USER_DASHBOARD] No email in token payload")
            return RedirectResponse("/login")
        
        # Проверяем соответствие URL и данных из токена
        token_clean_username = clean_username_for_url(user_email.split('@')[0] if '@' in user_email else user_email)
        logger.info(f"[USER_DASHBOARD] URL username={username}, token username={token_clean_username}, URL role={role}, token role={user_role}")
        
        # Более гибкая проверка соответствия URL и данных из токена
        if token_clean_username != username or user_role != role:
            logger.warning(f"[USER_DASHBOARD] URL mismatch: expected {token_clean_username}_{user_role}, got {username}_{role}")
            # Перенаправляем на правильный URL вместо страницы логина
            return RedirectResponse(f"/{token_clean_username}_{user_role}/")
        
        # Создаем объект пользователя для шаблона
        user = {
            "id": user_id,
            "username": user_email,  # Используем email вместо username
            "email": user_email,
            "role": user_role
        }
        
        # Попробуем получить дополнительные данные из кэша
        from redis_client import get_cached_user_data
        cached_data = get_cached_user_data(user_id)
        if cached_data and isinstance(cached_data, dict):
            # Обновляем данные пользователя из кэша
            user.update(cached_data)
        
        # Выводим отладочную информацию о токене в консоль
        print(f"Token from cookie: {access_token[:10]}..." if access_token else "No token")
        
        # TODO: Получить контакты только этого пользователя
        # contacts = crud.get_contacts_for_user(username)
        return templates.TemplateResponse("index.html", {
            "request": request,
            "user": user,
            # "contacts": contacts,
        })
    except JWTError:
        # Если токен невалиден, перенаправляем на страницу входа
        return RedirectResponse("/login")

@app.get("/current_user", response_class=HTMLResponse)
def current_user(request: Request):
    # TODO: Если залогинено несколько пользователей — показать выбор
    return templates.TemplateResponse("current_user.html", {"request": request})

@app.get("/logout")
def logout(request: Request, access_token: Optional[str] = Cookie(None), refresh_token: Optional[str] = Cookie(None)):
    try:
        # Если есть токен, пытаемся получить из него user_id
        if access_token:
            try:
                payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
                user_id = payload.get("id")
                
                if user_id:
                    # Удаляем refresh_token из Redis
                    from redis_client import delete_refresh_token
                    delete_refresh_token(user_id)
            except JWTError:
                pass
        
        # Если есть refresh_token, получаем по нему user_id
        if refresh_token:
            from redis_client import get_user_by_refresh_token
            user_id = get_user_by_refresh_token(refresh_token)
            if user_id:
                from redis_client import delete_refresh_token
                delete_refresh_token(user_id)
    except Exception as e:
        print(f"Error during logout: {e}")
    
    response = RedirectResponse("/login")
    
    # Удаляем все токены из cookie
    response.delete_cookie("access_token", path="/")
    response.delete_cookie("refresh_token", path="/")
    
    return response

@app.post("/token")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    db = SessionLocal()
    try:
        user = get_user_by_username(db, form_data.username)
        if not user or not pwd_context.verify(form_data.password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Неверное имя пользователя или пароль",
                headers={"WWW-Authenticate": "Bearer"},
            )
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user.username, "id": user.id, "role": user.role}, 
            expires_delta=access_token_expires
        )
        return {"access_token": access_token, "token_type": "bearer"}
    finally:
        db.close()

# Эндпоинт для проверки статуса авторизации

from fastapi import Body
from typing import List, Dict

@app.post("/accounts/status")
async def accounts_status(user_ids: List[int] = Body(...), access_token: Optional[str] = Cookie(None)):
    from redis_client import get_refresh_token, is_user_active, get_cached_user_data, is_recent_login
    result = {}
    
    # Получаем ID текущего пользователя из access_token
    current_user_id = None
    current_user_email = None
    current_user_role = None
    token_valid = False
    
    if access_token:
        try:
            payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
            current_user_id = payload.get("id")
            current_user_email = payload.get("email")
            current_user_role = payload.get("role", "user")
            
            # Проверяем, есть ли в Redis данные для этого пользователя
            # Если Redis был очищен, но токены в браузере остались, токен будет считаться невалидным
            refresh_token_data = get_refresh_token(current_user_id)
            if not refresh_token_data:
                print(f"\nПредупреждение: Токен в браузере есть, но в Redis нет соответствующего refresh_token.")
                print(f"Возможно, Redis был очищен при перезапуске Docker. Пользователю нужно будет перелогиниться.\n")
            else:
                token_valid = True
                print(f"\nТекущий пользователь: ID={current_user_id}, Email={current_user_email}, Роль={current_user_role}\n")
        except JWTError:
            pass
    
    # Получаем информацию о всех запрошенных пользователях
    db = SessionLocal()
    try:
        # Создаем словарь с информацией о пользователях
        users_info = {}
        for uid in user_ids:
            user = db.query(models.User).filter(models.User.id == uid).first()
            if user:
                users_info[uid] = {
                    "username": user.username,
                    "email": user.email,
                    "role": user.role
                }
    finally:
        db.close()
    
    # Убираем дубликаты из user_ids
    unique_user_ids = list(dict.fromkeys(user_ids))
    
    # Проверяем, какие пользователи имеют данные в Redis /me или недавно логинились
    users_to_log = []
    for uid in unique_user_ids:
        me_data = get_cached_user_data(uid)
        recent_login = is_recent_login(uid)
        if me_data or recent_login or (current_user_id and int(uid) == int(current_user_id)):
            users_to_log.append(uid)
    
    print("\nСтатусы аккаунтов в knownAccounts:")
    print("-" * 80)
    print(f"{'ID':<5} | {'Email':<25} | {'Role':<10} | {'Status':<10} | {'Recent Login':<12} | Описание")
    print("-" * 80)

    for uid in users_to_log:
        refresh_token_data = get_refresh_token(uid)
        is_active = is_user_active(uid)
        recent_login = is_recent_login(uid)
        user_email = users_info.get(uid, {}).get("email", "unknown")
        user_role = users_info.get(uid, {}).get("role", "unknown")
        recent_login_status = "Yes" if recent_login else "No"

        # Определяем статус и описание (НЕ меняем бизнес-логику, только логи)
        if current_user_id and int(uid) == int(current_user_id):
            if refresh_token_data:
                status = "green"
                status_desc = "Текущий пользователь с refresh_token (зеленая точка)"
            else:
                status = "yellow"
                status_desc = "Текущий пользователь без refresh_token (желтая точка)"
        elif refresh_token_data:
            status = "green"
            status_desc = "Есть refresh_token (зеленая точка)"
        elif is_active:
            status = "yellow"
            status_desc = "Активен, но без refresh_token (желтая точка)"
        elif recent_login:
            status = "yellow"
            status_desc = "Недавно логинился (желтая точка)"
        else:
            status = "gray"
            status_desc = "Неактивен (серая точка)"

        print(f"{uid:<5} | {user_email[:25]:<25} | {user_role:<10} | {status:<10} | {recent_login_status:<12} | {status_desc}")

    print("-" * 80)
    print("")
    
    # Возвращаем результат для всех запрошенных ID
    for uid in unique_user_ids:
        if uid not in result:
            # Проверяем наличие refresh_token в Redis
            refresh_token_data = get_refresh_token(uid)
            is_active = is_user_active(uid)
            recent_login = is_recent_login(uid)
            
            if current_user_id and int(uid) == int(current_user_id):
                result[uid] = "green"
            elif refresh_token_data:
                result[uid] = "green"
            elif is_active:
                result[uid] = "yellow"
            # Если недавно логинился, но не активен - желтая точка
            elif recent_login:
                result[uid] = "yellow"
                # Добавляем в лог
                user_email = users_info.get(uid, {}).get("email", "unknown")
                user_role = users_info.get(uid, {}).get("role", "unknown")
                print(f"{uid:<5} | {user_email[:25]:<25} | {user_role:<10} | yellow     | TimeOut    | Yes          | Недавно логинился (желтая точка)")
            else:
                result[uid] = "gray"
    
    return result

@app.get("/auth/status")
async def auth_status(
    request: Request,
    token: Optional[str] = Depends(get_token_from_cookie)
):
    user_session = request.session.get("user")
    
    result = {
        "session_auth": bool(user_session),
        "jwt_auth": False
    }
    
    if token:
        try:
            # Проверяем валидность JWT
            jwt_payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            result["jwt_auth"] = True
            result["jwt_username"] = jwt_payload.get("sub")
            result["jwt_role"] = jwt_payload.get("role", "user")
        except JWTError:
            pass
    
    return result

# Эндпоинт для изменения роли пользователя (только для админа и суперадмина)
@app.post("/users/{user_id}/change-role", response_model=dict)
async def change_user_role(
    user_id: int, 
    role_data: dict = Body(...),
    request: Request = None,
    token: Optional[str] = Depends(get_token_from_cookie)
):
    # Проверяем, авторизован ли пользователь и имеет ли права
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Необходима аутентификация",
        )
    
    try:
        # Декодируем JWT токен
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        current_user_id = payload.get("id")
        current_user_role = payload.get("role")
        
        # Проверяем права пользователя
        if not current_user_role or current_user_role not in ["admin", "superadmin"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Недостаточно прав для изменения роли пользователя",
            )
        
        # Логирование для отладки
        print(f"Текущий пользователь: id={current_user_id}, роль={current_user_role}")
        print(f"Изменение роли для пользователя с ID={user_id}, новая роль={role_data.get('role')}")
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный токен аутентификации",
        )
    
    # Проверяем, не пытается ли пользователь изменить свою собственную роль
    if str(current_user_id) == str(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы не можете изменить свою собственную роль",
        )
    
    # Проверяем валидность новой роли
    new_role = role_data.get("role")
    if new_role not in ["user", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Недопустимая роль. Допустимые значения: 'user', 'admin'",
        )
    
    # Проверяем, что пользователь не пытается изменить роль суперадмина
    db = SessionLocal()
    try:
        user_to_change = get_user_by_id(db, user_id)
        if not user_to_change:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пользователь с ID {user_id} не найден",
            )
        
        # Логирование для отладки
        print(f"Пользователь для изменения: id={user_to_change.id}, роль={user_to_change.role}")
        
        # Запрещаем менять роль суперадмина
        if user_to_change.role == "superadmin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Невозможно изменить роль суперадмина",
            )
        
        # Обновляем роль пользователя
        updated_user = update_user_role(db, user_id, new_role)
        print(f"Роль пользователя успешно изменена на: {new_role}")
        
        return {
            "status": "success", 
            "message": f"Роль пользователя изменена на {new_role}",
            "user_id": user_id,
            "new_role": new_role
        }
    finally:
        db.close()

@app.get("/switch_account/{user_id}", response_class=RedirectResponse)
async def switch_account(
    request: Request,
    user_id: int,
    access_token: Optional[str] = Cookie(None),
    refresh_token: Optional[str] = Cookie(None)
):
    print("\n" + "*" * 50)
    print(f"*** Функция switch_account вызвана для user_id={user_id} ***")
    print("*" * 50 + "\n")
    # Проверка на суперадмина (ID = -1)
    if user_id == -1:
        # Получаем данные суперадмина из переменных окружения
        superadmin_username = os.getenv("SUPERADMIN_USERNAME")
        
        if not superadmin_username:
            return RedirectResponse(url="/login", status_code=303)
        
        # Обеспечиваем валидный email с символом @
        superadmin_email = os.getenv("SUPERADMIN_EMAIL", superadmin_username)
        if '@' not in superadmin_email:
            superadmin_email = 'superadmin@example.com'
        
        # Данные пользователя для токенов
        user_data = {
            "id": -1,
            "username": superadmin_username,
            "email": superadmin_email,
            "role": "superadmin"
        }
        
        # Создаем access_token для JWT-аутентификации
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "id": -1, 
                "role": "superadmin",
                "email": superadmin_email
            }, 
            expires_delta=access_token_expires
        )
        
        # Создаем refresh_token
        refresh_token, refresh_expires = create_refresh_token(-1)
        
        # Сохраняем refresh_token в Redis
        from redis_client import store_refresh_token
        store_refresh_token(-1, refresh_token, refresh_expires, user_data)
        
        # Удаляем домен из email для URL
        clean_username = clean_username_for_url(superadmin_username)
        response = RedirectResponse(url=f"/{clean_username}_superadmin/", status_code=303)
        
        # Устанавливаем cookie с токенами
        response.set_cookie(
            key="access_token",
            value=access_token,
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
        
        return response
    
    # Обычная обработка для других пользователей
    db = SessionLocal()
    try:
        # Получаем пользователя по ID
        user_to_switch = get_user_by_id(db, user_id)
        if not user_to_switch:
            return RedirectResponse(url="/login", status_code=303)

        # Проверяем текущего пользователя из access_token
        current_user_id = None
        current_user_email = None
        if access_token:
            try:
                payload = jwt.decode(access_token, SECRET_KEY, algorithms=[ALGORITHM])
                current_user_id = payload.get("id")
                current_user_email = payload.get("email")
            except JWTError:
                pass

        # Получаем email целевого пользователя
        target_email = user_to_switch.email

        from redis_client import get_refresh_token, is_user_active, delete_refresh_token
        target_refresh_token = get_refresh_token(user_id)
        is_target_active = is_user_active(user_id)

        print(f"\n=== Переключение аккаунта ===")
        print(f"Текущий пользователь: email={current_user_email} id={current_user_id}")
        print(f"Целевой пользователь: email={target_email} id={user_id}")

        current_refresh_token = get_refresh_token(current_user_id) if current_user_id else None
        print(f"Refresh token текущего пользователя: {'ЕСТЬ' if current_refresh_token else 'ОТСУТСТВУЕТ'}")

        # Всегда удаляем refresh_token текущего пользователя при переключении, если email отличается
        if current_user_email and current_user_email != target_email:
            print(f"[ВАЖНО] Удаляем refresh_token для пользователя email={current_user_email} (id={current_user_id}) перед переключением")
            result = delete_refresh_token(current_user_id)
            print(f"Результат удаления refresh_token: {result}")
            after_delete = get_refresh_token(current_user_id)
            print(f"Refresh token после удаления: {'ВСЕ ЕЩЕ СУЩЕСТВУЕТ!' if after_delete else 'УСПЕШНО УДАЛЕН'}")
        elif current_user_email == target_email:
            print(f"Не требуется удалять refresh_token, так как текущий пользователь совпадает с целевым (email совпадает)")
        else:
            print(f"Не требуется удалять refresh_token, так как текущий пользователь отсутствует (нет access token)")

        # Если переходим на аккаунт с серой точкой (оба токена истекли), перенаправляем на логин
        if not target_refresh_token and not is_target_active:
            print("Целевой аккаунт неактивен (серый статус): редирект на логин.")
            return RedirectResponse(url=f"/login?email={user_to_switch.email}", status_code=303)

        # Данные пользователя для токенов
        user_data = {
            "id": user_to_switch.id,
            "username": user_to_switch.username,
            "email": user_to_switch.email,
            "role": user_to_switch.role or "user"
        }

        # Создаем access_token для JWT-аутентификации
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        new_access_token = create_access_token(
            data={
                "id": user_to_switch.id,
                "role": user_to_switch.role or "user",
                "email": user_to_switch.email
            },
            expires_delta=access_token_expires
        )

        # Создаем новый refresh_token для целевого аккаунта
        new_refresh_token, refresh_expires = create_refresh_token(user_to_switch.id)

        # Сохраняем новый refresh_token в Redis для целевого аккаунта
        from redis_client import store_refresh_token
        store_refresh_token(user_to_switch.id, new_refresh_token, refresh_expires, user_data)

        # Удаляем домен из email для URL если username это email
        clean_username = clean_username_for_url(user_to_switch.username)
        response = RedirectResponse(url=f"/{clean_username}_{user_to_switch.role or 'user'}/", status_code=303)

        # Устанавливаем cookie с токенами
        response.set_cookie(
            key="access_token",
            value=new_access_token,
            httponly=True,
            max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            path="/",
            samesite="lax"
        )

        response.set_cookie(
            key="refresh_token",
            value=new_refresh_token,
            httponly=True,
            max_age=60 * 60 * 24 * 30,  # 30 дней
            path="/",
            samesite="lax"
        )

        return response
    finally:
        db.close()


@app.post("/forgot", response_class=HTMLResponse)
async def forgot_password_submit(request: Request, background_tasks: BackgroundTasks, email: str = Form(...)):
    db = SessionLocal()
    try:
        # Проверяем, существует ли пользователь с таким email
        user = db.query(models.User).filter(models.User.email == email).first()
        if not user:
            return templates.TemplateResponse(
                "password_reset/forgot.html", 
                {
                    "request": request, 
                    "error": "Пользователь с таким email не найден"
                }
            )
        
        # Генерируем токен для сброса пароля
        reset_token = str(uuid.uuid4())
        
        # Устанавливаем срок действия токена (24 часа)
        expires_at = datetime.utcnow() + timedelta(hours=24)
        
        # Проверяем, есть ли уже существующие записи для сброса пароля
        existing_reset = db.query(models.PasswordReset).filter(models.PasswordReset.user_id == user.id).first()
        
        if existing_reset:
            # Если существует - обновляем
            existing_reset.token = reset_token
            existing_reset.expires_at = expires_at
            existing_reset.is_used = False
        else:
            # Если не существует - создаем новую запись
            password_reset = models.PasswordReset(
                user_id=user.id,
                token=reset_token,
                expires_at=expires_at
            )
            db.add(password_reset)
        
        db.commit()
        
        # Генерируем URL для сброса пароля
        reset_url = f"{request.base_url}reset/{reset_token}"
        
        # Логирование для отладки
        print(f"Ссылка для сброса пароля: {reset_url}")
        
        # Отправляем email в фоновом режиме
        background_tasks.add_task(
            send_password_reset_email, 
            to_email=email, 
            reset_url=str(reset_url), 
            username=user.username
        )
        
        return templates.TemplateResponse(
            "password_reset/forgot.html", 
            {
                "request": request, 
                "success": "На вашу почту отправлена ссылка для сброса пароля"
            }
        )
        
    except Exception as e:
        print(f"Ошибка при обработке запроса на сброс пароля: {e}")
        return templates.TemplateResponse(
            "password_reset/forgot.html", 
            {
                "request": request, 
                "error": "Произошла ошибка при обработке запроса. Пожалуйста, попробуйте позже."
            }
        )
    finally:
        db.close()


@app.get("/reset/{reset_token}", response_class=HTMLResponse)
async def reset_password_page(request: Request, reset_token: str):
    db = SessionLocal()
    try:
        # Проверяем валидность токена
        password_reset = db.query(models.PasswordReset).filter(
            models.PasswordReset.token == reset_token,
            models.PasswordReset.is_used == False,
            models.PasswordReset.expires_at > datetime.utcnow()
        ).first()
        
        if not password_reset:
            return templates.TemplateResponse(
                "password_reset/reset.html", 
                {"request": request, "expired": True, "reset_token": reset_token}
            )
        
        return templates.TemplateResponse(
            "password_reset/reset.html", 
            {"request": request, "reset_token": reset_token}
        )
    finally:
        db.close()


@app.post("/reset/{reset_token}", response_class=HTMLResponse)
async def reset_password_submit(
    request: Request, 
    reset_token: str, 
    password: str = Form(...), 
    confirm_password: str = Form(...)
):
    db = SessionLocal()
    try:
        # Проверяем совпадение паролей
        if password != confirm_password:
            return templates.TemplateResponse(
                "password_reset/reset.html", 
                {
                    "request": request, 
                    "error": "Пароли не совпадают", 
                    "reset_token": reset_token
                }
            )
        
        # Проверяем, что пароль достаточно длинный
        if len(password) < 6:
            return templates.TemplateResponse(
                "password_reset/reset.html", 
                {
                    "request": request, 
                    "error": "Пароль должен содержать не менее 6 символов", 
                    "reset_token": reset_token
                }
            )
        
        # Проверяем валидность токена
        password_reset = db.query(models.PasswordReset).filter(
            models.PasswordReset.token == reset_token,
            models.PasswordReset.is_used == False,
            models.PasswordReset.expires_at > datetime.utcnow()
        ).first()
        
        if not password_reset:
            return templates.TemplateResponse(
                "password_reset/reset.html", 
                {"request": request, "expired": True, "reset_token": reset_token}
            )
        
        # Получаем пользователя
        user = db.query(models.User).filter(models.User.id == password_reset.user_id).first()
        if not user:
            return templates.TemplateResponse(
                "password_reset/reset.html", 
                {
                    "request": request, 
                    "error": "Пользователь не найден", 
                    "reset_token": reset_token
                }
            )
        
        # Обновляем пароль и хешируем его
        user.hashed_password = models.User.get_password_hash(password)
        
        # Отмечаем токен как использованный
        password_reset.is_used = True
        
        db.commit()
        
        # Перенаправляем на страницу входа с сообщением об успешной смене пароля
        # Вместо использования сессии, передаем параметр в URL
        response = RedirectResponse(url="/login?password_reset_success=true")
        response.status_code = 303
        return response
        
    except Exception as e:
        print(f"Ошибка при сбросе пароля: {e}")
        return templates.TemplateResponse(
            "password_reset/reset.html", 
            {
                "request": request, 
                "error": "Произошла ошибка при сбросе пароля. Пожалуйста, попробуйте позже.",
                "reset_token": reset_token
            }
        )
    finally:
        db.close()
