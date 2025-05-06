from sqlalchemy import Column, Integer, String, Date, Text, ForeignKey, Table, DateTime, Boolean, func
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base
from passlib.context import CryptContext

# Создаём контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Association table for many-to-many Contact <-> Group
contact_group = Table(
    'contact_group', Base.metadata,
    Column('contact_id', Integer, ForeignKey('contacts.id'), primary_key=True),
    Column('group_id', Integer, ForeignKey('groups.id'), primary_key=True)
)

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, nullable=False, index=True)
    email = Column(String, unique=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    role = Column(String, default='user')  # 'admin' or 'user'
    is_verified = Column(Boolean, default=False)
    verification_code = Column(String, nullable=True)

    avatars = relationship('UserAvatar', back_populates='user', cascade="all, delete-orphan")
    contacts = relationship('Contact', back_populates='user', cascade="all, delete-orphan")
    password_resets = relationship("PasswordReset", back_populates="user", cascade="all, delete-orphan")
    
    # Методы для работы с паролем
    @staticmethod
    def get_password_hash(password):
        return pwd_context.hash(password)
        
    def verify_password(self, plain_password):
        return pwd_context.verify(plain_password, self.hashed_password)

class UserAvatar(Base):
    __tablename__ = 'user_avatars'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    file_path = Column(String, nullable=False)
    cloudinary_public_id = Column(String, nullable=True)  # Добавляем поле для хранения public_id из Cloudinary
    is_approved = Column(Integer, default=0)  # 0 - not approved, 1 - approved
    is_main = Column(Integer, default=0)      # 0 - not main, 1 - main
    request_type = Column(String, default='upload')  # 'upload' or 'set_main'
    request_status = Column(String, default='pending')  # 'pending', 'approved', 'rejected'
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship('User', back_populates='avatars')
    messages = relationship('AvatarRequestMessage', back_populates='avatar', cascade="all, delete-orphan")

class AvatarRequestMessage(Base):
    __tablename__ = 'avatar_request_messages'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)  # кто отправил запрос
    avatar_id = Column(Integer, ForeignKey('user_avatars.id'), nullable=False)
    message = Column(Text, nullable=True)
    status = Column(String, default='pending')  # 'pending', 'approved', 'rejected'
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_by = Column(Integer, ForeignKey('users.id'), nullable=True)  # кто подтвердил (админ)
    reviewed_at = Column(DateTime, nullable=True)

    avatar = relationship('UserAvatar', back_populates='messages')
    user = relationship('User', foreign_keys=[user_id])
    reviewer = relationship('User', foreign_keys=[reviewed_by])

class Contact(Base):
    __tablename__ = 'contacts'
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String)
    email = Column(String, nullable=False)
    birthday = Column(Date, nullable=False)
    extra_info = Column(Text)

    user = relationship('User', back_populates='contacts')
    phone_numbers = relationship('PhoneNumber', back_populates='contact', cascade="all, delete-orphan")
    avatars = relationship('Avatar', back_populates='contact', cascade="all, delete-orphan")
    photos = relationship('Photo', back_populates='contact', cascade="all, delete-orphan")
    groups = relationship('Group', secondary=contact_group, back_populates='contacts')

class PhoneNumber(Base):
    __tablename__ = 'phone_numbers'
    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey('contacts.id'))
    number = Column(String, nullable=False)
    label = Column(String, default="other")  # e.g., home, work, mobile

    contact = relationship('Contact', back_populates='phone_numbers')

class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False)
    contacts = relationship('Contact', secondary=contact_group, back_populates='groups')

class Avatar(Base):
    __tablename__ = 'avatars'
    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey('contacts.id'))
    file_path = Column(String)  # путь к файлу аватарки контакта
    is_main = Column(Integer, default=0)  # 1 если основная, 0 иначе
    show = Column(Integer, default=1)  # 1 если показывать, 0 иначе

    contact = relationship('Contact', back_populates='avatars')

class Photo(Base):
    __tablename__ = 'photos'
    id = Column(Integer, primary_key=True, index=True)
    contact_id = Column(Integer, ForeignKey('contacts.id'))
    file_path = Column(String)
    is_main = Column(Integer, default=0)
    show = Column(Integer, default=1)

    contact = relationship('Contact', back_populates='photos')

# Модель для хранения токенов сброса пароля
class PasswordReset(Base):
    __tablename__ = "password_resets"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    token = Column(String, unique=True, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=False)
    is_used = Column(Boolean, default=False)
    
    # Отношение к пользователю
    user = relationship("User", back_populates="password_resets")
