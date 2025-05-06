from database import engine
from models import Base

def initialize_database():
    print("Initializing database schema...")
    Base.metadata.create_all(bind=engine)
    print("Database schema initialized successfully!")

if __name__ == "__main__":
    initialize_database()