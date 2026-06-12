"""Middleware и зависимости для проверки JWT-авторизации."""

import os
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Секрет для подписи JWT (в продакшене задать через переменную окружения)
SECRET_KEY: str = os.getenv("SECRET_KEY", "demo-secret-key-change-in-production")
JWT_ALGORITHM: str = "HS256"

security = HTTPBearer()


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> dict[str, str]:
    """
    Проверяет JWT из заголовка Authorization: Bearer <token>.

    Возвращает словарь с username и role.
    """
    token = credentials.credentials

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
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

    username = payload.get("sub")
    role = payload.get("role")

    if not username or not role:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Некорректное содержимое токена",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return {"username": username, "role": role}


def create_access_token(username: str, role: str, expires_hours: int = 24) -> str:
    """Создаёт JWT-токен с указанным именем пользователя и ролью."""
    expire = datetime.now(timezone.utc) + timedelta(hours=expires_hours)
    payload = {
        "sub": username,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)
