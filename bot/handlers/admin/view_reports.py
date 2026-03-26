from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories.user_repo import get_all_active_participants
from bot.filters.role_filter import IsAdmin
from bot.keyboards.main_menu import BTN_VIEW_REPORTS, admin_menu
from bot.keyboards.report_views import employee_list_keyboard, period_keyboard
from bot.services.report_service import build_employee_breakdown, build_report, get_period_dates
from bot.states.report_states import AdminReportFSM

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == BTN_VIEW_REPORTS)
async def view_reports(message: Message, state: FSMContext):
    await state.set_state(AdminReportFSM.select_period)
    await message.answer(
        "📊 <b>Отчеты</b>\n\nВыберите период:",
        reply_markup=period_keyboard(),
    )


# --- Period selection ---

@router.callback_query(AdminReportFSM.select_period, F.data.startswith("period:"))
async def select_period(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    period = callback.data.split(":")[1]

    if period == "custom":
        await state.set_state(AdminReportFSM.enter_start_date)
        await callback.message.edit_text(
            "📅 Введите начальную дату (формат: ДД.ММ.ГГГГ):"
        )
        await callback.answer()
        return

    start_date, end_date, label = get_period_dates(period)
    await state.update_data(start_date=start_date.isoformat(), end_date=end_date.isoformat())

    # Show employee selection
    participants = await get_all_active_participants(session)
    await state.set_state(AdminReportFSM.select_employee)
    await callback.message.edit_text(
        f"📊 Период: <b>{label}</b>\n\nВыберите сотрудника:",
        reply_markup=employee_list_keyboard(participants),
    )
    await callback.answer()


# --- Custom date range ---

@router.message(AdminReportFSM.enter_start_date)
async def enter_start_date(message: Message, state: FSMContext):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except (ValueError, AttributeError):
        await message.answer("⚠️ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:")
        return

    await state.update_data(start_date=dt.isoformat())
    await state.set_state(AdminReportFSM.enter_end_date)
    await message.answer("📅 Введите конечную дату (формат: ДД.ММ.ГГГГ):")


@router.message(AdminReportFSM.enter_end_date)
async def enter_end_date(message: Message, state: FSMContext, session: AsyncSession):
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except (ValueError, AttributeError):
        await message.answer("⚠️ Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:")
        return

    await state.update_data(end_date=dt.isoformat())

    participants = await get_all_active_participants(session)
    await state.set_state(AdminReportFSM.select_employee)
    await message.answer(
        "Выберите сотрудника:",
        reply_markup=employee_list_keyboard(participants),
    )


# --- Employee selection and report ---

@router.callback_query(AdminReportFSM.select_employee, F.data.startswith("emp:"))
async def select_employee(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    value = callback.data.split(":")[1]

    if value == "cancel":
        await state.clear()
        await callback.message.edit_text("🔙 Отменено.")
        await callback.answer()
        return

    data = await state.get_data()
    from datetime import date as date_type
    start_date = date_type.fromisoformat(data["start_date"])
    end_date = date_type.fromisoformat(data["end_date"])

    user_id = None if value == "all" else int(value)

    report_text = await build_report(session, start_date, end_date, user_id=user_id)

    # Add employee breakdown for "all" view
    if value == "all":
        breakdown = await build_employee_breakdown(session, start_date, end_date)
        report_text += "\n" + breakdown

    await state.clear()

    # Split message if too long
    if len(report_text) <= 4096:
        await callback.message.edit_text(report_text)
    else:
        await callback.message.edit_text(report_text[:4096])
        remaining = report_text[4096:]
        while remaining:
            chunk = remaining[:4096]
            await callback.message.answer(chunk)
            remaining = remaining[4096:]

    await callback.answer()
