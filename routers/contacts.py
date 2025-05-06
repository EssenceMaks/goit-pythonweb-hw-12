from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import extract, and_, or_
from typing import List, Optional
from datetime import date, timedelta
import logging
import crud, models, schemas
from database import SessionLocal
from models import Contact, User
from schemas import Contact as ContactSchema, ContactCreate, ContactUpdate, UserWithContacts, UserWithBirthdays
# Используем обновлённые функции авторизации
from auth import get_current_user, check_contact_access

router = APIRouter(tags=["Contacts"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("/", response_model=ContactSchema)
async def create_contact(
    request: Request,
    contact: ContactCreate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    logging.info(f"[ROUTER] create_contact RAW: {contact}")
    
    # Для супер-админа и админа разрешаем создавать контакты для любого пользователя
    if current_user.role in ["superadmin", "admin"]:
        # Если явно указан user_id - используем его
        if contact.user_id is not None:
            target_user_id = contact.user_id
        else:
            # Если не указан - создаем для себя
            target_user_id = current_user.id
    # Для обычного пользователя создаем только для себя
    else:
        target_user_id = current_user.id
    
    try:
        return crud.create_contact(db, target_user_id, contact)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/grouped", response_model=List[UserWithContacts])
async def read_contacts_grouped(
    request: Request,
    search: str = Query(None),
    sort: str = Query("asc"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Определяем, кого возвращать
    query_users = db.query(models.User)
    
    if current_user.role == "superadmin":
        # Все пользователи для суперадмина
        pass
    elif current_user.role == "admin":
        # Все пользователи для админа
        pass
    else:
        # Только свои контакты для обычного пользователя
        query_users = query_users.filter(models.User.id == current_user.id)

    # Жадно грузим контакты
    query_users = query_users.options(joinedload(models.User.contacts))
    users = query_users.all()
    logging.info(f"/contacts/grouped: found {len(users)} users for role {current_user.role}")

    # Фильтрация и сортировка контактов на уровне Python
    result = []
    for u in users:
        contacts = u.contacts
        if search:
            search_lc = search.lower()
            contacts = [c for c in contacts if search_lc in (c.first_name or '').lower() or search_lc in (c.last_name or '').lower() or search_lc in (c.email or '').lower()]
        if sort == "desc":
            contacts = sorted(contacts, key=lambda c: (c.first_name or '').lower(), reverse=True)
        else:
            contacts = sorted(contacts, key=lambda c: (c.first_name or '').lower())
        
        # Улучшенная проверка и исправление email перед сериализацией
        email = u.email
        if not email or '@' not in email or ' ' in email:
            # Если email некорректный, создаем валидный email на основе имени пользователя
            # Удаляем все недопустимые символы и заменяем пробелы точками
            safe_username = u.username.replace(' ', '.').replace('@', '.').strip()
            email = f"{safe_username}@example.com"
            logging.info(f"Исправлен email для пользователя {u.id} с '{u.email}' на '{email}'")
            
        # Сериализуем ORM-объекты через pydantic
        contacts_data = [schemas.Contact.model_validate(c, from_attributes=True) for c in contacts]
        try:
            result.append(schemas.UserWithContacts(
                id=u.id,
                username=u.username,
                email=email,
                role=u.role or "user",
                contacts=contacts_data
            ))
        except Exception as e:
            logging.error(f"Ошибка при создании UserWithContacts для пользователя {u.id}: {str(e)}")
            # Создаем гарантированно валидный email
            fallback_email = f"user{u.id}@example.com"
            logging.info(f"Используем запасной email {fallback_email} для пользователя {u.id}")
            # Добавляем с пустым списком контактов вместо полного исключения
            result.append(schemas.UserWithContacts(
                id=u.id,
                username=u.username,
                email=fallback_email,
                role=u.role or "user",
                contacts=[]
            ))
    return result

@router.get("/grouped/birthdays", response_model=List[UserWithBirthdays])
async def read_birthdays_grouped_by_users(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получение дней рождения, сгруппированных по пользователям.
    Только для администраторов и суперадминов.
    """
    # Проверяем, что пользователь имеет права администратора
    if current_user.role not in ["superadmin", "admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Недостаточно прав для доступа к этому ресурсу"
        )
    
    # Получаем всех пользователей
    query_users = db.query(models.User)
    users = query_users.all()
    
    result = []
    today = date.today()
    in_seven_days = today + timedelta(days=7)
    today_md = today.month * 100 + today.day
    in_seven_days_md = in_seven_days.month * 100 + in_seven_days.day
    
    for user in users:
        # Дни рождения в ближайшие 7 дней
        next7_query = db.query(models.Contact).filter(
            models.Contact.user_id == user.id,
            models.Contact.birthday.isnot(None)
        )
        
        if today_md <= in_seven_days_md:
            next7_contacts = next7_query.filter(
                birthday_md_expr().between(today_md, in_seven_days_md)
            ).all()
        else:
            next7_contacts = next7_query.filter(
                or_(
                    birthday_md_expr().between(today_md, 1231),
                    birthday_md_expr().between(101, in_seven_days_md)
                )
            ).all()
        
        # Дни рождения в ближайшие 12 месяцев
        next12_contacts = db.query(models.Contact).filter(
            models.Contact.user_id == user.id,
            models.Contact.birthday.isnot(None),
            birthday_md_expr() >= today_md
        ).order_by(
            extract('month', models.Contact.birthday),
            extract('day', models.Contact.birthday)
        ).all()
        
        # Не добавляем пользователей без контактов с днями рождения
        if next7_contacts or next12_contacts:
            # Улучшенная проверка и исправление email перед сериализацией
            email = user.email
            if not email or '@' not in email or ' ' in email:
                # Если email некорректный, создаем валидный email на основе имени пользователя
                safe_username = user.username.replace(' ', '.').replace('@', '.').strip()
                email = f"{safe_username}@example.com"
                logging.info(f"Исправлен email для пользователя {user.id} с '{user.email}' на '{email}'")
            
            try:
                # Сериализуем контакты
                next7_data = [schemas.Contact.model_validate(c, from_attributes=True) for c in next7_contacts]
                next12_data = [schemas.Contact.model_validate(c, from_attributes=True) for c in next12_contacts]
                
                result.append(schemas.UserWithBirthdays(
                    id=user.id,
                    username=user.username,
                    email=email,
                    role=user.role or "user",
                    contacts_next7days=next7_data,
                    contacts_next12months=next12_data
                ))
            except Exception as e:
                logging.error(f"Ошибка при создании UserWithBirthdays для пользователя {user.id}: {str(e)}")
                # Создаем гарантированно валидный email
                fallback_email = f"user{user.id}@example.com"
                logging.info(f"Используем запасной email {fallback_email} для пользователя {user.id}")
                
                # Добавляем с пустыми списками контактов вместо полного исключения
                result.append(schemas.UserWithBirthdays(
                    id=user.id,
                    username=user.username,
                    email=fallback_email,
                    role=user.role or "user",
                    contacts_next7days=[],
                    contacts_next12months=[]
                ))
    
    return result

@router.get("/", response_model=List[ContactSchema])
async def read_contacts(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    search: str = Query(None),
    sort: str = Query("asc"),
    user_id: Optional[int] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    query = db.query(models.Contact)
    
    # Если не указан user_id и это супер-админ — показываем все контакты
    if user_id is not None:
        query = query.filter(models.Contact.user_id == user_id)
    elif current_user.role != "superadmin":
        # Обычный пользователь — только свои контакты
        query = query.filter(models.Contact.user_id == current_user.id)
    
    # superadmin без user_id — все контакты
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (models.Contact.first_name.ilike(search_pattern)) |
            (models.Contact.last_name.ilike(search_pattern)) |
            (models.Contact.email.ilike(search_pattern))
        )
    
    if sort == "desc":
        query = query.order_by(models.Contact.first_name.desc())
    else:
        query = query.order_by(models.Contact.first_name.asc())
    
    return query.offset(skip).limit(limit).all()

@router.get("/search/", response_model=List[ContactSchema])
async def search_contacts(
    request: Request,
    query: str, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    results = crud.search_contacts(db, query)
    # Фильтруем результаты по доступу пользователя
    if current_user.role not in ["superadmin", "admin"]:
        results = [contact for contact in results if contact.user_id == current_user.id]
    return results

@router.get("/birthdays/", response_model=List[ContactSchema])
async def get_upcoming_birthdays(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    results = crud.contacts_with_upcoming_birthdays(db)
    # Фильтруем результаты по доступу пользователя
    if current_user.role not in ["superadmin", "admin"]:
        results = [contact for contact in results if contact.user_id == current_user.id]
    return results

def birthday_md_expr():
    return extract('month', models.Contact.birthday) * 100 + extract('day', models.Contact.birthday)

@router.get("/birthdays/next7days", response_model=List[ContactSchema])
async def get_upcoming_birthdays_next7days(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    today = date.today()
    in_seven_days = today + timedelta(days=7)
    today_md = today.month * 100 + today.day
    in_seven_days_md = in_seven_days.month * 100 + in_seven_days.day

    query = db.query(models.Contact).filter(models.Contact.birthday.isnot(None))
    
    # Ограничиваем доступ для обычных пользователей
    if current_user.role not in ["superadmin", "admin"]:
        query = query.filter(models.Contact.user_id == current_user.id)

    if today_md <= in_seven_days_md:
        contacts = query.filter(
            birthday_md_expr().between(today_md, in_seven_days_md)
        ).all()
    else:
        contacts = query.filter(
            or_(
                birthday_md_expr().between(today_md, 1231),
                birthday_md_expr().between(101, in_seven_days_md)
            )
        ).all()
    return contacts

@router.get("/birthdays/next12months", response_model=List[ContactSchema])
async def get_birthdays_next_12_months(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    today = date.today()
    today_md = today.month * 100 + today.day
    
    query = db.query(models.Contact).filter(
        models.Contact.birthday.isnot(None),
        birthday_md_expr() >= today_md
    )
    
    # Ограничиваем доступ для обычных пользователей
    if current_user.role not in ["superadmin", "admin"]:
        query = query.filter(models.Contact.user_id == current_user.id)
        
    contacts = query.order_by(
        extract('month', models.Contact.birthday),
        extract('day', models.Contact.birthday)
    ).all()
    
    return contacts

@router.get("/{contact_id}", response_model=ContactSchema)
async def read_contact(
    request: Request,
    contact_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    db_contact = crud.get_contact(db, contact_id)
    if db_contact is None:
        raise HTTPException(status_code=404, detail="Contact not found")
        
    # Проверка доступа к контакту
    if current_user.role not in ["superadmin", "admin"] and db_contact.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to access this contact"
        )
        
    return db_contact

@router.put("/{contact_id}", response_model=ContactSchema)
async def update_contact(
    request: Request,
    contact_id: int, 
    contact: ContactUpdate, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Проверяем существование контакта
    existing_contact = crud.get_contact(db, contact_id)
    if not existing_contact:
        raise HTTPException(status_code=404, detail="Contact not found")
        
    # Проверяем доступ к контакту
    if current_user.role not in ["superadmin", "admin"] and existing_contact.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to update this contact"
        )
    
    logging.info(f"[ROUTER] update_contact RAW: {contact}")
    db_contact = crud.update_contact(db, contact_id, contact)
    return db_contact

@router.delete("/{contact_id}", response_model=ContactSchema)
async def delete_contact(
    request: Request,
    contact_id: int, 
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Проверяем существование контакта
    existing_contact = crud.get_contact(db, contact_id)
    if not existing_contact:
        raise HTTPException(status_code=404, detail="Contact not found")
        
    # Проверяем доступ к контакту
    if current_user.role not in ["superadmin", "admin"] and existing_contact.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions to delete this contact"
        )
        
    db_contact = crud.delete_contact(db, contact_id)
    return db_contact
