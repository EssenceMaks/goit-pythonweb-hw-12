from fastapi import APIRouter, HTTPException, Request, Depends, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.exc import OperationalError
from sqlalchemy import inspect, text
from database import engine, SessionLocal, is_docker_environment, is_render_environment
import models
from faker import Faker
import psycopg2
import os
import re
from urllib.parse import urlparse
from typing import Optional

# Создаем специальную схему OAuth2, которая не вызывает ошибку при отсутствии токена
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token", auto_error=False)

# Удаляем префикс "/db", так как он уже указан в main.py при подключении роутера
router = APIRouter(tags=["Database Utils"])
faker = Faker()

# Функция для получения параметров подключения к базе данных
def get_db_params():
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        # Исправляем URL для совместимости
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
            
            return {
                'host': host,
                'user': user,
                'password': password,
                'db_name': db_name,
                'port': port
            }
    
    # Второй приоритет: отдельные переменные окружения
    db_name = os.getenv('DB_NAME', 'contacts_db')
    db_user = os.getenv('DB_USER', 'postgres')
    db_password = os.getenv('DB_PASSWORD', 'postgres')
    
    # Определяем host в зависимости от окружения
    if is_docker_environment():
        db_host = os.getenv('DB_HOST', 'db')  # 'db' - для Docker
    else:
        db_host = os.getenv('DB_HOST', 'localhost')  # 'localhost' - для локальной разработки
        
    db_port = os.getenv('DB_PORT', '5432')
    
    return {
        'host': db_host,
        'user': db_user,
        'password': db_password,
        'db_name': db_name,
        'port': db_port
    }

@router.get("/status")
def db_status():
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if not tables:
            return {"status": "empty", "message": "База є, але таблиць немає."}
        return {"status": "ok", "tables": tables}
    except OperationalError:
        return {"status": "fail", "message": "Немає підключення до бази даних."}

@router.post("/init")
def db_init():
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if tables:
            return {"status": "exists", "message": "Таблиці вже створені."}
        models.Base.metadata.create_all(bind=engine)
        return {"status": "created", "message": "Таблиці успішно створені."}
    except OperationalError:
        raise HTTPException(status_code=500, detail="Немає підключення до бази даних.")

@router.post("/fill-fake")
def db_fill_fake(n: int = 10, request: Request = None):
    try:
        db = SessionLocal()
        inspector = inspect(engine)
        if not inspector.get_table_names():
            models.Base.metadata.create_all(bind=engine)
        from models import Contact, PhoneNumber, User
        import random
        
        # Определяем user_id для контактов
        user_id = None
        current_user = None
        
        # Получаем данные текущего пользователя из сессии
        if request and hasattr(request, 'session'):
            current_user = request.session.get('user')
            
        if current_user:
            # Проверяем, является ли пользователь суперадмином с ID = -1
            if current_user.get('role') == 'superadmin' and current_user.get('id') == -1:
                print("Обнаружен суперадмин с ID = -1, создаем или получаем его запись в БД")
                
                # Ищем или создаем пользователя-суперадмина в базе данных
                superadmin = db.query(User).filter_by(role='superadmin').first()
                if not superadmin:
                    # Создаем запись суперадмина в таблице users
                    superadmin_username = current_user.get('username', 'superadmin')
                    # Обязательно используем валидный email с символом @
                    superadmin_email = current_user.get('email')
                    
                    # Проверяем наличие @ в email, иначе используем дефолтный с @
                    if not superadmin_email or '@' not in superadmin_email:
                        superadmin_email = 'superadmin@example.com'
                    
                    superadmin = User(
                        username=superadmin_username,
                        email=superadmin_email,
                        hashed_password='$2b$12$gvvnkVD.WCFqTgWZr0BMiOQ/HwgKGw0Mb9/PIvJ8uJ8KsNV7AqgG6',  # хешированный пароль (не для входа)
                        role='superadmin',
                        is_verified=True
                    )
                    db.add(superadmin)
                    db.commit()
                    db.refresh(superadmin)
                
                # Используем ID реального пользователя-суперадмина из БД
                user_id = superadmin.id
                print(f"Создаем контакты для суперадмина с ID из БД: {user_id}")
            
            # Обычные пользователи и админы
            elif current_user.get('id') and current_user.get('id') != -1:
                user_id = current_user.get('id')
                print(f"Создаем контакты для пользователя ID={user_id}")
        
        # Если не удалось определить пользователя, берем первого из базы (запасной вариант)
        if not user_id:
            user = db.query(User).first()
            if not user:
                user = User(
                    username='testuser',
                    email='testuser@example.com',
                    hashed_password='$2b$12$gvvnkVD.WCFqTgWZr0BMiOQ/HwgKGw0Mb9/PIvJ8uJ8KsNV7AqgG6',
                    role='user',
                    is_verified=True
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            user_id = user.id
            print(f"Создаем контакты для первого пользователя ID={user_id} (запасной вариант)")
            
        # Создаем контакты с полученным user_id
        import logging
        for _ in range(n):
            first_name = faker.first_name() or "John"
            last_name = faker.last_name() or "Doe"
            email = faker.unique.email() or f"user{random.randint(1000,9999)}@example.com"
            contact = Contact(
                user_id=user_id,
                first_name=first_name,
                last_name=last_name,
                email=email,
                birthday=faker.date_of_birth(minimum_age=18, maximum_age=80),
                extra_info=faker.sentence()
            )
            db.add(contact)
            logging.info(f"Fake contact: {first_name} {last_name} {email}")
            db.flush()
            for _ in range(random.randint(1, 3)):
                import re
                raw_number = faker.phone_number()
                cleaned_number = re.sub(r'[^0-9\-+() ]', '', raw_number)
                if len(cleaned_number) < 7:
                    cleaned_number = '+380' + faker.msisdn()[:9]
                pn = PhoneNumber(
                    number=cleaned_number,
                    label=random.choice(["home", "work", "mobile"]),
                    contact_id=contact.id
                )
                db.add(pn)
        db.commit()
        return {"status": "ok", "message": f"Додано {n} випадкових контактів для user_id={user_id}."}
    except OperationalError:
        raise HTTPException(status_code=500, detail="Немає підключення до бази даних.")
    except Exception as e:
        db.rollback()
        print(f"Ошибка при создании контактов: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

@router.post("/clear")
def db_clear(request: Request = None):
    try:
        db = SessionLocal()
        from models import Contact, PhoneNumber, Avatar, Photo, User
        
        # Определяем для какого пользователя удаляем контакты
        user_id = None
        is_admin = False
        
        # Получаем информацию о текущем пользователе
        if request and hasattr(request, 'session'):
            current_user = request.session.get('user')
            if current_user:
                role = current_user.get('role')
                is_admin = role in ['admin', 'superadmin']
                
                # Проверка на суперадмина с ID = -1
                if role == 'superadmin' and current_user.get('id') == -1:
                    print("Обнаружен суперадмин с ID = -1")
                    # Ищем суперадмина в базе данных
                    superadmin = db.query(User).filter_by(role='superadmin').first()
                    if superadmin:
                        user_id = superadmin.id
                        print(f"Найден суперадмин с реальным ID={user_id}")
                    else:
                        print("Суперадмин не найден в базе данных")
                else:
                    user_id = current_user.get('id')
                
        # Если удаляет админ или суперадмин - удаляем все контакты
        if is_admin:
            print(f"Администратор (ID={user_id}, role={role}) удаляет все контакты")
            db.query(PhoneNumber).delete()
            db.query(Avatar).delete()
            db.query(Photo).delete()
            db.query(Contact).delete()
            msg = "Всі контакти видалені адміністратором."
        # Если это обычный пользователь или суперадмин удаляет свои контакты
        elif user_id:
            print(f"Пользователь ID={user_id} удаляет свои контакты")
            # Получаем все контакты пользователя
            user_contacts = db.query(Contact).filter(Contact.user_id == user_id).all()
            
            # Получаем ID всех контактов пользователя
            contact_ids = [contact.id for contact in user_contacts]
            
            if contact_ids:
                # Удаляем связанные записи телефонов, аватаров и фото
                db.query(PhoneNumber).filter(PhoneNumber.contact_id.in_(contact_ids)).delete(synchronize_session=False)
                db.query(Avatar).filter(Avatar.contact_id.in_(contact_ids)).delete(synchronize_session=False)
                db.query(Photo).filter(Photo.contact_id.in_(contact_ids)).delete(synchronize_session=False)
                
                # Удаляем сами контакты
                db.query(Contact).filter(Contact.user_id == user_id).delete()
            
            msg = f"Всі ваші контакти видалені. Видалено {len(contact_ids)} контактів."
        else:
            # Если не удалось определить пользователя - не удаляем ничего
            return {"status": "error", "message": "Необхідна авторизація для видалення контактів."}
            
        db.commit()
        return {"status": "ok", "message": msg}
    except OperationalError:
        raise HTTPException(status_code=500, detail="Немає підключення до бази даних.")
    except Exception as e:
        db.rollback()
        print(f"Ошибка при удалении контактов: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        db.close()

# Обновляем endpoint, чтобы он работал даже без авторизации
@router.get("/check-state")
def db_check_state(token: Optional[str] = Depends(optional_oauth2_scheme)):
    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        if not tables:
            return {"status": "no_tables", "message": "База існує, контактів 0 (тобто немає, створіть контакти)"}
        # Проверяем количество контактов
        db = SessionLocal()
        try:
            count = db.execute(text("SELECT COUNT(*) FROM contacts")).scalar()
            if count == 0:
                return {"status": "no_contacts", "message": "База існує, контактів 0 (тобто немає, створіть контакти)"}
            return {"status": "ok", "count": count}
        except Exception as e:
            return {"status": "error", "message": str(e)}
        finally:
            db.close()
    except OperationalError:
        return {"status": "no_db", "message": "База не існує, створіть базу"}

@router.post("/create-db")
def create_database(request: Request):
    # Получаем параметры для подключения к базе данных
    params = get_db_params()
    
    if not params['password'] or params['password'] == "YOUR_PASSWORD":
        return {"status": "noenv", "message": "Для створення бази встановіть налаштування в коді за допомогою <br> env.example та перезавантажте сервер"}
    
    try:
        # Подключаемся к postgres для создания новой базы
        conn = psycopg2.connect(
            dbname='postgres',
            user=params['user'],
            password=params['password'],
            host=params['host'],
            port=params['port'],
            connect_timeout=10
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        # Проверяем существование базы данных
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (params['db_name'],))
        exists = cur.fetchone()
        
        if not exists:
            # Создаем базу данных, если она не существует
            cur.execute(f"CREATE DATABASE {params['db_name']}")
            cur.close()
            conn.close()
            return {"status": "created", "message": f"База даних '{params['db_name']}' створена."}
        else:
            cur.close()
            conn.close()
            return {"status": "exists", "message": f"База даних '{params['db_name']}' вже існує."}
    except psycopg2.OperationalError as e:
        error_msg = str(e)
        if "connect" in error_msg.lower() or "unable to open database" in error_msg.lower():
            if is_docker_environment():
                return {"status": "error", "message": f"Помилка підключення до сервера PostgreSQL. Переконайтеся, що сервіс 'db' запущений: {error_msg}"}
            else:
                return {"status": "error", "message": f"Помилка підключення до сервера PostgreSQL: {error_msg}"}
        return {"status": "error", "message": f"Операційна помилка: {error_msg}"}
    except Exception as e:
        return {"status": "error", "message": f"Помилка: {str(e)}"}

@router.post("/drop-db")
def drop_database(request: Request):
    # Получаем параметры подключения
    params = get_db_params()
    
    try:
        # Подключаемся к postgres для удаления существующей базы
        conn = psycopg2.connect(
            dbname='postgres',
            user=params['user'],
            password=params['password'],
            host=params['host'],
            port=params['port'],
            connect_timeout=10
        )
        conn.autocommit = True
        cur = conn.cursor()
        
        # Проверяем существование базы данных
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (params['db_name'],))
        exists = cur.fetchone()
        
        if not exists:
            cur.close()
            conn.close()
            return {"status": "not_found", "message": f"База даних '{params['db_name']}' не знайдена."}
        
        # Отключаем пользователей от базы данных
        cur.execute(f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s", (params['db_name'],))
        
        # Удаляем базу данных
        cur.execute(f"DROP DATABASE {params['db_name']}")
        cur.close()
        conn.close()
        return {"status": "dropped", "message": f"База даних '{params['db_name']}' видалена."}
    except psycopg2.OperationalError as e:
        error_msg = str(e)
        if "connect" in error_msg.lower():
            if is_docker_environment():
                return {"status": "error", "message": f"Помилка підключення до сервера PostgreSQL. Переконайтеся, що сервіс 'db' запущений: {error_msg}"}
            else:
                return {"status": "error", "message": f"Помилка підключення до сервера PostgreSQL: {error_msg}"}
        return {"status": "error", "message": f"Операційна помилка: {error_msg}"}
    except psycopg2.errors.InvalidCatalogName:
        return {"status": "not_found", "message": f"База даних '{params['db_name']}' не знайдена."}
    except Exception as e:
        return {"status": "error", "message": f"Помилка: {str(e)}"}
