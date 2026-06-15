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
    manager_id: int
    full_name: str


class UserCreate(BaseModel):
    """Схема создания менеджера."""

    username: str
    password: str
    full_name: str


class UserUpdate(BaseModel):
    """Схема обновления данных менеджера."""

    username: Optional[str] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    is_active: Optional[bool] = None


class UserRole(str, Enum):
    """Допустимые роли пользователя."""

    ADMIN = "admin"
    MANAGER = "manager"
    DEALER = "dealer"
    COURIER = "courier"
    CASHIER = "cashier"


class UserResponse(BaseModel):
    """Схема ответа с данными пользователя."""

    id: int
    username: str
    full_name: str
    role: UserRole
    manager_id: Optional[int] = None
    phone: Optional[str] = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class InstallerBase(BaseModel):
    name: str
    phone: Optional[str] = None


class InstallerCreate(InstallerBase):
    pass


class InstallerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


class InstallerOut(InstallerBase):
    id: int
    manager_id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


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

    customer_phone: str = Field(
        ...,
        pattern=r"^\+7\d{10}$",
        description="Телефон клиента в формате +7XXXXXXXXXX",
    )
    status: OrderStatus = OrderStatus.NEW
    telegram_chat_id: Optional[str] = None
    comment: Optional[str] = None
    manager_id: Optional[int] = Field(
        default=None,
        description="ID менеджера (только для администратора)",
    )
    installer_id: Optional[int] = None


class OrderStatusUpdate(BaseModel):
    """Схема обновления статуса заказа."""

    status: OrderStatus
    comment: Optional[str] = None


class OrderResponse(OrderBase):
    """Схема ответа с данными заказа."""

    id: int
    external_id: Optional[str] = None
    public_token: Optional[str] = None
    status: OrderStatus
    manager_id: Optional[int] = None
    manager_name: Optional[str] = None
    installer: Optional[InstallerOut] = None
    created_at: datetime
    updated_at: datetime
    stages: List[OrderStageResponse] = []
    qr_url: str = Field(
        default="",
        description="URL эндпоинта PNG QR-кода для отслеживания заказа",
        json_schema_extra={"example": "/orders/a1b2c3d4e5f6789012345678abcdef01/qr"},
    )

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode="after")
    def populate_qr_url(self) -> Self:
        """Заполняет URL QR-кода на основе public_token заказа."""
        self.qr_url = f"/orders/{self.public_token}/qr"
        return self


class IntegrationOrderCreate(BaseModel):
    """Схема создания заказа из 1С."""

    external_id: str = Field(..., min_length=1, max_length=100)
    customer_name: str
    customer_phone: str = Field(
        ...,
        pattern=r"^\+7\d{10}$",
        description="Телефон клиента в формате +7XXXXXXXXXX",
    )
    product_name: str
    installer_id: Optional[int] = Field(
        default=None,
        description="ID установщика в трекере (приоритетный способ)",
    )
    installer_phone: Optional[str] = Field(
        default=None,
        description="Телефон установщика для поиска (если ID неизвестен)",
    )
    comment: Optional[str] = None


class IntegrationOrderCreateResponse(BaseModel):
    """Ответ после создания заказа из 1С."""

    id: int
    tracking_url: str
    qr_url: str


class IntegrationOrderStatusUpdate(BaseModel):
    """Схема обновления статуса заказа из 1С."""

    status: OrderStatus
    comment: Optional[str] = None


class IntegrationOrderStatusResponse(BaseModel):
    """Статус заказа для интеграции с 1С."""

    id: int
    external_id: str
    status: OrderStatus
    updated_at: datetime
    tracking_url: str
    qr_url: str
    stages: List[OrderStageResponse] = []


class ManagerOrderCount(BaseModel):
    """Количество заказов по менеджеру."""

    manager_id: int
    manager_name: str
    count: int


class DayOrderCount(BaseModel):
    """Количество заказов за день."""

    date: str
    count: int


class InstallerOrderCount(BaseModel):
    """Количество заказов по установщику."""

    installer_id: int
    installer_name: str
    count: int


class DashboardResponse(BaseModel):
    """Агрегированные метрики дашборда аналитики."""

    total_orders: int
    orders_by_status: dict[str, int]
    orders_by_manager: List[ManagerOrderCount]
    average_completion_days: Optional[float] = None
    orders_by_day: List[DayOrderCount]
    top_installers: List[InstallerOrderCount]
