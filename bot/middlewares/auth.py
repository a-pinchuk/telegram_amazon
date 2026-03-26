from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories.user_repo import get_user_by_telegram_id


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

        # Extract user from event
        user = None
        if isinstance(event, (Message, CallbackQuery)):
            user = event.from_user

        if user is None:
            return await handler(event, data)

        db_user = await get_user_by_telegram_id(session, user.id)

        # Auto-create admin on /start if telegram_id is in ADMIN_IDS
        if db_user is None and user.id in self.admin_ids:
            from bot.db.repositories.user_repo import create_user

            db_user = await create_user(
                session,
                telegram_id=user.id,
                full_name=user.full_name or "Admin",
                username=user.username,
                role="admin",
            )
            await session.commit()

        data["db_user"] = db_user

        # Allow /start for unregistered users (so they see a message)
        if db_user is None:
            if isinstance(event, Message) and event.text and event.text.startswith("/start"):
                return await handler(event, data)
            if isinstance(event, Message):
                await event.answer("❌ Вы не зарегистрированы. Обратитесь к администратору.")
                return
            if isinstance(event, CallbackQuery):
                await event.answer("Вы не зарегистрированы.", show_alert=True)
                return

        return await handler(event, data)
