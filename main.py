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

# Добавляем импорт роутера users
from routers import contacts, groups, db_utils, email_verification, users
from database import SessionLocal, engine, Base, is_render_environment, is_docker_environment
from crud import get_user_by_username, update_user_role, get_user_by_id
import models
import os
from dotenv import load_dotenv
# Импортируем функции из auth.py
from auth import pwd_context, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES, SECRET_KEY, ALGORITHM
# Добавляем импорт нашей новой функции отправки email
from utils_email_verif import send_verification_email, send_password_reset_email
# Импортируем функции для rate limiting
from rate_limiter import init_limiter

load_dotenv()

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(contacts.router, prefix="/contacts")
app.include_router(groups.router, prefix="/groups")
app.include_router(db_utils.router, prefix="/db")
# Добавляем подключение роутера users
app.include_router(users.router)
# Изменяем маршрут для email_verification, убирая префикс /verify,
# чтобы /auth/register был доступен
app.include_router(email_verification.router)

# Создаем таблицы базы данных при запуске приложения
@app.on_event("startup")
async def startup_db_and_tables():
    logger.info("Инициализация приложения...")
    
    # Добавляем задержку при запуске на Render.com или в Docker,
    # чтобы дать БД время инициализироваться
    if is_render_environment() or is_docker_environment():
        logger.info("Обнаружено окружение Render.com или Docker, ожидаем инициализацию внешних сервисов...")
        time.sleep(5)  # Даем время для инициализации внешних сервисов
    
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
            
            # Если email не содержит @, добавляем домен по умолчанию
            if superadmin_email and '@' not in superadmin_email:
                superadmin_email = f"{superadmin_email}@example.com"
            
            if superadmin_username and superadmin_password:
                # Проверяем, существует ли уже супер-админ
                existing_admin = get_user_by_username(db, superadmin_username)
                
                if not existing_admin:
                    logger.info(f"Создаем учетную запись супер-админа: {superadmin_username}")
                    # Создаем запись супер-админа в базе данных
                    hashed_password = models.User.get_password_hash(superadmin_password)
                    superadmin = models.User(
                        username=superadmin_username,
                        email=superadmin_email,
                        hashed_password=hashed_password,
                        role="superadmin",
                        is_verified=True  # Супер-админ не требует верификации
                    )
                    db.add(superadmin)
                    db.commit()
                    logger.info("Учетная запись супер-админа успешно создана")
                else:
                    logger.info("Учетная запись супер-админа уже существует")
        except Exception as e:
            logger.error(f"Ошибка при создании супер-админа: {e}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Ошибка при работе с базой данных: {e}")
    
    # Инициализация rate limiter
    try:
        await init_limiter()
    except Exception as e:
        logger.error(f"Ошибка при инициализации rate limiter: {e}")
        logger.info("Приложение продолжит работу без ограничения запросов (rate limiting)")

# Настройка сессий
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SECRET_KEY", "default_secret_key"))

# Настройка шаблонов
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Функция для обработки имени пользователя для URL (удаление домена email)
def clean_username_for_url(username: str) -> str:
    if '@' in username:
        return username.split('@')[0]  # Берем только часть до @
    return username

# Функция для получения токена из cookie
async def get_token_from_cookie(access_token: Optional[str] = Cookie(None)):
    if access_token and access_token.startswith("Bearer "):
        return access_token[7:]  # Убираем "Bearer " префикс
    return None

# Обновление редиректов для использования относительных URL
@app.get("/")
async def root(request: Request):
    user = request.session.get("user")
    if user and "username" in user:
        role = user.get("role", "user")
        # Удаляем домен из email для URL
        clean_username = clean_username_for_url(user['username'])
        return RedirectResponse(url=f"/{clean_username}_{role}/", status_code=303)
    return RedirectResponse(url="/login", status_code=303)

@app.get("/login")
async def login(request: Request):
    # Проверяем, было ли успешное изменение пароля
    password_reset_success = request.session.pop("password_reset_success", False)
    
    return templates.TemplateResponse(
        "login.html", 
        {
            "request": request, 
            "password_reset_success": password_reset_success
        }
    )

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
            
            # Сохраняем данные суперадмина в сессии с валидным ID
            request.session["user"] = {
                "id": superadmin_id,  # Используем -1 как специальный ID для суперадмина, если нет в БД
                "username": username,
                "email": username,  # Добавляем email для суперадмина
                "role": "superadmin"
            }
            
            # Создаем JWT-токен для API-запросов суперадмина
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": username, "id": superadmin_id, "role": "superadmin", "email": username}, 
                expires_delta=access_token_expires
            )
            
            # Удаляем домен из email для URL
            clean_username = clean_username_for_url(username)
            response = RedirectResponse(url=f"/{clean_username}_superadmin/", status_code=303)
            
            # Устанавливаем cookie с токеном для суперадмина
            response.set_cookie(
                key="access_token",
                value=f"Bearer {access_token}",
                httponly=True,
                max_age=1800,  # 30 минут в секундах
                path="/"  # Важно - токен будет доступен для всех путей
            )
            
            return response
        
        # Проверка для обычных пользователей
        elif user and pwd_context.verify(password, user.hashed_password):
            # Проверка, подтвержден ли email
            if not user.is_verified:
                return templates.TemplateResponse("login.html", {"request": request, "error": "Пожалуйста, подтвердите ваш email перед входом"})
            
            # Сохраняем данные пользователя в сессии
            request.session["user"] = {
                "id": user.id,
                "username": user.username,
                "email": user.email,  # Добавляем email пользователя
                "role": user.role or "user"  # Используем роль из БД или по умолчанию "user"
            }
            
            # Создаем JWT-токен для API-запросов
            access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = create_access_token(
                data={"sub": user.username, "id": user.id, "role": user.role or "user", "email": user.email}, 
                expires_delta=access_token_expires
            )
            
            # Удаляем домен из email для URL если username это email
            clean_username = clean_username_for_url(user.username)
            response = RedirectResponse(url=f"/{clean_username}_{user.role or 'user'}/", status_code=303)
            
            # Устанавливаем cookie с токеном (исправлено)
            response.set_cookie(
                key="access_token",
                value=f"Bearer {access_token}",
                httponly=True,
                max_age=1800,  # 30 минут в секундах
                path="/"  # Важно - токен будет доступен для всех путей
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
    request.session["user"] = {"username": username, "role": "user"}
    return RedirectResponse(f"/{username}_user/", status_code=302)

@app.get("/{username}_{role}/", response_class=HTMLResponse)
def user_dashboard(
    request: Request, 
    username: str, 
    role: str,
    token: Optional[str] = Depends(get_token_from_cookie)
):
    user = request.session.get("user")
    # Проверка на соответствие пользователя в сессии
    # Нам нужно сравнить часть до @ в сессионном имени пользователя
    if not user:
        return RedirectResponse("/login")
    
    session_clean_username = clean_username_for_url(user["username"])
    if session_clean_username != username or user["role"] != role:
        return RedirectResponse("/login")
    
    # Выводим отладочную информацию о токене в консоль
    print(f"Token from cookie: {token[:10]}..." if token else "No token")
    
    # TODO: Получить контакты только этого пользователя
    # contacts = crud.get_contacts_for_user(username)
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user,
        # "contacts": contacts,
    })

@app.get("/current_user", response_class=HTMLResponse)
def current_user(request: Request):
    # TODO: Если залогинено несколько пользователей — показать выбор
    return templates.TemplateResponse("current_user.html", {"request": request})

@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    response = RedirectResponse("/login")
    # Удаляем cookie с токеном
    response.delete_cookie("access_token", path="/")
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
    if not request.session.get("user") or request.session["user"].get("role") not in ["admin", "superadmin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для изменения роли пользователя",
        )
    
    # Получаем ID текущего пользователя из сессии
    current_user_id = request.session["user"].get("id")
    current_user_role = request.session["user"].get("role")
    
    # Логирование для отладки
    print(f"Текущий пользователь: id={current_user_id}, роль={current_user_role}")
    print(f"Изменение роли для пользователя с ID={user_id}, новая роль={role_data.get('role')}")
    
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

# Эндпоинт для переключения между аккаунтами
@app.get("/switch_account/{user_id}", response_class=RedirectResponse)
async def switch_account(
    request: Request,
    user_id: int
):
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
        
        # Сохраняем данные суперадмина в сессии
        request.session["user"] = {
            "id": -1,
            "username": superadmin_username,
            "email": superadmin_email,
            "role": "superadmin"
        }
        
        # Создаем JWT-токен для API-запросов суперадмина
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": superadmin_username, 
                "id": -1, 
                "role": "superadmin",
                "email": superadmin_email
            }, 
            expires_delta=access_token_expires
        )
        
        # Удаляем домен из email для URL
        clean_username = clean_username_for_url(superadmin_username)
        response = RedirectResponse(url=f"/{clean_username}_superadmin/", status_code=303)
        
        # Устанавливаем cookie с токеном для суперадмина
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=1800,  # 30 минут в секундах
            path="/"
        )
        
        return response
    
    # Обычная обработка для других пользователей
    db = SessionLocal()
    try:
        # Получаем пользователя по ID
        user_to_switch = get_user_by_id(db, user_id)
        if not user_to_switch:
            return RedirectResponse(url="/login", status_code=303)
        
        # Сохраняем данные пользователя в сессии
        request.session["user"] = {
            "id": user_to_switch.id,
            "username": user_to_switch.username,
            "email": user_to_switch.email,
            "role": user_to_switch.role or "user"
        }
        
        # Создаем новый JWT-токен для API-запросов
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={
                "sub": user_to_switch.username, 
                "id": user_to_switch.id, 
                "role": user_to_switch.role or "user",
                "email": user_to_switch.email
            }, 
            expires_delta=access_token_expires
        )
        
        # Удаляем домен из email для URL если username это email
        clean_username = clean_username_for_url(user_to_switch.username)
        response = RedirectResponse(url=f"/{clean_username}_{user_to_switch.role or 'user'}/", status_code=303)
        
        # Устанавливаем cookie с токеном
        response.set_cookie(
            key="access_token",
            value=f"Bearer {access_token}",
            httponly=True,
            max_age=1800,  # 30 минут в секундах
            path="/"
        )
        
        return response
    finally:
        db.close()

# Добавляем маршруты для восстановления пароля
@app.get("/forgot", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("password_reset/forgot.html", {"request": request})


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
        response = RedirectResponse(url="/login")
        response.status_code = 303
        request.session["password_reset_success"] = True
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
