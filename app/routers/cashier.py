"""API-эндпоинты для кассира."""

from decimal import Decimal
from typing import Annotated, Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth_middleware import get_current_user
from app.database import get_db
from app.models import CashHandover, Payment, User
from app.schemas import CashHandoverOut, CourierUnsettledOut

router = APIRouter(prefix="/cashier", tags=["cashier"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


class CashHandoverCreate(BaseModel):
    """Схема приёма денег от курьера."""

    courier_id: int


def _require_cashier_or_admin(current_user: dict[str, Any]) -> dict[str, Any]:
    """Разрешает доступ кассиру и администратору."""
    if current_user["role"] not in ("cashier", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для кассира и администратора",
        )
    return current_user


def _require_cashier(current_user: dict[str, Any]) -> dict[str, Any]:
    """Разрешает доступ только кассиру."""
    if current_user["role"] != "cashier":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для кассира",
        )
    return current_user


def _current_user_id(current_user: dict[str, Any]) -> int:
    """Возвращает ID текущего пользователя из JWT."""
    return int(current_user["manager_id"])


def _handover_to_out(handover: CashHandover, courier_name: str) -> CashHandoverOut:
    """Формирует ответ с данными сдачи наличных."""
    return CashHandoverOut(
        id=handover.id,
        courier_id=handover.courier_id,
        courier_name=courier_name,
        cashier_id=handover.cashier_id,
        total_amount=handover.total_amount,
        handed_at=handover.handed_at,
    )


@router.get("/couriers", response_model=List[CourierUnsettledOut])
def list_couriers_with_unsettled(
    db: DbSession,
    current_user: CurrentUser,
) -> List[CourierUnsettledOut]:
    """Список курьеров с несданными остатками."""
    _require_cashier_or_admin(current_user)

    rows = (
        db.query(
            User.id,
            User.full_name,
            func.sum(Payment.amount).label("unsettled_amount"),
        )
        .join(Payment, Payment.courier_id == User.id)
        .filter(
            User.role == "courier",
            Payment.handover_id.is_(None),
        )
        .group_by(User.id, User.full_name)
        .all()
    )

    return [
        CourierUnsettledOut(
            courier_id=row.id,
            full_name=row.full_name,
            unsettled_amount=row.unsettled_amount,
        )
        for row in rows
    ]


@router.get("/handovers", response_model=List[CashHandoverOut])
def list_handovers(
    db: DbSession,
    current_user: CurrentUser,
) -> List[CashHandoverOut]:
    """История всех сдач наличных."""
    _require_cashier_or_admin(current_user)

    rows = (
        db.query(CashHandover, User.full_name)
        .join(User, User.id == CashHandover.courier_id)
        .order_by(CashHandover.handed_at.desc())
        .all()
    )

    return [
        _handover_to_out(handover, courier_name)
        for handover, courier_name in rows
    ]


@router.post("/handovers", response_model=CashHandoverOut, status_code=status.HTTP_201_CREATED)
def create_handover(
    handover_data: CashHandoverCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> CashHandoverOut:
    """Принять деньги от курьера."""
    _require_cashier(current_user)

    payments = (
        db.query(Payment)
        .filter(
            Payment.courier_id == handover_data.courier_id,
            Payment.handover_id.is_(None),
        )
        .all()
    )
    if not payments:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нет несданных платежей",
        )

    total_amount = sum((payment.amount for payment in payments), Decimal("0"))
    cashier_id = _current_user_id(current_user)

    handover = CashHandover(
        courier_id=handover_data.courier_id,
        cashier_id=cashier_id,
        total_amount=total_amount,
    )
    db.add(handover)
    db.flush()

    for payment in payments:
        payment.handover_id = handover.id

    db.commit()
    db.refresh(handover)

    courier = db.query(User).filter(User.id == handover_data.courier_id).first()
    courier_name = courier.full_name if courier else ""

    return _handover_to_out(handover, courier_name)
