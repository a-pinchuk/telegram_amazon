from datetime import datetime
import zoneinfo

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User
from bot.db.repositories import report_repo
from bot.filters.role_filter import IsParticipant
from bot.services.notifications import notify_admins_new_report
from bot.keyboards.country_select import country_keyboard
from bot.keyboards.main_menu import BTN_EDIT_REPORT
from bot.states.report_states import EditReportFSM
from bot.services.country_data import COUNTRIES
from bot.keyboards.common import confirm_cancel_keyboard
from bot.utils.formatting import format_daily_report_preview
from aiogram.types import CallbackQuery

router = Router()
router.message.filter(IsParticipant())
router.callback_query.filter(IsParticipant())


def _get_today(tz_name: str = "Europe/Kiev"):
    return datetime.now(zoneinfo.ZoneInfo(tz_name)).date()


@router.message(F.text == BTN_EDIT_REPORT)
async def start_edit(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    today = _get_today()
    existing = await report_repo.get_report(session, db_user.id, today)

    if not existing or not existing.is_complete:
        await message.answer("⚠️ У вас нет отчета за сегодня. Сначала отправьте отчет.")
        return

    # Pre-populate with existing data
    listing_selected = [e.country_code for e in existing.listing_entries]
    instruction_selected = [e.country_code for e in existing.instruction_entries]

    await state.set_state(EditReportFSM.select_listing_countries)
    await state.update_data(
        selected_listing=listing_selected,
        listing_counts={},
        current_idx=0,
        total_instructions=existing.total_instructions,
        selected_instruction=instruction_selected,
        instruction_counts={},
    )

    await message.answer(
        "✏️ <b>Редактирование отчета за сегодня</b>\n\n"
        "📦 <b>Шаг 1/2 — Листинги</b>\n"
        "Выберите страны (предыдущий выбор сохранен).\n"
        "Нажмите /cancel для отмены.",
        reply_markup=country_keyboard("ecl", set(listing_selected)),
    )


# --- Cancel ---

@router.message(EditReportFSM(), F.text == "/cancel")
async def cancel_edit(message: Message, state: FSMContext):
    from bot.keyboards.main_menu import participant_menu
    await state.clear()
    await message.answer("❌ Редактирование отменено.", reply_markup=participant_menu())


# --- Step 1: Select listing countries ---

@router.callback_query(EditReportFSM.select_listing_countries, F.data.startswith("ecl:"))
async def toggle_listing(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":")[1]

    if code == "done":
        data = await state.get_data()
        selected = data["selected_listing"]
        if not selected:
            await callback.answer("Выберите хотя бы одну страну!", show_alert=True)
            return

        await state.update_data(current_idx=0)
        await state.set_state(EditReportFSM.enter_listing_count)
        first = COUNTRIES[selected[0]]
        await callback.message.edit_text(
            f"📦 Сколько листингов для <b>{first['flag']} {first['name']}</b>?"
        )
        await callback.answer()
        return

    data = await state.get_data()
    selected = data["selected_listing"]
    if code in selected:
        selected.remove(code)
    else:
        selected.append(code)
    await state.update_data(selected_listing=selected)
    await callback.message.edit_reply_markup(reply_markup=country_keyboard("ecl", set(selected)))
    await callback.answer()


# --- Step 1b: Enter listing counts ---

@router.message(EditReportFSM.enter_listing_count)
async def enter_listing_count(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return

    count = int(message.text.strip())
    data = await state.get_data()
    selected = data["selected_listing"]
    idx = data["current_idx"]
    counts = data["listing_counts"]
    counts[selected[idx]] = count
    idx += 1
    await state.update_data(listing_counts=counts, current_idx=idx)

    if idx < len(selected):
        c = COUNTRIES[selected[idx]]
        await message.answer(f"📦 Сколько листингов для <b>{c['flag']} {c['name']}</b>?")
    else:
        await state.set_state(EditReportFSM.enter_total_instructions)
        await message.answer("📝 Сколько инструкций создано всего?")


# --- Step 2a: Total instructions ---

@router.message(EditReportFSM.enter_total_instructions)
async def enter_total(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return

    count = int(message.text.strip())
    await state.update_data(total_instructions=count, selected_instruction=[], current_idx=0)
    await state.set_state(EditReportFSM.select_instruction_countries)

    data = await state.get_data()
    await message.answer(
        "📝 Выберите страны для инструкций:",
        reply_markup=country_keyboard("eci", set(data.get("selected_instruction", []))),
    )


# --- Step 2b: Select instruction countries ---

@router.callback_query(EditReportFSM.select_instruction_countries, F.data.startswith("eci:"))
async def toggle_instr(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":")[1]

    if code == "done":
        data = await state.get_data()
        selected = data["selected_instruction"]
        if not selected:
            await state.update_data(instruction_counts={})
            await _show_edit_confirmation(callback.message, state, edit=True)
            await callback.answer()
            return

        await state.update_data(current_idx=0)
        await state.set_state(EditReportFSM.enter_instruction_count)
        first = COUNTRIES[selected[0]]
        await callback.message.edit_text(
            f"📝 Сколько инструкций для <b>{first['flag']} {first['name']}</b>?"
        )
        await callback.answer()
        return

    data = await state.get_data()
    selected = data["selected_instruction"]
    if code in selected:
        selected.remove(code)
    else:
        selected.append(code)
    await state.update_data(selected_instruction=selected)
    await callback.message.edit_reply_markup(reply_markup=country_keyboard("eci", set(selected)))
    await callback.answer()


# --- Step 2c: Enter instruction counts ---

@router.message(EditReportFSM.enter_instruction_count)
async def enter_instr_count(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return

    count = int(message.text.strip())
    data = await state.get_data()
    selected = data["selected_instruction"]
    idx = data["current_idx"]
    counts = data["instruction_counts"]
    counts[selected[idx]] = count
    idx += 1
    await state.update_data(instruction_counts=counts, current_idx=idx)

    if idx < len(selected):
        c = COUNTRIES[selected[idx]]
        await message.answer(f"📝 Сколько инструкций для <b>{c['flag']} {c['name']}</b>?")
    else:
        await _show_edit_confirmation(message, state)


# --- Confirmation ---

async def _show_edit_confirmation(target: Message, state: FSMContext, edit: bool = False):
    data = await state.get_data()
    text = format_daily_report_preview(
        data["listing_counts"],
        data["total_instructions"],
        data["instruction_counts"],
    )
    text += "\n\nПодтвердить изменения?"
    await state.set_state(EditReportFSM.confirm_report)

    if edit:
        await target.edit_text(text, reply_markup=confirm_cancel_keyboard("erpt"))
    else:
        await target.answer(text, reply_markup=confirm_cancel_keyboard("erpt"))


@router.callback_query(EditReportFSM.confirm_report, F.data.startswith("erpt:"))
async def confirm_edit(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User, bot: Bot):
    action = callback.data.split(":")[1]

    if action == "no":
        await state.clear()
        await callback.message.edit_text("❌ Редактирование отменено.")
        await callback.answer()
        return

    data = await state.get_data()
    today = _get_today()

    existing = await report_repo.get_report(session, db_user.id, today)
    if existing:
        await report_repo.update_report(
            session, existing,
            total_instructions=data["total_instructions"],
            listing_data=data["listing_counts"],
            instruction_data=data["instruction_counts"],
        )

    await state.clear()
    await callback.message.edit_text("✅ Отчет обновлен!")
    await callback.answer("Сохранено!")

    # Notify admins about edit
    await notify_admins_new_report(
        bot, session, db_user,
        report_date=today.strftime("%d.%m.%Y"),
        listing_data=data["listing_counts"],
        total_instructions=data["total_instructions"],
        instruction_data=data["instruction_counts"],
        is_edit=True,
    )
