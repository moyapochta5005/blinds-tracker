"""Точка входа FastAPI-приложения для отслеживания заказов."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.database import Base, engine
from app.create_admin import create_initial_users
from app.routers import analytics, auth, cashier, couriers, dealers, integration, orders, qr, users

# Создание таблиц
Base.metadata.create_all(bind=engine)

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
app.include_router(dealers.router)
app.include_router(couriers.router)
app.include_router(cashier.router)
app.include_router(orders.router)
app.include_router(qr.router)
app.include_router(integration.router)

# Статические файлы фронтенда
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
def root() -> RedirectResponse:
    """Редирект на страницу входа."""
    return RedirectResponse(url="/static/login.html")


@app.get("/health")
def health_check() -> dict[str, str]:
    """Проверка работоспособности сервиса."""
    return {"status": "ok"}
