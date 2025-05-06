from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from datetime import date, timedelta
import models, schemas
from sqlalchemy.exc import IntegrityError

# USERS CRUD

def get_user_by_username(db: Session, username: str):
    return db.query(models.User).filter(models.User.username == username).first()

def get_user_by_id(db: Session, user_id: int):
    return db.query(models.User).filter(models.User.id == user_id).first()

def update_user_role(db: Session, user_id: int, role: str):
    """Обновляет роль пользователя."""
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        return None
    
    # Проверка валидности роли
    if role not in ['user', 'admin', 'superadmin']:
        raise ValueError("Invalid role. Must be 'user', 'admin' or 'superadmin'")
    
    db_user.role = role
    db.commit()
    db.refresh(db_user)
    return db_user

# CONTACTS CRUD

from sqlalchemy.orm import joinedload

def get_contact(db: Session, contact_id: int):
    return (
        db.query(models.Contact)
        .options(
            joinedload(models.Contact.phone_numbers),
            joinedload(models.Contact.avatars),
            joinedload(models.Contact.photos),
            joinedload(models.Contact.groups),
        )
        .filter(models.Contact.id == contact_id)
        .first()
    )

def get_contacts(db: Session, user_id: int, skip: int = 0, limit: int = 100):
    return db.query(models.Contact).filter(models.Contact.user_id == user_id).offset(skip).limit(limit).all()

def create_contact(db: Session, user_id: int, contact: schemas.ContactCreate):
    db_contact = models.Contact(
        user_id=user_id,
        first_name=contact.first_name,
        last_name=contact.last_name,
        email=contact.email,
        birthday=contact.birthday,
        extra_info=contact.extra_info
    )
    # Add groups
    if getattr(contact, 'group_ids', None):
        groups = db.query(models.Group).filter(models.Group.id.in_(contact.group_ids)).all()
        db_contact.groups = groups
    db.add(db_contact)
    try:
        db.flush()  # get db_contact.id
    except IntegrityError as e:
        db.rollback()
        raise ValueError(f"Email already exists: {contact.email}")
    # Add phone numbers
    for pn in getattr(contact, 'phone_numbers', []):
        db_pn = models.PhoneNumber(number=pn.number, label=pn.label, contact_id=db_contact.id)
        db.add(db_pn)
    db.commit()
    db.refresh(db_contact)
    return db_contact

def update_contact(db: Session, contact_id: int, contact: schemas.ContactUpdate):
    db_contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if not db_contact:
        return None
    for field, value in contact.dict(exclude_unset=True).items():
        if field == "phone_numbers" and value is not None:
            db.query(models.PhoneNumber).filter(models.PhoneNumber.contact_id == contact_id).delete()
            for pn in value:
                # Исправление: поддержка dict и схемы
                if isinstance(pn, dict):
                    pn = schemas.PhoneNumberCreate(**pn)
                db_pn = models.PhoneNumber(number=pn.number, label=pn.label, contact_id=contact_id)
                db.add(db_pn)
        elif field == "group_ids" and value is not None:
            groups = db.query(models.Group).filter(models.Group.id.in_(value)).all()
            db_contact.groups = groups
        else:
            setattr(db_contact, field, value)
    db.commit()
    db.refresh(db_contact)
    return db_contact

def delete_contact(db: Session, contact_id: int):
    db_contact = db.query(models.Contact).filter(models.Contact.id == contact_id).first()
    if not db_contact:
        return None
    db.delete(db_contact)
    db.commit()
    return db_contact

def search_contacts(db: Session, query: str):
    query = f"%{query}%"
    return db.query(models.Contact).filter(
        or_(models.Contact.first_name.ilike(query),
            models.Contact.last_name.ilike(query),
            models.Contact.email.ilike(query))
    ).all()

def contacts_with_upcoming_birthdays(db: Session):
    today = date.today()
    in_seven_days = today + timedelta(days=7)
    # Check only month and day, ignore year
    return db.query(models.Contact).filter(
        or_(
            and_(func.extract('month', models.Contact.birthday) == today.month,
                 func.extract('day', models.Contact.birthday) >= today.day),
            and_(func.extract('month', models.Contact.birthday) == in_seven_days.month,
                 func.extract('day', models.Contact.birthday) <= in_seven_days.day)
        )
    ).all()

# GROUPS CRUD

def get_groups(db: Session):
    return db.query(models.Group).all()

def get_group(db: Session, group_id: int):
    return db.query(models.Group).filter(models.Group.id == group_id).first()

def create_group(db: Session, group: schemas.GroupCreate):
    db_group = models.Group(name=group.name)
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

def update_group(db: Session, group_id: int, group: schemas.GroupCreate):
    db_group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not db_group:
        return None
    db_group.name = group.name
    db.commit()
    db.refresh(db_group)
    return db_group

def delete_group(db: Session, group_id: int):
    db_group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not db_group:
        return None
    db.delete(db_group)
    db.commit()
    return db_group
