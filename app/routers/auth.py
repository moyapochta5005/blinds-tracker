"""API-эндпоинты авторизации сотрудников."""

from fastapi import APIRouter, HTTPException, status

from app.auth_middleware import create_access_token
from app.schemas import LoginRequest, LoginResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# Демо-пользователи: логин → пароль и роль
DEMO_USERS: dict[str, dict[str, str]] = {
    "admin": {"password": "admin123", "role": "admin"},
    "master": {"password": "master123", "role": "master"},
    "courier": {"password": "courier123", "role": "courier"},
}


@router.post("/login", response_model=LoginResponse)
def login(credentials: LoginRequest) -> LoginResponse:
    """Аутентификация по логину и паролю, возвращает JWT-токен."""
    user = DEMO_USERS.get(credentials.username)

    if user is None or user["password"] != credentials.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
        )

    role = user["role"]
    token = create_access_token(
        username=credentials.username,
        role=role,
    )

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        username=credentials.username,
        role=role,
    )
