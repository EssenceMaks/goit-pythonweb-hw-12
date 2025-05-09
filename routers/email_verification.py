import random
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User
from utils_email_verif import send_verification_email
from passlib.context import CryptContext

router = APIRouter(prefix="/auth", tags=["Auth and Verification"])

# Jinja2 templates for rendering HTML forms
templates = Jinja2Templates(directory="templates")

@router.get("/forgot", response_class=HTMLResponse)
async def forgot_password_form(request: Request):
    return templates.TemplateResponse("password_reset/forgot.html", {"request": request})

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

class RegisterRequest(BaseModel):
    username: str
    email: str
    password: str

class VerifyRequest(BaseModel):
    email: str
    code: str

class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/register")
async def register_user(data: RegisterRequest, db: Session = Depends(get_db)):
    existing_email = db.query(User).filter(User.email == data.email).first()
    if existing_email:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
    existing_username = db.query(User).filter(User.username == data.username).first()
    if existing_username:
        raise HTTPException(status_code=400, detail="Ім'я зайнято, створіть інше")
    code = "{:06d}".format(random.randint(0, 999999))
    user = User(
        username=data.username,
        email=data.email,
        hashed_password=hash_password(data.password),
        is_verified=False,
        verification_code=code
    )
    db.add(user)
    db.commit()
    await send_verification_email(data.email, code)
    return {"detail": "Проверьте почту и введите код для завершения регистрации"}

@router.post("/verify")
async def verify_email(data: VerifyRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or user.verification_code != data.code:
        raise HTTPException(status_code=400, detail="Неверный код")
    user.is_verified = True
    user.verification_code = None
    db.commit()
    return {"detail": "Email подтверждён!"}

async def process_password_reset_email(request: Request, user: User, db: Session):
    import secrets
    from datetime import datetime, timedelta
    from models import PasswordReset
    reset_token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=24)
    # Сохраняем токен
    reset_entry = PasswordReset(user_id=user.id, token=reset_token, expires_at=expires_at)
    db.add(reset_entry)
    db.commit()
    # Формируем ссылку
    reset_url = f"https://{request.base_url.hostname}/reset/{reset_token}"
    from utils_email_verif import send_password_reset_email
    await send_password_reset_email(user.email, reset_url, user.username)
    return {"detail": "Лист для відновлення пароля надіслано на вашу пошту"}

@router.post("/forgot")
async def forgot_password(request: Request, db: Session = Depends(get_db)):
    data = await request.json()
    email = data.get('email')
    if not email:
        raise HTTPException(status_code=400, detail="Email обов'язковий")
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Перевірте чи саме на цей email ви хочете відправити листа для відновлення пароля")
    return await process_password_reset_email(request, user, db)

from fastapi import Depends
from auth import get_current_user

@router.post("/reset-password-from-settings")
async def reset_password_from_settings(request: Request, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if not current_user or not current_user.email:
        raise HTTPException(status_code=401, detail="Не удалось определить пользователя")
    user = db.query(User).filter(User.email == current_user.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    return await process_password_reset_email(request, user, db)

@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not pwd_context.verify(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Подтвердите email для входа")
    return {"detail": "Успешный вход!", "user_id": user.id}
