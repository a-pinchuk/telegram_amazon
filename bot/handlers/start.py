from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.db.models import User
from bot.keyboards.main_menu import admin_menu, participant_menu

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User | None = None):
    if db_user is None:
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Вы не зарегистрированы в системе.\n"
            "Обратитесь к администратору для получения доступа."
        )
        return

    if db_user.role == "admin":
        await message.answer(
            f"👋 Привет, <b>{db_user.full_name}</b>!\n"
            "Вы вошли как <b>администратор</b>.",
            reply_markup=admin_menu(),
        )
    else:
        await message.answer(
            f"👋 Привет, <b>{db_user.full_name}</b>!\n"
            "Выберите действие:",
            reply_markup=participant_menu(),
        )
