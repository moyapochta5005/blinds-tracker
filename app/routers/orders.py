"""API-эндпоинты для работы с заказами."""

from typing import Annotated, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.auth_middleware import get_current_user
from app.database import get_db
from app.models import Order, OrderStage
from app.notifications import send_telegram_notification
from app.schemas import OrderCreate, OrderResponse, OrderStatusUpdate

router = APIRouter(prefix="/orders", tags=["orders"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict[str, str], Depends(get_current_user)]


@router.get("", response_model=List[OrderResponse])
def list_orders(db: DbSession, current_user: CurrentUser) -> List[Order]:
    """Получить список всех заказов с этапами."""
    return (
        db.query(Order)
        .options(joinedload(Order.stages))
        .order_by(Order.updated_at.desc())
        .all()
    )


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: DbSession) -> Order:
    """Получить заказ по идентификатору."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден",
        )
    return order


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    order_data: OrderCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> Order:
    """Создать новый заказ."""
    order = Order(
        customer_name=order_data.customer_name,
        customer_phone=order_data.customer_phone,
        product_name=order_data.product_name,
        status=order_data.status.value,
        telegram_chat_id=order_data.telegram_chat_id,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return order


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: int,
    status_update: OrderStatusUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> Order:
    """Обновить статус заказа и зафиксировать этап в истории."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден",
        )

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

    return order
