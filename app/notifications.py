"""Уведомления покупателю о смене статуса заказа через Telegram."""

from typing import Optional

# Эмодзи для каждого статуса заказа
STATUS_EMOJIS: dict[str, str] = {
    "new": "📋",
    "in_production": "🏭",
    "ready": "✅",
    "shipped": "🚚",
    "handed_to_courier": "🚚",
    "in_transit": "📦",
    "delivered": "🎉",
    "cancelled": "❌",
}

# Человекочитаемые названия статусов
STATUS_LABELS: dict[str, str] = {
    "new": "Принят",
    "in_production": "В производстве",
    "ready": "Готов",
    "shipped": "Отправлен",
    "handed_to_courier": "Передан курьеру",
    "in_transit": "В пути",
    "delivered": "Доставлен",
    "cancelled": "Отменён",
}


def format_status_notification(
    order_id: int,
    new_status: str,
    comment: Optional[str] = None,
) -> str:
    """Формирует текст уведомления о смене статуса заказа."""
    emoji = STATUS_EMOJIS.get(new_status, "📌")
    label = STATUS_LABELS.get(new_status, new_status)

    lines = [
        f"{emoji} <b>Статус заказа №{order_id} изменён</b>",
        "",
        f"Новый статус: <b>{label}</b>",
    ]

    if comment:
        lines.extend(["", f"💬 {comment}"])

    return "\n".join(lines)


def send_telegram_notification(
    chat_id: str,
    order_id: int,
    new_status: str,
    comment: Optional[str] = None,
) -> None:
    """
    Отправляет уведомление покупателю в Telegram.

    Пока заглушка — выводит сообщение в консоль.
    Реальная отправка через Bot API будет подключена позже.
    """
    message = format_status_notification(order_id, new_status, comment)
    print(f"[Telegram → chat_id={chat_id}]\n{message}")
