"""Скрипт миграции SQLite-базы данных."""

import os
import sqlite3
from typing import Final, Optional

import bcrypt

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

ADD_PUBLIC_TOKEN_COLUMN: Final[str] = """
ALTER TABLE orders ADD COLUMN public_token TEXT
"""

BACKFILL_PUBLIC_TOKEN: Final[str] = """
UPDATE orders SET public_token = lower(hex(randomblob(16))) WHERE public_token IS NULL
"""

CREATE_PUBLIC_TOKEN_INDEX: Final[str] = """
CREATE UNIQUE INDEX IF NOT EXISTS ix_orders_public_token ON orders(public_token)
"""

ADD_USER_MANAGER_ID_COLUMN: Final[str] = """
ALTER TABLE users ADD COLUMN manager_id INTEGER REFERENCES users(id)
"""

ADD_USER_PHONE_COLUMN: Final[str] = """
ALTER TABLE users ADD COLUMN phone TEXT
"""

ADD_DEALER_ID_COLUMN: Final[str] = """
ALTER TABLE orders ADD COLUMN dealer_id INTEGER REFERENCES users(id)
"""

ADD_COURIER_ID_COLUMN: Final[str] = """
ALTER TABLE orders ADD COLUMN courier_id INTEGER REFERENCES users(id)
"""

CREATE_CASH_HANDOVERS_TABLE: Final[str] = """
CREATE TABLE IF NOT EXISTS cash_handovers (
    id INTEGER PRIMARY KEY,
    courier_id INTEGER REFERENCES users(id),
    cashier_id INTEGER REFERENCES users(id),
    total_amount NUMERIC(10,2),
    handed_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
"""

CREATE_PAYMENTS_TABLE: Final[str] = """
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY,
    order_id INTEGER REFERENCES orders(id),
    dealer_id INTEGER REFERENCES users(id),
    courier_id INTEGER REFERENCES users(id),
    amount NUMERIC(10,2),
    received_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    handover_id INTEGER REFERENCES cash_handovers(id)
)
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

        if not column_exists(cursor, "orders", "public_token"):
            cursor.execute(ADD_PUBLIC_TOKEN_COLUMN)
            print("Колонка public_token добавлена в таблицу orders.")
        else:
            print("Колонка public_token уже существует в таблице orders.")

        cursor.execute(BACKFILL_PUBLIC_TOKEN)
        print("public_token заполнен для заказов без токена.")

        cursor.execute(CREATE_PUBLIC_TOKEN_INDEX)
        print("Уникальный индекс ix_orders_public_token создан или уже существует.")

        if not column_exists(cursor, "users", "manager_id"):
            cursor.execute(ADD_USER_MANAGER_ID_COLUMN)
            print("Колонка manager_id добавлена в таблицу users.")
        else:
            print("Колонка manager_id уже существует в таблице users.")

        if not column_exists(cursor, "users", "phone"):
            cursor.execute(ADD_USER_PHONE_COLUMN)
            print("Колонка phone добавлена в таблицу users.")
        else:
            print("Колонка phone уже существует в таблице users.")

        if not column_exists(cursor, "orders", "dealer_id"):
            cursor.execute(ADD_DEALER_ID_COLUMN)
            print("Колонка dealer_id добавлена в таблицу orders.")
        else:
            print("Колонка dealer_id уже существует в таблице orders.")

        if not column_exists(cursor, "orders", "courier_id"):
            cursor.execute(ADD_COURIER_ID_COLUMN)
            print("Колонка courier_id добавлена в таблицу orders.")
        else:
            print("Колонка courier_id уже существует в таблице orders.")

        cursor.execute(CREATE_CASH_HANDOVERS_TABLE)
        print("Таблица cash_handovers создана или уже существует.")

        cursor.execute(CREATE_PAYMENTS_TABLE)
        print("Таблица payments создана или уже существует.")

        cursor.execute("SELECT id, name, phone, manager_id FROM installers")
        installers: list[tuple] = cursor.fetchall()
        dealer_password_hash: str = bcrypt.hashpw(
            b"dealer123", bcrypt.gensalt()
        ).decode("utf-8")

        for installer_id, name, phone, manager_id in installers:
            cursor.execute("SELECT id FROM users WHERE phone = ?", (phone,))
            existing_user: Optional[tuple] = cursor.fetchone()
            if existing_user is not None:
                continue

            phone_digits: str = "".join(ch for ch in (phone or "") if ch.isdigit())
            username: str = f"dealer_{phone_digits}"

            cursor.execute(
                """
                INSERT INTO users (
                    username, password_hash, full_name, role, phone, manager_id, is_active
                )
                VALUES (?, ?, ?, 'dealer', ?, ?, 1)
                """,
                (username, dealer_password_hash, name, phone, manager_id),
            )
            user_id: int = cursor.lastrowid

            cursor.execute(
                "UPDATE orders SET dealer_id = ? WHERE installer_id = ?",
                (user_id, installer_id),
            )

        print(f"Миграция installers → users: обработано {len(installers)} записей.")

        connection.commit()
    finally:
        connection.close()


if __name__ == "__main__":
    run_migrations()
