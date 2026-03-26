from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def confirm_cancel_keyboard(prefix: str = "confirm") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"{prefix}:yes"),
                InlineKeyboardButton(text="❌ Отмена", callback_data=f"{prefix}:no"),
            ]
        ]
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
        ]
    )
