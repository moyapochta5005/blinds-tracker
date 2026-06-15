"""API-эндпоинты для работы с заказами."""

import secrets
from datetime import datetime
from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session, joinedload

from app.auth_middleware import get_current_user, get_optional_user
from app.database import get_db
from app.models import Order, OrderStage, User
from app.notifications import send_telegram_notification
from app.schemas import OrderCreate, OrderResponse, OrderStatus, OrderStatusUpdate


class OrderTrackStageResponse(BaseModel):
    """Публичный этап заказа для страницы отслеживания."""

    stage_name: str
    comment: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OrderTrackResponse(BaseModel):
    """Публичный ответ для отслеживания заказа по токену."""

    id: int
    external_id: Optional[str] = None
    public_token: Optional[str] = None
    product_name: str
    status: OrderStatus
    created_at: datetime
    updated_at: datetime
    stages: List[OrderTrackStageResponse] = []

    model_config = ConfigDict(from_attributes=True)

router = APIRouter(prefix="/orders", tags=["orders"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]
OptionalUser = Annotated[Optional[dict[str, Any]], Depends(get_optional_user)]


def _order_to_response(order: Order) -> OrderResponse:
    """Преобразует модель заказа в ответ API с именем менеджера."""
    response = OrderResponse.model_validate(order)
    if order.manager is not None:
        response.manager_name = order.manager.full_name
    return response


def _check_order_access(order: Order, current_user: Optional[dict[str, Any]]) -> None:
    """
    Проверяет доступ к заказу.

    Без токена доступ публичный (страница отслеживания).
    Менеджер видит только свои заказы, администратор — все.
    """
    if current_user is None:
        return

    role = current_user["role"]
    if role == "admin":
        return

    if role == "manager" and order.manager_id == current_user["manager_id"]:
        return

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Нет доступа к этому заказу",
    )


@router.get("", response_model=List[OrderResponse])
def list_orders(
    db: DbSession,
    current_user: CurrentUser,
    manager_id: Optional[int] = Query(
        default=None,
        description="Фильтр по менеджеру (только для администратора)",
    ),
) -> List[OrderResponse]:
    """Получить список заказов с учётом роли пользователя."""
    query = db.query(Order).options(joinedload(Order.manager), joinedload(Order.stages))

    if current_user["role"] == "manager":
        query = query.filter(Order.manager_id == current_user["manager_id"])
    elif current_user["role"] == "dealer":
        query = query.filter(Order.dealer_id == current_user["manager_id"])
    elif manager_id is not None:
        query = query.filter(Order.manager_id == manager_id)

    orders = query.order_by(Order.updated_at.desc()).all()
    return [_order_to_response(order) for order in orders]


@router.get("/track/{public_token}", response_model=OrderTrackResponse)
def track_order(public_token: str, db: DbSession) -> OrderTrackResponse:
    """Публичное отслеживание заказа по токену (без авторизации)."""
    order = (
        db.query(Order)
        .options(joinedload(Order.stages))
        .filter(Order.public_token == public_token)
        .first()
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден",
        )
    return OrderTrackResponse.model_validate(order)


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> OrderResponse:
    """Получить заказ по идентификатору."""
    order = (
        db.query(Order)
        .options(joinedload(Order.manager), joinedload(Order.stages))
        .filter(Order.id == order_id)
        .first()
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден",
        )

    _check_order_access(order, current_user)
    return _order_to_response(order)


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    order_data: OrderCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> OrderResponse:
    """Создать новый заказ и привязать к менеджеру."""
    manager_id: Optional[int] = None
    if current_user["role"] == "manager":
        manager_id = current_user["manager_id"]
    elif order_data.manager_id is not None:
        manager = (
            db.query(User)
            .filter(
                User.id == order_data.manager_id,
                User.role == "manager",
                User.is_active.is_(True),
            )
            .first()
        )
        if manager is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Менеджер не найден или неактивен",
            )
        manager_id = order_data.manager_id

    order_dealer_id: Optional[int] = None
    if order_data.dealer_id is not None:
        order_dealer_id = order_data.dealer_id
    elif order_data.installer_id is not None:
        order_dealer_id = order_data.installer_id

    order = Order(
        public_token=secrets.token_hex(16),
        customer_name=order_data.customer_name,
        customer_phone=order_data.customer_phone,
        product_name=order_data.product_name,
        status=order_data.status.value,
        telegram_chat_id=order_data.telegram_chat_id,
        manager_id=manager_id,
        dealer_id=order_dealer_id,
    )
    db.add(order)
    db.flush()

    if order_data.comment:
        stage = OrderStage(
            order_id=order.id,
            stage_name=order_data.status.value,
            comment=order_data.comment,
        )
        db.add(stage)

    db.commit()
    db.refresh(order)

    order = (
        db.query(Order)
        .options(joinedload(Order.manager), joinedload(Order.stages))
        .filter(Order.id == order.id)
        .first()
    )
    return _order_to_response(order)


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> OrderResponse:
    """Обновить статус заказа и зафиксировать этап в истории."""
    order = (
        db.query(Order)
        .options(joinedload(Order.manager), joinedload(Order.stages))
        .filter(Order.id == order_id)
        .first()
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден",
        )

    _check_order_access(order, current_user)

    order.status = status_update.status.value

    # Каждое изменение статуса сохраняется как отдельный этап
    stage = OrderStage(
        order_id=order.id,
        stage_name=status_update.status.value,
        comment=status_update.comment,
    )
    db.add(stage)
    db.commit()
    db.refresh(order)

    if order.telegram_chat_id:
        send_telegram_notification(
            chat_id=order.telegram_chat_id,
            order_id=order.id,
            new_status=status_update.status.value,
            comment=status_update.comment,
        )

    order = (
        db.query(Order)
        .options(joinedload(Order.manager), joinedload(Order.stages))
        .filter(Order.id == order.id)
        .first()
    )
    return _order_to_response(order)
