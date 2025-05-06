import psycopg2
import os
from dotenv import load_dotenv
import re
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Получаем параметры подключения к базе данных
def get_db_params():
    # Первый приоритет: DATABASE_URL (например, от Render.com)
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        # Для совместимости, если URL начинается с 'postgres://',
        # заменяем на 'postgresql://'
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        
        # Извлекаем параметры из строки подключения
        # postgresql://username:password@host:port/dbname
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
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_password = os.getenv('DB_PASSWORD')
    db_host = os.getenv('DB_HOST', 'postgres')  # По умолчанию используем 'postgres' для Docker
    db_port = os.getenv('DB_PORT', '5432')
    
    return {
        'host': db_host,
        'user': db_user,
        'password': db_password,
        'db_name': db_name,
        'port': db_port
    }

# Получаем параметры подключения
params = get_db_params()

try:
    logger.info(f"Connecting to PostgreSQL server at {params['host']}:{params['port']} as {params['user']}...")
    
    # Подключаемся к postgres для создания новой базы
    conn = psycopg2.connect(
        dbname='postgres', 
        user=params['user'], 
        password=params['password'], 
        host=params['host'],
        port=params['port']
    )
    conn.autocommit = True
    cur = conn.cursor()

    try:
        logger.info(f"Attempting to create database '{params['db_name']}'...")
        cur.execute(f"CREATE DATABASE {params['db_name']}")
        logger.info(f"Database '{params['db_name']}' created successfully!")
    except psycopg2.errors.DuplicateDatabase:
        logger.info(f"Database '{params['db_name']}' already exists.")
    finally:
        cur.close()
        conn.close()
except Exception as e:
    logger.error(f"Error connecting to database: {e}")
    logger.error("Make sure your database connection parameters are correct.")
