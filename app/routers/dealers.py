"""API-эндпоинты управления дилерами."""

from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth_middleware import get_current_user
from app.database import get_db
from app.models import User
from app.schemas import UserResponse
from app.security import hash_password

router = APIRouter(prefix="/dealers", tags=["dealers"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


class DealerCreate(BaseModel):
    """Схема создания дилера."""

    full_name: str
    phone: str
    password: str
    manager_id: Optional[int] = Field(
        default=None,
        description="ID менеджера (только для администратора)",
    )


class DealerUpdate(BaseModel):
    """Схема обновления данных дилера."""

    full_name: Optional[str] = None
    phone: Optional[str] = None
    is_active: Optional[bool] = None


def _require_admin_or_manager(current_user: dict[str, Any]) -> dict[str, Any]:
    """Разрешает доступ только администратору и менеджеру."""
    if current_user["role"] not in ("admin", "manager"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для администратора и менеджера",
        )
    return current_user


def _get_dealer_or_404(db: Session, dealer_id: int) -> User:
    """Возвращает дилера по ID или 404."""
    dealer = (
        db.query(User)
        .filter(User.id == dealer_id, User.role == "dealer")
        .first()
    )
    if dealer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Дилер не найден",
        )
    return dealer


def _check_dealer_access(dealer: User, current_user: dict[str, Any]) -> None:
    """Проверяет, что менеджер имеет доступ к дилеру."""
    if current_user["role"] == "admin":
        return
    if dealer.manager_id != current_user["manager_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этому дилеру",
        )


@router.get("", response_model=List[UserResponse])
def list_dealers(
    db: DbSession,
    current_user: CurrentUser,
) -> List[User]:
    """Получить список дилеров."""
    _require_admin_or_manager(current_user)

    query = db.query(User).filter(User.role == "dealer")

    if current_user["role"] == "manager":
        query = query.filter(User.manager_id == current_user["manager_id"])

    return query.order_by(User.full_name).all()


@router.get("/{dealer_id}", response_model=UserResponse)
def get_dealer(
    dealer_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> User:
    """Получить карточку дилера."""
    _require_admin_or_manager(current_user)

    dealer = _get_dealer_or_404(db, dealer_id)
    _check_dealer_access(dealer, current_user)
    return dealer


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_dealer(
    dealer_data: DealerCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> User:
    """Создать нового дилера."""
    _require_admin_or_manager(current_user)

    if current_user["role"] == "manager":
        manager_id = current_user["manager_id"]
    elif dealer_data.manager_id is not None:
        manager = (
            db.query(User)
            .filter(
                User.id == dealer_data.manager_id,
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
        manager_id = dealer_data.manager_id
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Укажите manager_id",
        )

    phone_digits = "".join(ch for ch in dealer_data.phone if ch.isdigit())
    username = f"dealer_{phone_digits}"

    existing = db.query(User).filter(User.username == username).first()
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Дилер с таким телефоном уже существует",
        )

    dealer = User(
        username=username,
        password_hash=hash_password(dealer_data.password),
        full_name=dealer_data.full_name,
        role="dealer",
        phone=dealer_data.phone,
        manager_id=manager_id,
        is_active=True,
    )
    db.add(dealer)
    db.commit()
    db.refresh(dealer)
    return dealer


@router.patch("/{dealer_id}", response_model=UserResponse)
def update_dealer(
    dealer_id: int,
    dealer_data: DealerUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> User:
    """Обновить данные дилера."""
    _require_admin_or_manager(current_user)

    dealer = _get_dealer_or_404(db, dealer_id)
    _check_dealer_access(dealer, current_user)

    if dealer_data.full_name is not None:
        dealer.full_name = dealer_data.full_name

    if dealer_data.phone is not None:
        dealer.phone = dealer_data.phone

    if dealer_data.is_active is not None:
        dealer.is_active = dealer_data.is_active

    db.commit()
    db.refresh(dealer)
    return dealer
