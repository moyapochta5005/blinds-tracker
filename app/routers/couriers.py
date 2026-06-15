"""API-эндпоинты для курьеров."""

from decimal import Decimal
from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth_middleware import get_current_user
from app.database import get_db
from app.models import Order, Payment, User
from app.schemas import OrderResponse, PaymentOut, UserResponse

router = APIRouter(prefix="/couriers", tags=["couriers"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


class PaymentCreate(BaseModel):
    """Схема приёма оплаты от дилера."""

    order_id: int
    amount: Decimal = Field(..., gt=0)


class PaymentsTotalResponse(BaseModel):
    """Сумма несданных платежей курьера."""

    total: Decimal


def _require_admin_or_manager(current_user: dict[str, Any]) -> dict[str, Any]:
    """Разрешает доступ только администратору и менеджеру."""
    if current_user["role"] not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для администратора и менеджера",
        )
    return current_user


def _require_courier(current_user: dict[str, Any]) -> dict[str, Any]:
    """Разрешает доступ только курьеру."""
    if current_user["role"] != "courier":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для курьера",
        )
    return current_user


def _current_user_id(current_user: dict[str, Any]) -> int:
    """Возвращает ID текущего пользователя из JWT."""
    return int(current_user["manager_id"])


@router.get("", response_model=List[UserResponse])
def list_couriers(
    db: DbSession,
    current_user: CurrentUser,
) -> List[User]:
    """Получить список курьеров."""
    _require_admin_or_manager(current_user)

    return (
        db.query(User)
        .filter(User.role == "courier")
        .order_by(User.full_name)
        .all()
    )


@router.get("/orders", response_model=List[OrderResponse])
def list_courier_orders(
    db: DbSession,
    current_user: CurrentUser,
) -> List[Order]:
    """Получить заказы текущего курьера."""
    _require_courier(current_user)

    courier_id = _current_user_id(current_user)
    return (
        db.query(Order)
        .filter(Order.courier_id == courier_id)
        .order_by(Order.created_at.desc())
        .all()
    )


@router.post("/payments", response_model=PaymentOut, status_code=status.HTTP_201_CREATED)
def create_payment(
    payment_data: PaymentCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> Payment:
    """Принять оплату от дилера по заказу."""
    _require_courier(current_user)

    courier_id = _current_user_id(current_user)
    order = db.query(Order).filter(Order.id == payment_data.order_id).first()
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден",
        )

    if order.courier_id != courier_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Заказ не назначен этому курьеру",
        )

    if order.dealer_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У заказа не указан дилер",
        )

    payment = Payment(
        order_id=payment_data.order_id,
        dealer_id=order.dealer_id,
        courier_id=courier_id,
        amount=payment_data.amount,
    )
    db.add(payment)
    db.commit()
    db.refresh(payment)
    return payment


@router.get("/payments/total", response_model=PaymentsTotalResponse)
def get_unsettled_payments_total(
    db: DbSession,
    current_user: CurrentUser,
) -> PaymentsTotalResponse:
    """Получить сумму несданных платежей текущего курьера."""
    _require_courier(current_user)

    courier_id = _current_user_id(current_user)
    total = (
        db.query(func.sum(Payment.amount))
        .filter(
            Payment.courier_id == courier_id,
            Payment.handover_id.is_(None),
        )
        .scalar()
    )
    return PaymentsTotalResponse(total=total or Decimal("0"))


@router.get("/payments", response_model=List[PaymentOut])
def list_courier_payments(
    db: DbSession,
    current_user: CurrentUser,
    unsettled: Optional[bool] = Query(default=None),
) -> List[Payment]:
    """Получить список платежей текущего курьера."""
    _require_courier(current_user)

    courier_id = _current_user_id(current_user)
    query = db.query(Payment).filter(Payment.courier_id == courier_id)

    if unsettled is True:
        query = query.filter(Payment.handover_id.is_(None))

    return query.order_by(Payment.received_at.desc()).all()
