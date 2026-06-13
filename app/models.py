"""SQLAlchemy-модели для пользователей, заказов и этапов их обработки."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """Пользователь системы (администратор или менеджер)."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    orders = relationship("Order", back_populates="manager")


class Order(Base):
    """Заказ на изготовление жалюзи или штор."""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(100), nullable=True, unique=True, index=True)
    customer_name = Column(String(255), nullable=False)
    customer_phone = Column(String(50), nullable=False)
    product_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="new")
    telegram_chat_id = Column(String(50), nullable=True)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    manager = relationship("User", back_populates="orders")
    stages = relationship(
        "OrderStage",
        back_populates="order",
        cascade="all, delete-orphan",
    )


class OrderStage(Base):
    """Этап обработки заказа (история изменений статуса)."""

    __tablename__ = "order_stages"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False, index=True)
    stage_name = Column(String(100), nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    order = relationship("Order", back_populates="stages")
