"""Telegram-бот для отслеживания заказов и подписки на уведомления."""

import logging
import os
import re
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session, joinedload
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.database import SessionLocal
from app.models import Order
from app.notifications import STATUS_EMOJIS, STATUS_LABELS

# Этапы заказа в порядке прохождения (как на странице track.html)
TRACKING_STAGES: list[tuple[str, str]] = [
    ("new", "Принят"),
    ("in_production", "В производстве"),
    ("ready", "Готов"),
    ("handed_to_courier", "Передан курьеру"),
    ("in_transit", "В пути"),
    ("delivered", "Доставлен"),
]

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def _format_date(iso_dt: datetime) -> str:
    """Форматирует дату этапа для отображения в боте."""
    return iso_dt.strftime("%d.%m.%Y %H:%M")


def _build_order_message(order: Order) -> str:
    """Собирает сообщение с текущим статусом и таймлайном заказа."""
    emoji = STATUS_EMOJIS.get(order.status, "📌")
    status_label = STATUS_LABELS.get(order.status, order.status)

    lines = [
        f"📦 <b>Заказ №{order.id}</b>",
        f"Товар: {order.product_name}",
        f"Покупатель: {order.customer_name}",
        "",
        f"{emoji} <b>Текущий статус:</b> {status_label}",
        "",
        "<b>История доставки:</b>",
    ]

    stages_map: dict[str, object] = {}
    for stage in order.stages:
        stages_map[stage.stage_name] = stage

    current_index = next(
        (i for i, (key, _) in enumerate(TRACKING_STAGES) if key == order.status),
        -1,
    )

    for index, (key, label) in enumerate(TRACKING_STAGES):
        stage = stages_map.get(key)
        stage_emoji = STATUS_EMOJIS.get(key, "○")

        if current_index >= 0 and index < current_index:
            marker = "✓"
        elif index == current_index:
            marker = "▶"
        else:
            marker = "○"

        line = f"{marker} {stage_emoji} {label}"
        if stage is not None:
            line += f" — {_format_date(stage.created_at)}"
            if stage.comment:
                line += f"\n   💬 {stage.comment}"
        lines.append(line)

    return "\n".join(lines)


def _get_order(db: Session, order_id: int) -> Optional[Order]:
    """Загружает заказ с этапами из базы данных."""
    return (
        db.query(Order)
        .options(joinedload(Order.stages))
        .filter(Order.id == order_id)
        .first()
    )


def _link_chat_to_order(db: Session, order: Order, chat_id: int) -> None:
    """Привязывает Telegram chat_id к заказу для уведомлений."""
    order.telegram_chat_id = str(chat_id)
    db.commit()


async def _reply_order_status(
    update: Update,
    order: Order,
    *,
    subscribed: bool = False,
) -> None:
    """Отправляет пользователю статус заказа."""
    message = _build_order_message(order)
    if subscribed:
        message += (
            "\n\n🔔 Вы подписаны на уведомления об изменении статуса этого заказа."
        )
    await update.message.reply_text(message, parse_mode=ParseMode.HTML)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start. Поддерживает deep link: /start <номер_заказа>."""
    chat_id = update.effective_chat.id

    if context.args:
        try:
            order_id = int(context.args[0])
        except ValueError:
            await update.message.reply_text(
                "Некорректный номер заказа. Используйте: /track <номер>"
            )
            return

        db = SessionLocal()
        try:
            order = _get_order(db, order_id)
            if order is None:
                await update.message.reply_text(
                    f"Заказ №{order_id} не найден. Проверьте номер и попробуйте снова."
                )
                return

            _link_chat_to_order(db, order, chat_id)
            await _reply_order_status(update, order, subscribed=True)
        finally:
            db.close()
        return

    await update.message.reply_text(
        "👋 Добро пожаловать в Blinds Tracker!\n\n"
        "Я помогу отслеживать статус вашего заказа.\n\n"
        "Команды:\n"
        "• /track <номер> — статус и история заказа\n"
        "• Отправьте номер заказа (число) — то же самое\n\n"
        "Чтобы подписаться на уведомления, нажмите кнопку "
        "«Получать уведомления в Telegram» на странице отслеживания."
    )


async def track_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /track <номер_заказа>."""
    if not context.args:
        await update.message.reply_text(
            "Укажите номер заказа: /track 123"
        )
        return

    try:
        order_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text(
            "Некорректный номер заказа. Пример: /track 123"
        )
        return

    db = SessionLocal()
    try:
        order = _get_order(db, order_id)
        if order is None:
            await update.message.reply_text(
                f"Заказ №{order_id} не найден. Проверьте номер и попробуйте снова."
            )
            return
        await _reply_order_status(update, order)
    finally:
        db.close()


async def order_number_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обработчик сообщения с номером заказа (просто число)."""
    text = update.message.text.strip()
    if not re.fullmatch(r"\d+", text):
        return

    order_id = int(text)
    db = SessionLocal()
    try:
        order = _get_order(db, order_id)
        if order is None:
            await update.message.reply_text(
                f"Заказ №{order_id} не найден. Проверьте номер и попробуйте снова."
            )
            return
        await _reply_order_status(update, order)
    finally:
        db.close()


def main() -> None:
    """Запускает Telegram-бота в режиме long polling."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "Переменная окружения TELEGRAM_BOT_TOKEN не задана. "
            "Укажите токен бота перед запуском."
        )

    application = (
        Application.builder()
        .token(token)
        .build()
    )

    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("track", track_command))
    application.add_handler(
        MessageHandler(filters.Regex(r"^\d+$"), order_number_handler)
    )

    logger.info("Бот запущен")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
