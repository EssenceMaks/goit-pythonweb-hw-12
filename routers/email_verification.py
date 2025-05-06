import random
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from database import SessionLocal
from models import User
from utils_email_verif import send_verification_email
from passlib.context import CryptContext

router = APIRouter(prefix="/auth", tags=["Auth and Verification"])

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
    existing = db.query(User).filter(User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email уже зарегистрирован")
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

@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if not user or not pwd_context.verify(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Подтвердите email для входа")
    return {"detail": "Успешный вход!", "user_id": user.id}
