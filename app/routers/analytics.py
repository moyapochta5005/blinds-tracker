"""API-эндпоинты аналитики для дашборда."""

from datetime import datetime, timedelta
from typing import Annotated, Any, Dict, List, Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.auth_middleware import get_current_user
from app.database import get_db
from app.models import Installer, Order, User
from app.schemas import (
    DashboardResponse,
    DayOrderCount,
    InstallerOrderCount,
    ManagerOrderCount,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]

PeriodType = Literal["day", "week", "month", "all"]

ORDER_STATUSES: List[str] = [
    "new",
    "in_production",
    "ready",
    "handed_to_courier",
    "in_transit",
    "delivered",
]


def _period_start(period: PeriodType) -> Optional[datetime]:
    """Возвращает начало периода для фильтра по created_at или None для «всё время»."""
    now = datetime.utcnow()
    if period == "day":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        return now - timedelta(days=7)
    if period == "month":
        return now - timedelta(days=30)
    return None


def _apply_scope(
    query: Any,
    current_user: dict[str, Any],
    period_start: Optional[datetime],
) -> Any:
    """Применяет фильтр по менеджеру и периоду создания заказа."""
    if current_user["role"] == "manager":
        query = query.filter(Order.manager_id == current_user["manager_id"])
    if period_start is not None:
        query = query.filter(Order.created_at >= period_start)
    return query


def _delivered_at(order: Order) -> datetime:
    """Момент доставки: этап delivered или updated_at как fallback."""
    for stage in order.stages:
        if stage.stage_name == "delivered":
            return stage.created_at
    return order.updated_at


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    db: DbSession,
    current_user: CurrentUser,
    period: PeriodType = Query(default="month", description="Период фильтрации"),
) -> DashboardResponse:
    """Агрегированные метрики дашборда для администратора или менеджера."""
    period_start = _period_start(period)

    base_query = _apply_scope(db.query(Order), current_user, period_start)
    total_orders = base_query.count()

    status_rows = (
        _apply_scope(
            db.query(Order.status, func.count(Order.id)),
            current_user,
            period_start,
        )
        .group_by(Order.status)
        .all()
    )
    orders_by_status: Dict[str, int] = {status: 0 for status in ORDER_STATUSES}
    for status, count in status_rows:
        if status in orders_by_status:
            orders_by_status[status] = count

    orders_by_manager: List[ManagerOrderCount] = []
    if current_user["role"] == "admin":
        manager_query = (
            db.query(User.id, User.full_name, func.count(Order.id))
            .join(Order, Order.manager_id == User.id)
        )
        if period_start is not None:
            manager_query = manager_query.filter(Order.created_at >= period_start)
        manager_rows = (
            manager_query
            .group_by(User.id, User.full_name)
            .order_by(func.count(Order.id).desc())
            .all()
        )
        orders_by_manager = [
            ManagerOrderCount(
                manager_id=manager_id,
                manager_name=full_name,
                count=count,
            )
            for manager_id, full_name, count in manager_rows
        ]

    delivered_orders = (
        _apply_scope(
            db.query(Order).options(joinedload(Order.stages)),
            current_user,
            period_start,
        )
        .filter(Order.status == "delivered")
        .all()
    )
    average_completion_days: Optional[float] = None
    if delivered_orders:
        total_days = sum(
            (_delivered_at(order) - order.created_at).total_seconds() / 86400
            for order in delivered_orders
        )
        average_completion_days = round(total_days / len(delivered_orders), 1)

    day_rows = (
        _apply_scope(
            db.query(
                func.date(Order.created_at).label("day"),
                func.count(Order.id),
            ),
            current_user,
            period_start,
        )
        .group_by(func.date(Order.created_at))
        .order_by(func.date(Order.created_at))
        .all()
    )
    orders_by_day = [
        DayOrderCount(date=str(day), count=count) for day, count in day_rows
    ]

    installer_query = (
        db.query(Installer.id, Installer.name, func.count(Order.id))
        .join(Order, Order.installer_id == Installer.id)
    )
    if current_user["role"] == "manager":
        installer_query = installer_query.filter(
            Order.manager_id == current_user["manager_id"]
        )
    if period_start is not None:
        installer_query = installer_query.filter(Order.created_at >= period_start)
    installer_rows = (
        installer_query
        .group_by(Installer.id, Installer.name)
        .order_by(func.count(Order.id).desc())
        .limit(10)
        .all()
    )
    top_installers = [
        InstallerOrderCount(
            installer_id=installer_id,
            installer_name=installer_name,
            count=count,
        )
        for installer_id, installer_name, count in installer_rows
    ]

    return DashboardResponse(
        total_orders=total_orders,
        orders_by_status=orders_by_status,
        orders_by_manager=orders_by_manager,
        average_completion_days=average_completion_days,
        orders_by_day=orders_by_day,
        top_installers=top_installers,
    )
