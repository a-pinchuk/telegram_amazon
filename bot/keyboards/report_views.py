from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.db.models import User


def period_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Сегодня", callback_data="period:today"),
                InlineKeyboardButton(text="Вчера", callback_data="period:yesterday"),
            ],
            [
                InlineKeyboardButton(text="Эта неделя", callback_data="period:week"),
                InlineKeyboardButton(text="Этот месяц", callback_data="period:month"),
            ],
            [
                InlineKeyboardButton(text="Выбрать даты", callback_data="period:custom"),
            ],
        ]
    )


def employee_list_keyboard(users: list[User], include_all: bool = True) -> InlineKeyboardMarkup:
    buttons = []
    if include_all:
        buttons.append([InlineKeyboardButton(text="👥 Все сотрудники", callback_data="emp:all")])

    for user in users:
        buttons.append([
            InlineKeyboardButton(text=user.full_name, callback_data=f"emp:{user.id}")
        ])

    buttons.append([InlineKeyboardButton(text="❌ Отмена", callback_data="emp:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def user_manage_keyboard(users: list[User]) -> InlineKeyboardMarkup:
    buttons = []
    for user in users:
        label = f"❌ {user.full_name} (@{user.username})" if user.username else f"❌ {user.full_name}"
        buttons.append([
            InlineKeyboardButton(text=label, callback_data=f"rm_user:{user.id}")
        ])
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data="rm_user:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
