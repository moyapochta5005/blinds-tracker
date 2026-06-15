"""API-эндпоинты для интеграции с 1С."""

import os
import secrets
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.database import get_db
from app.models import Installer, Order, OrderStage, User
from app.notifications import send_telegram_notification
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
BASE_URL: str = os.getenv("BASE_URL", "https://track.tkani-05.ru")


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


def _build_tracking_url(public_token: str) -> str:
    """Формирует URL страницы отслеживания заказа."""
    return f"{BASE_URL}/static/track.html?order={public_token}"


def _build_qr_url(public_token: str) -> str:
    """Формирует относительный URL эндпоинта QR-кода."""
    return f"/orders/{public_token}/qr"


def _order_to_integration_response(order: Order) -> IntegrationOrderStatusResponse:
    """Преобразует модель заказа в ответ интеграционного API."""
    return IntegrationOrderStatusResponse(
        id=order.id,
        external_id=order.external_id,
        status=OrderStatus(order.status),
        updated_at=order.updated_at,
        tracking_url=_build_tracking_url(order.public_token),
        qr_url=_build_qr_url(order.public_token),
        stages=order.stages,
    )


def _resolve_installer(
    db: Session,
    installer_id: Optional[int],
    installer_phone: Optional[str],
) -> Optional[Installer]:
    """Находит активного установщика по ID или телефону."""
    if installer_id is not None:
        installer = (
            db.query(Installer)
            .filter(
                Installer.id == installer_id,
                Installer.is_active.is_(True),
            )
            .first()
        )
        return installer

    if installer_phone is not None:
        installer = (
            db.query(Installer)
            .filter(
                Installer.phone == installer_phone,
                Installer.is_active.is_(True),
            )
            .first()
        )
        return installer

    return None


def _resolve_dealer(
    db: Session,
    dealer_id: Optional[int],
    dealer_phone: Optional[str],
) -> Optional[User]:
    """Находит активного дилера по ID или телефону."""
    if dealer_id is not None:
        dealer = (
            db.query(User)
            .filter(
                User.id == dealer_id,
                User.role == "dealer",
                User.is_active.is_(True),
            )
            .first()
        )
        return dealer

    if dealer_phone is not None:
        dealer = (
            db.query(User)
            .filter(
                User.phone == dealer_phone,
                User.role == "dealer",
                User.is_active.is_(True),
            )
            .first()
        )
        return dealer

    return None


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

    installer = _resolve_installer(
        db,
        order_data.installer_id,
        order_data.installer_phone,
    )
    dealer = _resolve_dealer(
        db,
        order_data.dealer_id,
        order_data.dealer_phone,
    )
    installer_id: Optional[int] = None
    order_dealer_id: Optional[int] = None
    manager_id: Optional[int] = None
    if installer is not None:
        installer_id = installer.id
        manager_id = installer.manager_id
    if dealer is not None:
        order_dealer_id = dealer.id

    order = Order(
        external_id=order_data.external_id,
        public_token=secrets.token_hex(16),
        customer_name=order_data.customer_name,
        customer_phone=order_data.customer_phone,
        product_name=order_data.product_name,
        status=OrderStatus.NEW.value,
        manager_id=manager_id,
        installer_id=installer_id,
        dealer_id=order_dealer_id,
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
        tracking_url=_build_tracking_url(order.public_token),
        qr_url=_build_qr_url(order.public_token),
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
