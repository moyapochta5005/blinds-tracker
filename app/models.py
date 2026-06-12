"""SQLAlchemy-модели для заказов и этапов их обработки."""

from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Order(Base):
    """Заказ на изготовление жалюзи или штор."""

    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    customer_name = Column(String(255), nullable=False)
    customer_phone = Column(String(50), nullable=False)
    product_name = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False, default="new")
    telegram_chat_id = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )

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
