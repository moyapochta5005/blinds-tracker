"""SQLAlchemy-модели для пользователей, заказов и этапов их обработки."""

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    """Пользователь системы (admin, manager, dealer, courier, cashier)."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    phone = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    orders = relationship(
        "Order",
        foreign_keys="Order.manager_id",
        back_populates="manager",
    )
    installers = relationship("Installer", back_populates="manager")


class Installer(Base):
    __tablename__ = "installers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    phone = Column(String, nullable=True)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    manager = relationship("User", back_populates="installers")
    orders = relationship("Order", back_populates="installer")


class Order(Base):
    """Заказ на изготовление жалюзи или штор."""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    external_id = Column(String(100), nullable=True, unique=True, index=True)
    public_token = Column(String(32), unique=True, nullable=True, index=True)
    customer_name = Column(String(255), nullable=False)
    customer_phone = Column(String(50), nullable=False)
    product_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="new")
    telegram_chat_id = Column(String(50), nullable=True)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    installer_id = Column(Integer, ForeignKey("installers.id"), nullable=True)
    dealer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    courier_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

    manager = relationship("User", foreign_keys=[manager_id], back_populates="orders")
    dealer = relationship("User", foreign_keys=[dealer_id])
    courier = relationship("User", foreign_keys=[courier_id])
    installer = relationship("Installer", back_populates="orders")
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
