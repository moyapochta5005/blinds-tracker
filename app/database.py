"""Настройка подключения к базе данных SQLite."""

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# URL базы данных SQLite (переопределяется через DATABASE_URL в Docker)
SQLALCHEMY_DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./orders.db")

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """Зависимость FastAPI: предоставляет сессию БД на время запроса."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
