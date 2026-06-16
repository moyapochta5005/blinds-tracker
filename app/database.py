"""Настройка подключения к базе данных."""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

SQLALCHEMY_DATABASE_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql://blinds_user:password@db:5432/blinds_tracker",
)

engine = create_engine(SQLALCHEMY_DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Зависимость FastAPI: предоставляет сессию БД на время запроса."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
