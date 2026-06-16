"""API-эндпоинты управления пользователями (только для администратора)."""

from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth_middleware import require_admin
from app.database import get_db
from app.models import User
from app.schemas import UserCreate, UserResponse, UserUpdate
from app.security import hash_password

router = APIRouter(prefix="/users", tags=["users"])

DbSession = Annotated[Session, Depends(get_db)]
AdminUser = Annotated[dict[str, object], Depends(require_admin)]


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_manager(
    user_data: UserCreate,
    db: DbSession,
    current_user: AdminUser,
) -> User:
    """Создать нового менеджера."""
    existing = db.query(User).filter(User.username == user_data.username).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким логином уже существует",
        )

    user = User(
        username=user_data.username,
        password_hash=hash_password(user_data.password),
        full_name=user_data.full_name,
        role="manager",
        is_active=True,
        company_id=current_user.get("company_id"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("", response_model=List[UserResponse])
def list_managers(db: DbSession, current_user: AdminUser) -> List[User]:
    """Получить список всех менеджеров."""
    query = db.query(User).filter(User.role == "manager")
    company_id = current_user.get("company_id")
    if current_user["role"] != "superadmin" and company_id is not None:
        query = query.filter(User.company_id == company_id)
    return query.order_by(User.full_name).all()


@router.patch("/{user_id}", response_model=UserResponse)
def update_manager(
    user_id: int,
    user_data: UserUpdate,
    db: DbSession,
    current_user: AdminUser,
) -> User:
    """Обновить данные менеджера."""
    query = db.query(User).filter(User.id == user_id, User.role == "manager")
    company_id = current_user.get("company_id")
    if current_user["role"] != "superadmin" and company_id is not None:
        query = query.filter(User.company_id == company_id)
    user = query.first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Менеджер не найден",
        )

    if user_data.username is not None and user_data.username != user.username:
        existing = (
            db.query(User)
            .filter(User.username == user_data.username, User.id != user_id)
            .first()
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Пользователь с таким логином уже существует",
            )
        user.username = user_data.username

    if user_data.full_name is not None:
        user.full_name = user_data.full_name

    if user_data.password is not None:
        user.password_hash = hash_password(user_data.password)

    if user_data.is_active is not None:
        user.is_active = user_data.is_active

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", response_model=UserResponse)
def deactivate_manager(
    user_id: int,
    db: DbSession,
    current_user: AdminUser,
) -> User:
    """Деактивировать менеджера (мягкое удаление)."""
    query = db.query(User).filter(User.id == user_id, User.role == "manager")
    company_id = current_user.get("company_id")
    if current_user["role"] != "superadmin" and company_id is not None:
        query = query.filter(User.company_id == company_id)
    user = query.first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Менеджер не найден",
        )

    user.is_active = False
    db.commit()
    db.refresh(user)
    return user
