from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, Update
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories.user_repo import get_user_by_telegram_id


def _extract_user_and_event(update: TelegramObject):
    """Extract the Telegram user and inner event from an Update or direct event."""
    if isinstance(update, Update):
        if update.message:
            return update.message.from_user, update.message
        if update.callback_query:
            return update.callback_query.from_user, update.callback_query
        return None, None
    if isinstance(update, (Message, CallbackQuery)):
        return update.from_user, update
    return None, None


class AuthMiddleware(BaseMiddleware):
    def __init__(self, admin_ids: list[int] | None = None):
        self.admin_ids = admin_ids or []

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session: AsyncSession = data["session"]

        tg_user, inner_event = _extract_user_and_event(event)

        if tg_user is None:
            return await handler(event, data)

        db_user = await get_user_by_telegram_id(session, tg_user.id)

        # Auto-create admin on /start if telegram_id is in ADMIN_IDS
        if db_user is None and tg_user.id in self.admin_ids:
            from bot.db.repositories.user_repo import create_user

            db_user = await create_user(
                session,
                telegram_id=tg_user.id,
                full_name=tg_user.full_name or "Admin",
                username=tg_user.username,
                role="admin",
            )
            await session.commit()

        data["db_user"] = db_user

        # Allow /start for unregistered users (so they see a message)
        if db_user is None:
            if isinstance(inner_event, Message) and inner_event.text and inner_event.text.startswith("/start"):
                return await handler(event, data)
            if isinstance(inner_event, Message):
                await inner_event.answer("❌ Вы не зарегистрированы. Обратитесь к администратору.")
                return
            if isinstance(inner_event, CallbackQuery):
                await inner_event.answer("Вы не зарегистрированы.", show_alert=True)
                return

        return await handler(event, data)
