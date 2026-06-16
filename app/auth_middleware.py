"""Middleware и зависимости для проверки JWT-авторизации."""

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Секрет для подписи JWT (в продакшене задать через переменную окружения)
SECRET_KEY: str = os.getenv("SECRET_KEY", "demo-secret-key-change-in-production")
JWT_ALGORITHM: str = "HS256"

security = HTTPBearer()
optional_security = HTTPBearer(auto_error=False)


def _decode_token(token: str) -> dict[str, Any]:
    """Декодирует JWT и возвращает payload."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Срок действия токена истёк",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Недействительный токен",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _payload_to_user(payload: dict[str, Any]) -> dict[str, Any]:
    """Преобразует payload JWT в словарь текущего пользователя."""
    username = payload.get("sub")
    role = payload.get("role")
    manager_id = payload.get("manager_id")
    full_name = payload.get("full_name")
    company_id = payload.get("company_id")

    if not username or not role or manager_id is None or not full_name:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректное содержимое токена",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {
        "username": username,
        "role": role,
        "manager_id": int(manager_id),
        "full_name": full_name,
        "company_id": company_id,
    }


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> dict[str, Any]:
    """
    Проверяет JWT из заголовка Authorization: Bearer <token>.

    Возвращает словарь с username, role, manager_id и full_name.
    """
    payload = _decode_token(credentials.credentials)
    return _payload_to_user(payload)


def get_optional_user(
    credentials: Annotated[
        Optional[HTTPAuthorizationCredentials],
        Depends(optional_security),
    ],
) -> Optional[dict[str, Any]]:
    """Возвращает текущего пользователя или None, если токен не передан."""
    if credentials is None:
        return None

    payload = _decode_token(credentials.credentials)
    return _payload_to_user(payload)


def require_admin(
    current_user: Annotated[dict[str, Any], Depends(get_current_user)],
) -> dict[str, Any]:
    """Разрешает доступ только администратору."""
    if current_user["role"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для администратора",
        )
    return current_user


def create_access_token(
    username: str,
    role: str,
    manager_id: int,
    full_name: str,
    company_id: Optional[int] = None,
    expires_hours: int = 24,
) -> str:
    """Создаёт JWT-токен с данными пользователя."""
    expire = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    payload = {
        "sub": username,
        "role": role,
        "manager_id": manager_id,
        "full_name": full_name,
        "company_id": company_id,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
