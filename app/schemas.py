"""Pydantic-схемы для валидации и сериализации данных API."""

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self


class LoginRequest(BaseModel):
    """Схема запроса на вход в систему."""

    username: str
    password: str


class LoginResponse(BaseModel):
    """Схема ответа с JWT-токеном после успешного входа."""

    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class OrderStatus(str, Enum):
    """Допустимые статусы заказа."""

    NEW = "new"
    IN_PRODUCTION = "in_production"
    READY = "ready"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class OrderStageBase(BaseModel):
    """Базовые поля этапа заказа."""

    stage_name: str
    comment: Optional[str] = None


class OrderStageCreate(OrderStageBase):
    """Схема создания этапа заказа."""

    pass


class OrderStageResponse(OrderStageBase):
    """Схема ответа с данными этапа заказа."""

    id: int
    order_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderBase(BaseModel):
    """Базовые поля заказа."""

    customer_name: str
    customer_phone: str
    product_name: str


class OrderCreate(OrderBase):
    """Схема создания нового заказа."""

    status: OrderStatus = OrderStatus.NEW
    telegram_chat_id: Optional[str] = None


class OrderStatusUpdate(BaseModel):
    """Схема обновления статуса заказа."""

    status: OrderStatus
    comment: Optional[str] = None


class OrderResponse(OrderBase):
    """Схема ответа с данными заказа."""

    id: int
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    stages: List[OrderStageResponse] = []
    qr_url: str = Field(
        default="",
        description="URL эндпоинта PNG QR-кода для отслеживания заказа",
        json_schema_extra={"example": "/orders/1/qr"},
    )

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def populate_qr_url(self) -> Self:
        """Заполняет URL QR-кода на основе идентификатора заказа."""
        self.qr_url = f"/orders/{self.id}/qr"
        return self
