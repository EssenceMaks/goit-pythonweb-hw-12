from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
import logging
import sys

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Проверка, запущено ли приложение на Render.com
def is_render_environment():
    return os.environ.get('RENDER') == 'true' or os.environ.get('RENDER_EXTERNAL_HOSTNAME') is not None

# Проверка, запущено ли приложение в Docker
def is_docker_environment():
    # Несколько способов определения Docker-контейнера
    # 1. Проверяем наличие файла /.dockerenv, который есть в Docker контейнерах
    docker_env = os.path.exists("/.dockerenv")
    
    # 2. Проверяем переменную окружения, которую можем сами установить в Dockerfile или docker-compose
    docker_env_var = os.environ.get('DOCKER_ENV') == 'true'
    
    # 3. Проверяем, является ли hostname контейнерным ID (обычно короткий хеш)
    try:
        with open('/proc/self/cgroup', 'r') as f:
            docker_cgroup = any('docker' in line for line in f)
    except:
        docker_cgroup = False
    
    # 4. Проверяем наличие переменной окружения DB_HOST=db (типичная для docker-compose)
    docker_db_host = os.environ.get('DB_HOST') == 'db'
    
    # Используем один из этих методов
    return docker_env or docker_env_var or docker_cgroup or docker_db_host

# Получаем URL для подключения к базе данных
def get_database_url():
    # Первый приоритет: прямой URL из переменной окружения DATABASE_URL
    database_url = os.environ.get("DATABASE_URL")
    
    # Если приложение запущено в Docker
    if is_docker_environment():
        # В Docker используем имя сервиса db вместо localhost
        logger.info("Запуск в Docker контейнере")
        
        # Если DATABASE_URL задан явно, используем его
        if database_url:
            logger.info("Используется указанный DATABASE_URL для Docker")
        else:
            # Иначе собираем URL из отдельных параметров или используем дефолт
            db_name = os.getenv("DB_NAME", "contacts_db")
            db_user = os.getenv("DB_USER", "postgres")
            db_password = os.getenv("DB_PASSWORD", "postgres")
            db_host = os.getenv("DB_HOST", "db")
            db_port = os.getenv("DB_PORT", "5432")
            
            database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            logger.info(f"Используется сконструированный URL базы данных для Docker")
    
    # Если приложение запущено на Render.com
    elif is_render_environment():
        if not database_url:
            # Проверяем, есть ли база данных внутри Render.com
            if os.environ.get("RENDER_DATABASE_URL"):
                logger.info("Найдена переменная RENDER_DATABASE_URL, используем её")
                database_url = os.environ.get("RENDER_DATABASE_URL")
            else:
                logger.error("DATABASE_URL не задан в переменных окружения на Render.com")
                logger.error("Приложение не может работать без подключения к базе данных")
                return None
    
    # Для локальной разработки
    else:
        # Если URL не задан, собираем из отдельных параметров
        if not database_url:
            db_name = os.getenv("DB_NAME")
            db_user = os.getenv("DB_USER")
            db_password = os.getenv("DB_PASSWORD")
            db_host = os.getenv("DB_HOST", "localhost")
            db_port = os.getenv("DB_PORT", "5432")
            
            if db_name and db_user and db_password:
                database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
            else:
                # Для локальной разработки используем значение по умолчанию
                logger.warning("DATABASE_URL не задан в переменных окружения, используется значение по умолчанию")
                database_url = "postgresql://postgres:postgres@localhost:5432/contacts_db"
    
    # Для совместимости с SQLAlchemy, если URL начинается с 'postgres://'
    if database_url and database_url.startswith("postgres://"):
        database_url = database_url.replace("postgres://", "postgresql://", 1)
    
    # Безопасно выводим URL без пароля для отладки
    if database_url:
        safe_url_parts = database_url.split('@')
        if len(safe_url_parts) > 1:
            credentials = safe_url_parts[0].split(':')
            if len(credentials) > 2:
                safe_url = f"{credentials[0]}:{credentials[1]}:****@{safe_url_parts[1]}"
                logger.info(f"Connecting to database: {safe_url}")
            else:
                logger.info(f"Connecting to database: {database_url.split('@')[0]}:****@{database_url.split('@')[1]}")
    
    return database_url

# Создаем глобальный URL для базы данных
DATABASE_URL = get_database_url()

# Проверка наличия допустимого URL для подключения к базе данных
if DATABASE_URL is None:
    logger.error("Не удалось получить URL для подключения к базе данных")
    if is_render_environment():
        logger.error("Убедитесь, что переменная DATABASE_URL задана в настройках Render.com")
        logger.error("Приложение не может работать без подключения к базе данных")
        sys.exit(1)  # Завершаем приложение с ошибкой, если нет URL для БД в продакшене

# Вывод информации об окружении
if is_render_environment():
    logger.info("Приложение запущено на платформе Render.com")
    logger.info("RENDER_EXTERNAL_HOSTNAME: " + str(os.environ.get('RENDER_EXTERNAL_HOSTNAME')))
elif is_docker_environment():
    logger.info("Приложение запущено в Docker контейнере")
    # Выводим информацию о параметрах подключения к БД
    logger.info(f"DB_HOST: {os.getenv('DB_HOST', 'db')}")
    logger.info(f"DB_PORT: {os.getenv('DB_PORT', '5432')}")
    logger.info(f"DB_NAME: {os.getenv('DB_NAME', 'contacts_db')}")
else:
    logger.info("Приложение запущено в режиме локальной разработки")

# Создаем движок базы данных с подробной отладочной информацией
engine = create_engine(
    DATABASE_URL,
    pool_size=5,
    max_overflow=10,
    pool_recycle=3600,
    pool_pre_ping=True,  # Важно: проверяет соединение перед использованием
    # echo=(is_render_environment() or is_docker_environment())  # Включаем подробные логи SQL в продакшен режиме для отладки
    echo=False #  Выключаем вывод SQL-запросов для уменьшения шума в логах
)

# Создаем фабрику сессий
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Класс для моделей SQLAlchemy
Base = declarative_base()

# Функция для получения соединения с БД в виде зависимости FastAPI
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
