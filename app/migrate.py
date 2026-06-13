"""Скрипт миграции SQLite-базы данных."""

import os
import sqlite3
from typing import Final

CREATE_INSTALLERS_TABLE: Final[str] = """
CREATE TABLE IF NOT EXISTS installers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR NOT NULL,
    phone VARCHAR,
    manager_id INTEGER NOT NULL REFERENCES users(id),
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

ADD_INSTALLER_ID_COLUMN: Final[str] = """
ALTER TABLE orders ADD COLUMN installer_id INTEGER REFERENCES installers(id)
"""


def get_database_path() -> str:
    """Возвращает путь к файлу SQLite из DATABASE_URL или значение по умолчанию."""
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./orders.db")
    if database_url.startswith("sqlite:///"):
        return database_url.removeprefix("sqlite:///")
    return database_url


def column_exists(cursor: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    """Проверяет наличие колонки в таблице через PRAGMA table_info."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns: list[tuple] = cursor.fetchall()
    return any(row[1] == column_name for row in columns)


def run_migrations() -> None:
    """Применяет миграции: создаёт таблицу installers и добавляет installer_id в orders."""
    db_path: str = get_database_path()
    connection: sqlite3.Connection = sqlite3.connect(db_path)
    cursor: sqlite3.Cursor = connection.cursor()

    try:
        cursor.execute(CREATE_INSTALLERS_TABLE)
        print("Таблица installers создана или уже существует.")

        if not column_exists(cursor, "orders", "installer_id"):
            cursor.execute(ADD_INSTALLER_ID_COLUMN)
            print("Колонка installer_id добавлена в таблицу orders.")
        else:
            print("Колонка installer_id уже существует в таблице orders.")

        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    run_migrations()
