"""API-эндпоинты для генерации QR-кодов отслеживания заказов."""

import io
from typing import Annotated

import qrcode
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Order

router = APIRouter(prefix="/orders", tags=["qr"])

DbSession = Annotated[Session, Depends(get_db)]

# Базовый URL страницы отслеживания для QR-кода
TRACK_PAGE_BASE_URL = "http://localhost:8001/static/track.html"


@router.get("/{public_token}/qr")
def get_order_qr(public_token: str, db: DbSession) -> Response:
    """Сгенерировать PNG QR-кода со ссылкой на отслеживание заказа."""
    order = db.query(Order).filter(Order.public_token == public_token).first()
    if order is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Заказ не найден",
        )

    track_url = f"{TRACK_PAGE_BASE_URL}?order={order.public_token}"

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(track_url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    return Response(content=buffer.getvalue(), media_type="image/png")
