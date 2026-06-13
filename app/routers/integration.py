"""API-эндпоинты для интеграции с 1С."""

import os
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Order, OrderStage, User
from app.notifications import send_telegram_notification
from app.routers.qr import TRACK_PAGE_BASE_URL
from app.schemas import (
    IntegrationOrderCreate,
    IntegrationOrderCreateResponse,
    IntegrationOrderStatusResponse,
    IntegrationOrderStatusUpdate,
    OrderStatus,
)

router = APIRouter(
    prefix="/api/v1/integration",
    tags=["integration"],
)

DbSession = Annotated[Session, Depends(get_db)]

INTEGRATION_API_KEY: str = os.getenv("INTEGRATION_API_KEY", "")


def verify_integration_api_key(
    x_api_key: Annotated[str, Header(alias="X-API-Key")],
) -> None:
    """Проверяет API-ключ интеграции из заголовка X-API-Key."""
    if not INTEGRATION_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="INTEGRATION_API_KEY не настроен на сервере",
        )
    if x_api_key != INTEGRATION_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный API-ключ",
        )


ApiKeyAuth = Annotated[None, Depends(verify_integration_api_key)]


def _build_tracking_url(order_id: int) -> str:
    """Формирует URL страницы отслеживания заказа."""
    return f"{TRACK_PAGE_BASE_URL}?order={order_id}"


def _build_qr_url(order_id: int) -> str:
    """Формирует относительный URL эндпоинта QR-кода."""
    return f"/orders/{order_id}/qr"


def _order_to_integration_response(order: Order) -> IntegrationOrderStatusResponse:
    """Преобразует модель заказа в ответ интеграционного API."""
    return IntegrationOrderStatusResponse(
        id=order.id,
        external_id=order.external_id,
        status=OrderStatus(order.status),
        updated_at=order.updated_at,
        tracking_url=_build_tracking_url(order.id),
        qr_url=_build_qr_url(order.id),
        stages=order.stages,
    )


def _get_order_by_external_id(db: Session, external_id: str) -> Order:
    """Возвращает заказ по external_id или выбрасывает 404."""
    order = (
        db.query(Order)
        .options(joinedload(Order.stages))
        .filter(Order.external_id == external_id)
        .first()
    )
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ с таким external_id не найден",
        )
    return order


@router.post(
    "/orders",
    response_model=IntegrationOrderCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_order_from_1c(
    order_data: IntegrationOrderCreate,
    db: DbSession,
    _: ApiKeyAuth,
) -> IntegrationOrderCreateResponse:
    """Создать заказ из 1С по external_id."""
    existing = (
        db.query(Order)
        .filter(Order.external_id == order_data.external_id)
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Заказ с external_id «{order_data.external_id}» уже существует",
        )

    manager_id: Optional[int] = None
    if order_data.manager_username is not None:
        manager = (
            db.query(User)
            .filter(
                User.username == order_data.manager_username,
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
        manager_id = manager.id

    order = Order(
        external_id=order_data.external_id,
        customer_name=order_data.customer_name,
        customer_phone=order_data.customer_phone,
        product_name=order_data.product_name,
        status=OrderStatus.NEW.value,
        manager_id=manager_id,
    )
    db.add(order)
    db.flush()

    if order_data.comment:
        stage = OrderStage(
            order_id=order.id,
            stage_name=OrderStatus.NEW.value,
            comment=order_data.comment,
        )
        db.add(stage)

    db.commit()
    db.refresh(order)

    return IntegrationOrderCreateResponse(
        id=order.id,
        tracking_url=_build_tracking_url(order.id),
        qr_url=_build_qr_url(order.id),
    )


@router.patch(
    "/orders/{external_id}/status",
    response_model=IntegrationOrderStatusResponse,
)
def update_order_status_from_1c(
    external_id: str,
    status_update: IntegrationOrderStatusUpdate,
    db: DbSession,
    _: ApiKeyAuth,
) -> IntegrationOrderStatusResponse:
    """Обновить статус заказа по external_id из 1С."""
    order = _get_order_by_external_id(db, external_id)

    order.status = status_update.status.value

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
        .options(joinedload(Order.stages))
        .filter(Order.id == order.id)
        .first()
    )
    return _order_to_integration_response(order)


@router.get(
    "/orders/{external_id}",
    response_model=IntegrationOrderStatusResponse,
)
def get_order_status_from_1c(
    external_id: str,
    db: DbSession,
    _: ApiKeyAuth,
) -> IntegrationOrderStatusResponse:
    """Получить статус заказа по external_id из 1С."""
    order = _get_order_by_external_id(db, external_id)
    return _order_to_integration_response(order)
