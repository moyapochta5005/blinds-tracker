"""API-эндпоинты авторизации сотрудников."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth_middleware import create_access_token
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, LoginResponse
from app.security import verify_password

router = APIRouter(prefix="/auth", tags=["auth"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post("/login", response_model=LoginResponse)
def login(credentials: LoginRequest, db: DbSession) -> LoginResponse:
    """Аутентификация по логину и паролю, возвращает JWT-токен."""
    user = (
        db.query(User)
        .filter(User.username == credentials.username)
        .first()
    )

    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Учётная запись деактивирована",
        )

    token = create_access_token(
        username=user.username,
        role=user.role,
        manager_id=user.id,
        full_name=user.full_name,
        company_id=user.company_id,
    )

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        username=user.username,
        role=user.role,
        manager_id=user.id,
        full_name=user.full_name,
    )
