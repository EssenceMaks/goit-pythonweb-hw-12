from typing import List, Optional
from datetime import date, datetime
from pydantic import BaseModel, EmailStr, Field, constr, validator
import re

class PhoneNumberBase(BaseModel):
    number: constr(strip_whitespace=True, min_length=2, max_length=32)  
    label: Optional[str] = Field(default=None, description="Label: any string or None")

    @validator('number')
    def validate_number(cls, v):
        pattern = r'^[0-9\-+() ]+$'
        if not re.match(pattern, v):
            raise ValueError('Phone number must contain only digits, spaces, +, -, (, )')
        return v

class PhoneNumberCreate(PhoneNumberBase):
    pass

class PhoneNumber(PhoneNumberBase):
    id: int
    class Config:
        orm_mode = True

class Avatar(BaseModel):
    id: int
    file_path: Optional[str]
    is_main: int = 0
    show: int = 1
    class Config:
        orm_mode = True

class Photo(BaseModel):
    id: int
    file_path: Optional[str]
    is_main: int = 0
    show: int = 1
    class Config:
        orm_mode = True

class GroupBase(BaseModel):
    name: str

class GroupCreate(GroupBase):
    pass

class Group(GroupBase):
    id: int
    class Config:
        orm_mode = True

class ContactBase(BaseModel):
    first_name: str
    last_name: Optional[str] = None
    email: EmailStr
    birthday: date
    extra_info: Optional[str] = None

class ContactCreate(ContactBase):
    user_id: int
    phone_numbers: List[PhoneNumberCreate]
    group_ids: Optional[List[int]] = []

class ContactUpdate(ContactBase):
    phone_numbers: Optional[List[PhoneNumberCreate]] = None
    group_ids: Optional[List[int]] = None

class Contact(ContactBase):
    id: int
    phone_numbers: List[PhoneNumber] = []
    avatars: List[Avatar] = []
    photos: List[Photo] = []
    groups: List[Group] = []
    class Config:
        orm_mode = True

# Добавляю класс UserResponse для эндпоинта /users/me
class UserResponse(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    avatar_url: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    class Config:
        orm_mode = True

class UserWithContacts(BaseModel):
    id: int
    username: str
    email: EmailStr
    role: str
    contacts: List[Contact] = []
    class Config:
        orm_mode = True

class UserWithBirthdays(BaseModel):
    """
    Схема пользователя с контактами, у которых скоро день рождения.
    Используется для отображения списка дней рождений контактов,
    сгруппированных по пользователям.
    """
    id: int
    username: str
    email: EmailStr
    role: Optional[str] = "user"
    contacts_next7days: List[Contact] = []  # Контакты с ДР в ближайшие 7 дней
    contacts_next12months: List[Contact] = []  # Контакты с ДР в ближайшие 12 месяцев
    
    class Config:
        orm_mode = True
