"""API-эндпоинты управления компаниями (только для суперадмина)."""

from typing import Annotated, Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth_middleware import get_current_user
from app.database import get_db
from app.models import Company, User
from app.security import hash_password

router = APIRouter(prefix="/companies", tags=["companies"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[dict[str, Any], Depends(get_current_user)]


class CompanyCreate(BaseModel):
    """Схема создания компании."""

    name: str
    slug: str
    admin_username: str
    admin_password: str
    admin_full_name: str


class CompanyResponse(BaseModel):
    """Схема ответа компании."""

    id: int
    name: str
    slug: str
    is_active: bool
    created_at: str

    model_config = {"from_attributes": False}


class CompanyUpdate(BaseModel):
    """Схема обновления компании."""

    name: Optional[str] = None
    is_active: Optional[bool] = None


class CompanyRegister(BaseModel):
    """Схема публичной регистрации компании."""

    company_name: str
    admin_full_name: str
    admin_username: str
    admin_password: str
    admin_phone: Optional[str] = None


def _require_superadmin(current_user: dict[str, Any]) -> None:
    """Разрешает доступ только суперадмину."""
    if current_user["role"] != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для суперадмина",
        )


def _generate_slug(name: str) -> str:
    """Генерирует slug из названия компании (латиница + цифры + дефис)."""
    import re

    name = name.lower().strip()
    transliteration = {
        'а':'a','б':'b','в':'v','г':'g','д':'d','е':'e','ё':'yo',
        'ж':'zh','з':'z','и':'i','й':'y','к':'k','л':'l','м':'m',
        'н':'n','о':'o','п':'p','р':'r','с':'s','т':'t','у':'u',
        'ф':'f','х':'kh','ц':'ts','ч':'ch','ш':'sh','щ':'shch',
        'ъ':'','ы':'y','ь':'','э':'e','ю':'yu','я':'ya'
    }
    result = ''
    for char in name:
        result += transliteration.get(char, char)
    result = re.sub(r'[^a-z0-9]+', '-', result)
    result = result.strip('-')
    return result or 'company'


@router.get("", response_model=List[CompanyResponse])
def list_companies(
    db: DbSession,
    current_user: CurrentUser,
) -> list:
    """Получить список всех компаний."""
    _require_superadmin(current_user)
    companies = db.query(Company).order_by(Company.created_at.desc()).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "slug": c.slug,
            "is_active": c.is_active,
            "created_at": c.created_at.strftime("%d.%m.%Y"),
        }
        for c in companies
    ]


@router.post("", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(
    data: CompanyCreate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Создать новую компанию и admin-аккаунт для неё."""
    _require_superadmin(current_user)

    existing_company = db.query(Company).filter(Company.slug == data.slug).first()
    if existing_company is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Компания с таким slug уже существует",
        )

    existing_user = db.query(User).filter(User.username == data.admin_username).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким логином уже существует",
        )

    company = Company(name=data.name, slug=data.slug, is_active=True)
    db.add(company)
    db.flush()

    admin = User(
        username=data.admin_username,
        password_hash=hash_password(data.admin_password),
        full_name=data.admin_full_name,
        role="admin",
        is_active=True,
        company_id=company.id,
    )
    db.add(admin)
    db.commit()
    db.refresh(company)

    return {
        "id": company.id,
        "name": company.name,
        "slug": company.slug,
        "is_active": company.is_active,
        "created_at": company.created_at.strftime("%d.%m.%Y"),
    }


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register_company(
    data: CompanyRegister,
    db: DbSession,
) -> dict:
    """Публичная регистрация новой компании. Авторизация не требуется."""

    existing_user = db.query(User).filter(User.username == data.admin_username).first()
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким логином уже существует",
        )

    base_slug = _generate_slug(data.company_name)
    slug = base_slug
    counter = 1
    while db.query(Company).filter(Company.slug == slug).first() is not None:
        slug = f"{base_slug}-{counter}"
        counter += 1

    company = Company(name=data.company_name, slug=slug, is_active=True)
    db.add(company)
    db.flush()

    admin = User(
        username=data.admin_username,
        password_hash=hash_password(data.admin_password),
        full_name=data.admin_full_name,
        role="admin",
        is_active=True,
        phone=data.admin_phone,
        company_id=company.id,
    )
    db.add(admin)
    db.commit()
    db.refresh(company)

    return {
        "success": True,
        "company_id": company.id,
        "company_name": company.name,
        "slug": company.slug,
        "admin_username": data.admin_username,
    }


@router.patch("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int,
    data: CompanyUpdate,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Обновить название или статус компании."""
    _require_superadmin(current_user)

    company = db.query(Company).filter(Company.id == company_id).first()
    if company is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Компания не найдена",
        )

    if data.name is not None:
        company.name = data.name
    if data.is_active is not None:
        company.is_active = data.is_active

    db.commit()
    db.refresh(company)

    return {
        "id": company.id,
        "name": company.name,
        "slug": company.slug,
        "is_active": company.is_active,
        "created_at": company.created_at.strftime("%d.%m.%Y"),
    }
