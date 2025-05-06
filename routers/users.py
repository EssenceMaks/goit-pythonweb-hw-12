from fastapi import APIRouter, Depends, HTTPException, Request, Response, File, UploadFile, Form
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select
from datetime import timedelta, datetime
from typing import Optional, List

from database import get_db
from models import User, UserAvatar, AvatarRequestMessage
from auth import get_current_user, create_access_token
from schemas import UserResponse
from utils_cloudinary import upload_image, delete_image
# Импортируем функцию ограничения запросов
from rate_limiter import check_rate_limit_me

router = APIRouter(
    prefix="/users",
    tags=["users"],
)

@router.get("/me", response_model=UserResponse, dependencies=[Depends(check_rate_limit_me)])
async def get_current_user_info(request: Request, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Получить информацию о текущем авторизованном пользователе
    Ограничение: 5 запросов в минуту
    """
    # Получаем основной аватар пользователя (если есть) - используем явный запрос вместо lazy loading
    avatar_url = None
    
    # Получаем пользователя с активной сессией
    user_with_session = db.query(User).filter(User.id == current_user.id).first()
    
    if user_with_session:
        # Загружаем аватары пользователя (если есть)
        avatars = db.query(UserAvatar).filter(UserAvatar.user_id == user_with_session.id).all()
        
        if avatars:
            # Ищем основной аватар со статусом approved
            main_avatar = next((avatar for avatar in avatars 
                                if avatar.is_main == 1 and avatar.is_approved == 1), None)
            if main_avatar:
                avatar_url = main_avatar.file_path
            else:
                # Если основного нет, берем первый approved
                approved_avatar = next((avatar for avatar in avatars 
                                       if avatar.is_approved == 1), None)
                if approved_avatar:
                    avatar_url = approved_avatar.file_path
    
    # Если аватар не найден, используем стандартный в зависимости от роли
    if not avatar_url:
        if user_with_session.role == "superadmin":
            avatar_url = "/static/menu/img/manager.png"
        elif user_with_session.role == "admin":
            avatar_url = "/static/menu/img/ska.png"
        else:
            avatar_url = "/static/menu/img/avatar.png"
    
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "avatar_url": avatar_url,
        "created_at": getattr(current_user, 'created_at', None),
        "updated_at": getattr(current_user, 'updated_at', None)
    }

@router.patch("/update/username")
async def update_username(
    request: Request,
    response: Response,
    username_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Обновить имя пользователя
    """
    if "username" not in username_data:
        raise HTTPException(status_code=400, detail="Username is required")
    
    new_username = username_data["username"]
    
    # Проверка, не занято ли имя пользователя
    existing_user = db.query(User).filter(User.username == new_username, User.id != current_user.id).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already taken")
    
    # Получаем пользователя из текущей сессии для обновления
    user_to_update = db.query(User).filter(User.id == current_user.id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Обновляем имя пользователя
    user_to_update.username = new_username
    db.commit()
    db.refresh(user_to_update)
    
    # Создаем новый токен с обновленным именем пользователя
    access_token_expires = timedelta(minutes=60 * 24 * 7)  # 7 дней
    access_token = create_access_token(
        data={"sub": new_username, "id": user_to_update.id, "role": user_to_update.role, "email": user_to_update.email},
        expires_delta=access_token_expires
    )
    
    # Обновляем токен в куках
    response.set_cookie(
        key="access_token", 
        value=access_token, 
        httponly=True, 
        max_age=60*60*24*7,  # 7 дней
        samesite="lax"
    )
    
    return {"message": "Username updated successfully", "username": new_username}

@router.patch("/update/password")
async def update_password(
    request: Request,
    password_data: dict,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Обновить пароль пользователя
    """
    if "current_password" not in password_data or "new_password" not in password_data:
        raise HTTPException(status_code=400, detail="Current password and new password are required")
    
    # Получаем пользователя из текущей сессии для обновления
    user_to_update = db.query(User).filter(User.id == current_user.id).first()
    if not user_to_update:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Проверка текущего пароля
    if not user_to_update.verify_password(password_data["current_password"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Обновляем пароль
    user_to_update.hashed_password = User.get_password_hash(password_data["new_password"])
    db.commit()
    
    return {"message": "Password updated successfully"}

@router.post("/password/reset")
async def reset_password(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Инициировать процесс сброса пароля
    """
    # В реальном приложении здесь должна быть отправка email с ссылкой для сброса пароля
    # Для упрощения в тестовой версии просто возвращаем ответ об успехе
    
    # Получаем пользователя из текущей сессии
    user_to_reset = db.query(User).filter(User.id == current_user.id).first()
    if not user_to_reset:
        raise HTTPException(status_code=404, detail="User not found")
    
    # В реальном приложении здесь генерируется токен сброса пароля,
    # сохраняется в базе и отправляется по email
    
    # Имитируем успешную отправку
    return {"message": "Password reset link has been sent to your email"}

@router.get("/avatars", response_model=List[dict])
async def get_user_avatars(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получить список всех аватаров пользователя
    """
    avatars = db.query(UserAvatar).filter(UserAvatar.user_id == current_user.id).all()
    
    return [
        {
            "id": avatar.id,
            "file_path": avatar.file_path,
            "is_main": avatar.is_main == 1,
            "is_approved": avatar.is_approved == 1,
            "request_status": avatar.request_status,
            "created_at": avatar.created_at
        }
        for avatar in avatars
    ]

@router.post("/avatars/upload")
async def upload_user_avatar(
    request: Request,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Загрузить новый аватар пользователя
    """
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    try:
        url, public_id = upload_image(await file.read())
        if not url or not public_id:
            raise HTTPException(status_code=500, detail="Failed to upload avatar")
        # Для админов — сразу approved и основным
        if current_user.role in ["admin", "superadmin"]:
            is_approved = 1
            request_status = 'approved'
            is_main = 1
        else:
            is_approved = 0
            request_status = None
            is_main = 0
        new_avatar = UserAvatar(
            user_id=current_user.id,
            file_path=url,
            cloudinary_public_id=public_id,
            is_approved=is_approved,
            is_main=is_main,
            request_type='upload',
            request_status=request_status
        )
        db.add(new_avatar)
        db.commit()
        db.refresh(new_avatar)
        return {
            "id": new_avatar.id,
            "file_path": new_avatar.file_path,
            "is_main": new_avatar.is_main == 1,
            "is_approved": new_avatar.is_approved == 1,
            "request_status": new_avatar.request_status,
            "message": "Avatar uploaded successfully"
        }
    except Exception as e:
        print(f"Error uploading avatar: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload avatar: {str(e)}")

@router.patch("/avatars/{avatar_id}/set-main")
async def set_avatar_as_main(
    request: Request,
    avatar_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Установить аватар как основной
    """
    avatar = db.query(UserAvatar).filter(
        UserAvatar.id == avatar_id,
        UserAvatar.user_id == current_user.id
    ).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found or not owned by user")
    # Сбросить pending/approved/rejected у всех аватарок пользователя
    db.query(UserAvatar).filter(UserAvatar.user_id == current_user.id).update({
        "request_status": None,
        "is_main": 0
    })
    if current_user.role in ["admin", "superadmin"]:
        avatar.is_main = 1
        avatar.is_approved = 1
        avatar.request_status = 'approved'
        db.commit()
        return {"message": "Avatar set as main successfully"}
    # Для обычных пользователей — создаём заявку
    avatar.request_type = 'set_main'
    avatar.request_status = 'pending'
    avatar.is_main = 0  # Не делаем основным до одобрения
    avatar.is_approved = 0
    db.commit()
    # Сбросить все pending-заявки в AvatarRequestMessage
    db.query(AvatarRequestMessage).filter(
        AvatarRequestMessage.user_id == current_user.id,
        AvatarRequestMessage.status == 'pending'
    ).delete()
    # Создаём заявку
    msg = AvatarRequestMessage(
        user_id=current_user.id,
        avatar_id=avatar.id,
        message="Request to set avatar as main",
        status='pending',
        created_at=datetime.utcnow()
    )
    db.add(msg)
    db.commit()
    return {"message": "Request to set avatar as main sent for approval"}

@router.post("/avatar-requests/{avatar_id}/approve")
async def approve_avatar_request(
    request: Request,
    avatar_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    avatar = db.query(UserAvatar).filter(UserAvatar.id == avatar_id).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    # Находим заявку
    req = db.query(AvatarRequestMessage).filter(AvatarRequestMessage.avatar_id == avatar_id, AvatarRequestMessage.status == 'pending').first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    # Сбросить is_main у всех аватарок пользователя
    db.query(UserAvatar).filter(UserAvatar.user_id == avatar.user_id).update({"is_main": 0})
    # Обновляем статусы
    avatar.is_approved = 1
    avatar.request_status = 'approved'
    avatar.is_main = 1
    req.status = 'approved'
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.utcnow()
    db.commit()
    return {"message": "Avatar request approved"}

@router.post("/{user_id}/set-role")
async def set_user_role(
    request: Request,
    user_id: int,
    new_role: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    if new_role not in ["user", "admin", "superadmin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = new_role
    db.commit()
    return {"message": f"User role set to {new_role}"}

@router.get("/permissions", response_model=List[dict])
async def get_users_with_permissions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Получить всех пользователей с их ролями, аватарами и pending заявками на смену аватара.
    Только для админов и суперадминов.
    """
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")

    users = db.query(User).options(joinedload(User.avatars)).all()
    # Получаем pending заявки на смену аватара
    pending_requests = db.query(AvatarRequestMessage).filter(AvatarRequestMessage.status == 'pending').all()
    # Группируем pending заявки по user_id
    requests_by_user = {}
    for req in pending_requests:
        if req.user_id not in requests_by_user:
            requests_by_user[req.user_id] = []
        requests_by_user[req.user_id].append({
            "id": req.id,
            "avatar_id": req.avatar_id,
            "avatar_url": req.avatar.file_path if req.avatar else None,
            "request_type": req.avatar.request_type if req.avatar else None,
            "status": req.status,
            "created_at": req.created_at,
            "message": req.message
        })

    result = []
    for user in users:
        # Определяем основной аватар (is_main=1 и is_approved=1)
        main_avatar = next((a for a in user.avatars if a.is_main == 1 and a.is_approved == 1), None)
        if not main_avatar:
            # Если нет основного, ищем любой одобренный
            main_avatar = next((a for a in user.avatars if a.is_approved == 1), None)
        main_avatar_url = main_avatar.file_path if main_avatar else None
        # Все аватары пользователя
        avatars = [{
            "id": a.id,
            "file_path": a.file_path,
            "is_main": a.is_main == 1,
            "is_approved": a.is_approved == 1,
            "created_at": a.created_at
        } for a in user.avatars]
        # Pending заявки
        pending = requests_by_user.get(user.id, [])
        result.append({
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "role": user.role,
            "main_avatar_url": main_avatar_url,
            "avatars": avatars,
            "pending_avatar_requests": pending
        })
    return result

@router.post("/avatars/{avatar_id}/request-main")
async def request_avatar_as_main(
    request: Request,
    avatar_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Пользователь отправляет запрос на сделать аватар основным. Все предыдущие pending-запросы удаляются.
    """
    avatar = db.query(UserAvatar).filter(UserAvatar.id == avatar_id, UserAvatar.user_id == current_user.id).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found or not owned by user")
    # Сбросить pending/approved/rejected у всех аватарок пользователя
    db.query(UserAvatar).filter(UserAvatar.user_id == current_user.id).update({
        'is_approved': 0,
        'request_status': None,
        'is_main': 0
    })
    db.commit()
    # Удаляем все предыдущие pending-запросы пользователя
    db.query(AvatarRequestMessage).filter(
        AvatarRequestMessage.user_id == current_user.id, 
        AvatarRequestMessage.status == 'pending'
    ).delete()
    db.commit()
    # Создаём новый pending-запрос
    req = AvatarRequestMessage(
        user_id=current_user.id,
        avatar_id=avatar_id,
        message="Запрос на установку основного аватара",
        status='pending'
    )
    db.add(req)
    # У отмеченной аватарки выставляем request_status
    avatar.is_approved = 0
    avatar.request_status = 'pending'
    avatar.is_main = 0
    db.commit()
    return {"message": "Запрос отправлен на модерацию"}

@router.delete("/avatar-requests/{avatar_id}/cancel")
async def cancel_avatar_request(
    request: Request,
    avatar_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Пользователь отменяет pending-запрос на смену основного аватара.
    """
    req = db.query(AvatarRequestMessage).filter(
        AvatarRequestMessage.avatar_id == avatar_id,
        AvatarRequestMessage.user_id == current_user.id,
        AvatarRequestMessage.status == 'pending'
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail="Pending request not found")
    db.delete(req)
    # Сбросить статус у аватарки
    avatar = db.query(UserAvatar).filter(UserAvatar.id == avatar_id, UserAvatar.user_id == current_user.id).first()
    if avatar:
        avatar.is_approved = 0
        avatar.request_status = None
        avatar.is_main = 0
    db.commit()
    return {"message": "Запрос отменён"}

@router.post("/avatar-requests/{avatar_id}/reject")
async def reject_avatar_request(
    request: Request,
    avatar_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    avatar = db.query(UserAvatar).filter(UserAvatar.id == avatar_id).first()
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found")
    req = db.query(AvatarRequestMessage).filter(AvatarRequestMessage.avatar_id == avatar_id, AvatarRequestMessage.status == 'pending').first()
    if not req:
        raise HTTPException(status_code=404, detail="Request not found")
    avatar.request_status = 'rejected'
    avatar.is_approved = 0
    avatar.is_main = 0
    req.status = 'rejected'
    req.reviewed_by = current_user.id
    req.reviewed_at = datetime.utcnow()
    db.commit()
    return {"message": "Avatar request rejected"}

@router.delete("/avatars/{avatar_id}")
async def delete_user_avatar(
    request: Request,
    avatar_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Удалить аватар пользователя
    """
    # Проверяем, существует ли аватар и принадлежит ли он пользователю
    avatar = db.query(UserAvatar).filter(
        UserAvatar.id == avatar_id,
        UserAvatar.user_id == current_user.id
    ).first()
    
    if not avatar:
        raise HTTPException(status_code=404, detail="Avatar not found or not owned by user")
    
    # Если удаляемый аватар был основным, нужно выбрать другой аватар как основной
    was_main = avatar.is_main == 1
    
    # Если у аватара есть public_id в Cloudinary, удаляем изображение из Cloudinary
    if hasattr(avatar, 'cloudinary_public_id') and avatar.cloudinary_public_id:
        delete_image(avatar.cloudinary_public_id)
    
    # Удаляем из базы данных
    db.delete(avatar)
    db.commit()
    
    # Если удаленный аватар был основным, устанавливаем следующий доступный как основной
    if was_main:
        next_avatar = db.query(UserAvatar).filter(
            UserAvatar.user_id == current_user.id,
            UserAvatar.is_approved == 1
        ).first()
        
        if next_avatar:
            next_avatar.is_main = 1
            db.commit()
    
    return {"message": "Avatar deleted successfully"}

@router.get("/avatar-requests", response_model=List[dict])
async def get_avatar_requests(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    # Показываем только pending заявки
    requests = db.query(AvatarRequestMessage).options(joinedload(AvatarRequestMessage.user), joinedload(AvatarRequestMessage.avatar)).filter(AvatarRequestMessage.status == 'pending').all()
    result = []
    for req in requests:
        result.append({
            "id": req.id,
            "user_id": req.user_id,
            "username": req.user.username if req.user else None,
            "email": req.user.email if req.user else None,
            "avatar_id": req.avatar_id,
            "avatar_url": req.avatar.file_path if req.avatar else None,
            "request_type": req.avatar.request_type if req.avatar else None,
            "status": req.status,
            "created_at": req.created_at,
            "message": req.message
        })
    return result