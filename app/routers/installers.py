"""API-эндпоинты для управления установщиками."""

from typing import Annotated, Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth_middleware import get_current_user
from app.database import get_db
from app import models, schemas

router = APIRouter(prefix="/installers", tags=["installers"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


def _get_installer_or_404(db: Session, installer_id: int) -> models.Installer:
    """Возвращает установщика по ID или 404."""
    installer = (
        db.query(models.Installer)
        .filter(models.Installer.id == installer_id)
        .first()
    )
    if installer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Установщик не найден",
        )
    return installer


def _check_installer_ownership(
    installer: models.Installer,
    current_user: dict[str, Any],
) -> None:
    """Проверяет, что установщик принадлежит текущему пользователю (кроме admin)."""
    if current_user["role"] == "admin":
        return
    if installer.manager_id != current_user["manager_id"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нет доступа к этому установщику",
        )


@router.get("", response_model=List[schemas.InstallerOut])
def list_installers(db: DbSession, current_user: CurrentUser) -> List[models.Installer]:
    """Список установщиков: менеджер — только свои, администратор — все."""
    query = db.query(models.Installer)

    if current_user["role"] == "manager":
        query = query.filter(
            models.Installer.manager_id == current_user["manager_id"]
        )

    return query.order_by(models.Installer.name).all()


@router.post(
    "",
    response_model=schemas.InstallerOut,
    status_code=status.HTTP_201_CREATED,
)
def create_installer(
    installer_data: schemas.InstallerCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> models.Installer:
    """Создать установщика, привязанного к текущему пользователю."""
    installer = models.Installer(
        name=installer_data.name,
        phone=installer_data.phone,
        manager_id=current_user["manager_id"],
        is_active=True,
    )
    db.add(installer)
    db.commit()
    db.refresh(installer)
    return installer


@router.patch("/{installer_id}", response_model=schemas.InstallerOut)
def update_installer(
    installer_id: int,
    installer_data: schemas.InstallerUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> models.Installer:
    """Обновить данные установщика (только своего)."""
    installer = _get_installer_or_404(db, installer_id)
    _check_installer_ownership(installer, current_user)

    if installer_data.name is not None:
        installer.name = installer_data.name

    if installer_data.phone is not None:
        installer.phone = installer_data.phone

    if installer_data.is_active is not None:
        installer.is_active = installer_data.is_active

    db.commit()
    db.refresh(installer)
    return installer


@router.delete("/{installer_id}", response_model=schemas.InstallerOut)
def deactivate_installer(
    installer_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> models.Installer:
    """Деактивировать установщика (мягкое удаление, только своего)."""
    installer = _get_installer_or_404(db, installer_id)
    _check_installer_ownership(installer, current_user)

    installer.is_active = False
    db.commit()
    db.refresh(installer)
    return installer
