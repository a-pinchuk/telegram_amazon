from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.db.models import User
from bot.keyboards.main_menu import admin_menu, participant_menu

router = Router()

HELP_PARTICIPANT = (
    "📖 <b>Как пользоваться ботом</b>\n\n"
    "<b>📝 Отправить отчет</b> — ежедневный отчет за день:\n"
    "  1. 📋 Обработано — выберите страны и количество\n"
    "  2. ✅ Выставлено — выберите страны и количество\n"
    "  3. 🚫 Заблокировано — страны, количество и причина\n"
    "  4. 📝 Инструкции — общее кол-во + по странам\n"
    "  5. Проверьте и подтвердите отчет\n\n"
    "На каждом шаге можно пропустить (нажать Готово без выбора).\n\n"
    "<b>📊 Моя статистика</b> — посмотреть свою статистику за период\n\n"
    "<b>✏️ Редактировать отчет</b> — изменить отчет за сегодня\n"
    "(можно редактировать только текущий день)\n\n"
    "<b>/cancel</b> — отменить текущее действие\n"
    "<b>/start</b> — вернуться в главное меню"
)

HELP_ADMIN = (
    "📖 <b>Как пользоваться ботом (администратор)</b>\n\n"
    "У вас есть все функции сотрудника + администрирование.\n\n"
    "<b>📊 Отчеты за период</b> — сформировать отчет:\n"
    "  1. Выберите период (сегодня, вчера, неделя, месяц или свои даты)\n"
    "  2. Выберите сотрудника или всех\n"
    "  3. Получите сводку: обработано, выставлено, заблокировано, инструкции\n\n"
    "<b>👥 Управление участниками</b>:\n"
    "  • Добавить сотрудника — нужен его Telegram ID\n"
    "    (сотрудник может узнать свой ID через @userinfobot)\n"
    "  • Удалить сотрудника — нажмите на имя в списке\n\n"
    "Когда сотрудник отправляет отчет, вам придет уведомление."
)


@router.message(CommandStart())
async def cmd_start(message: Message, db_user: User | None = None):
    if db_user is None:
        await message.answer(
            "👋 Добро пожаловать!\n\n"
            "Вы не зарегистрированы в системе.\n"
            "Обратитесь к администратору для получения доступа.\n\n"
            "Чтобы вас добавили, отправьте администратору свой Telegram ID.\n"
            "Узнать его можно через @userinfobot"
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


@router.message(Command("help"))
async def cmd_help(message: Message, db_user: User | None = None):
    if db_user and db_user.role == "admin":
        await message.answer(HELP_ADMIN)
    else:
        await message.answer(HELP_PARTICIPANT)
