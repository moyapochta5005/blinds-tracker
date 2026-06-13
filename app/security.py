"""Утилиты для хэширования и проверки паролей."""

import bcrypt


def hash_password(password: str) -> str:
    """Хэширует пароль с помощью bcrypt."""
    password_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Проверяет соответствие пароля сохранённому хэшу."""
    return bcrypt.checkpw(
        password.encode("utf-8"),
        password_hash.encode("utf-8"),
    )
