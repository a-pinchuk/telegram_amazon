from aiogram import F, Router
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User
from bot.filters.role_filter import IsRegistered
from bot.keyboards.main_menu import BTN_MY_STATS
from bot.keyboards.report_views import period_keyboard
from bot.services.report_service import build_report, get_period_dates

router = Router()
router.message.filter(IsRegistered())
router.callback_query.filter(IsRegistered())


@router.message(F.text == BTN_MY_STATS)
async def my_stats(message: Message):
    await message.answer(
        "📊 <b>Моя статистика</b>\n\nВыберите период:",
        reply_markup=period_keyboard(),
    )


@router.callback_query(F.data.startswith("period:"))
async def select_period(callback: CallbackQuery, session: AsyncSession, db_user: User):
    period = callback.data.split(":")[1]

    if period == "custom":
        await callback.answer("Пока недоступно — будет добавлено.", show_alert=True)
        return

    start_date, end_date, label = get_period_dates(period)
    report_text = await build_report(session, start_date, end_date, user_id=db_user.id)

    await callback.message.edit_text(report_text)
    await callback.answer()
