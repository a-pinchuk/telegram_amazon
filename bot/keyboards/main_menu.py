from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Button text constants
BTN_SUBMIT_REPORT = "📝 Отправить отчет"
BTN_MY_STATS = "📊 Моя статистика"
BTN_EDIT_REPORT = "✏️ Редактировать отчет"
BTN_VIEW_REPORTS = "📊 Отчеты за период"
BTN_MANAGE_USERS = "👥 Управление участниками"


def participant_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SUBMIT_REPORT)],
            [KeyboardButton(text=BTN_MY_STATS), KeyboardButton(text=BTN_EDIT_REPORT)],
        ],
        resize_keyboard=True,
    )


def admin_menu() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_SUBMIT_REPORT)],
            [KeyboardButton(text=BTN_MY_STATS), KeyboardButton(text=BTN_EDIT_REPORT)],
            [KeyboardButton(text=BTN_VIEW_REPORTS), KeyboardButton(text=BTN_MANAGE_USERS)],
        ],
        resize_keyboard=True,
    )
