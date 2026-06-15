"""Точка входа FastAPI-приложения для отслеживания заказов."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import inspect, text

from app.database import Base, engine
from app.create_admin import create_initial_users
from app.migrate import run_migrations
from app.routers import analytics, auth, installers, integration, orders, qr, users


def _migrate_orders_table() -> None:
    """Добавляет новые колонки в существующую таблицу orders (SQLite)."""
    inspector = inspect(engine)
    if not inspector.has_table("orders"):
        return

    column_names = {col["name"] for col in inspector.get_columns("orders")}
    if "telegram_chat_id" not in column_names:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE orders ADD COLUMN telegram_chat_id VARCHAR(50)")
            )
    if "manager_id" not in column_names:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE orders ADD COLUMN manager_id INTEGER")
            )
    if "external_id" not in column_names:
        with engine.begin() as conn:
            conn.execute(
                text("ALTER TABLE orders ADD COLUMN external_id VARCHAR(100)")
            )
            conn.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS "
                    "ix_orders_external_id ON orders (external_id)"
                )
            )


run_migrations()

# Создание таблиц при первом запуске
Base.metadata.create_all(bind=engine)
_migrate_orders_table()
create_initial_users()

app = FastAPI(
    title="Blinds Tracker",
    description="Сервис отслеживания заказов жалюзи и штор",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


# CORS: разрешаем запросы к API с любого источника (для фронтенда)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(analytics.router)
app.include_router(users.router)
app.include_router(installers.router)
app.include_router(orders.router)
app.include_router(qr.router)
app.include_router(integration.router)

# Статические файлы фронтенда
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def root() -> RedirectResponse:
    """Редирект на страницу отслеживания заказа."""
    return RedirectResponse(url="/static/track.html")


@app.get("/health")
def health_check() -> dict[str, str]:
    """Проверка работоспособности сервиса."""
    return {"status": "ok"}
