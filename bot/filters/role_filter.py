from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery

from bot.db.models import User


class IsAdmin(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, db_user: User | None = None) -> bool:
        return db_user is not None and db_user.role == "admin" and db_user.is_active


class IsParticipant(BaseFilter):
    async def __call__(self, event: Message | CallbackQuery, db_user: User | None = None) -> bool:
        return db_user is not None and db_user.role == "participant" and db_user.is_active
