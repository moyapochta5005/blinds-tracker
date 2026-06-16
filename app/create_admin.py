"""Скрипт начальной инициализации пользователей в базе данных."""

from app.database import Base, SessionLocal, engine
from app.models import Company, User
from app.security import hash_password

ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"
ADMIN_FULL_NAME = "Администратор"

TEST_MANAGERS: list[tuple[str, str, str]] = [
    ("manager1", "pass1", "Ахмед"),
    ("manager2", "pass2", "Магомед"),
    ("manager3", "pass3", "Расул"),
    ("manager4", "pass4", "Камиль"),
    ("manager5", "pass5", "Тимур"),
]


def create_initial_users() -> None:
    """Создаёт администратора и тестовых менеджеров, если их ещё нет."""
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        company = db.query(Company).filter(Company.slug == "shtora").first()
        if not company:
            company = Company(name="Штора", slug="shtora", is_active=True)
            db.add(company)
            db.flush()

        admin = db.query(User).filter(User.username == ADMIN_USERNAME).first()
        if admin is None:
            admin = User(
                username=ADMIN_USERNAME,
                password_hash=hash_password(ADMIN_PASSWORD),
                full_name=ADMIN_FULL_NAME,
                role="admin",
                is_active=True,
                company_id=company.id,
            )
            db.add(admin)
            print(f"Создан администратор: {ADMIN_USERNAME}")

        for username, password, full_name in TEST_MANAGERS:
            existing = db.query(User).filter(User.username == username).first()
            if existing is None:
                db.add(
                    User(
                        username=username,
                        password_hash=hash_password(password),
                        full_name=full_name,
                        role="manager",
                        is_active=True,
                        company_id=company.id,
                    )
                )
                print(f"Создан менеджер: {username} ({full_name})")

        superadmin = db.query(User).filter(User.username == "superadmin").first()
        if superadmin is None:
            db.add(User(
                username="superadmin",
                password_hash=hash_password("superadmin123"),
                full_name="Суперадминистратор",
                role="superadmin",
                is_active=True,
                company_id=None,
            ))
            print("Создан суперадмин: superadmin")

        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    create_initial_users()
