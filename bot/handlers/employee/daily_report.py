from datetime import datetime
import zoneinfo

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from aiogram import Bot

from bot.db.models import User
from bot.db.repositories import report_repo
from bot.filters.role_filter import IsParticipant
from bot.services.notifications import notify_admins_new_report
from bot.keyboards.common import confirm_cancel_keyboard
from bot.keyboards.country_select import country_keyboard
from bot.keyboards.main_menu import BTN_SUBMIT_REPORT, participant_menu
from bot.services.country_data import COUNTRIES, ALL_COUNTRY_CODES
from bot.states.report_states import DailyReportFSM
from bot.utils.formatting import format_daily_report_preview

router = Router()
router.message.filter(IsParticipant())
router.callback_query.filter(IsParticipant())


def _get_today(tz_name: str = "Europe/Kyiv"):
    return datetime.now(zoneinfo.ZoneInfo(tz_name)).date()


# --- Cancel handler ---

@router.message(DailyReportFSM(), F.text == "/cancel")
async def cancel_report(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=participant_menu())


@router.callback_query(DailyReportFSM(), F.data == "cancel")
async def cancel_report_cb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("❌ Отменено.")
    await callback.answer()


# --- Entry point ---

@router.message(F.text == BTN_SUBMIT_REPORT)
async def start_report(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    today = _get_today()
    existing = await report_repo.get_report(session, db_user.id, today)

    if existing and existing.is_complete:
        await message.answer(
            "⚠️ Вы уже отправили отчет за сегодня.\n"
            "Используйте «✏️ Редактировать отчет» для изменений."
        )
        return

    await state.set_state(DailyReportFSM.select_listing_countries)
    await state.update_data(
        selected_listing=[],
        listing_counts={},
        current_idx=0,
        total_instructions=0,
        selected_instruction=[],
        instruction_counts={},
    )

    await message.answer(
        "📦 <b>Шаг 1/2 — Листинги</b>\n\n"
        "Выберите страны, для которых вы создали листинги сегодня.\n"
        "Нажмите /cancel для отмены.",
        reply_markup=country_keyboard("cl"),
    )


# --- Step 1: Select listing countries ---

@router.callback_query(DailyReportFSM.select_listing_countries, F.data.startswith("cl:"))
async def toggle_listing_country(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":")[1]

    if code == "done":
        data = await state.get_data()
        selected = data["selected_listing"]

        if not selected:
            await callback.answer("Выберите хотя бы одну страну!", show_alert=True)
            return

        # Move to entering counts
        await state.update_data(current_idx=0)
        await state.set_state(DailyReportFSM.enter_listing_count)

        first_code = selected[0]
        c = COUNTRIES[first_code]
        await callback.message.edit_text(
            f"📦 Сколько листингов вы создали для <b>{c['flag']} {c['name']}</b>?"
        )
        await callback.answer()
        return

    # Toggle country selection
    data = await state.get_data()
    selected = data["selected_listing"]
    if code in selected:
        selected.remove(code)
    else:
        selected.append(code)
    await state.update_data(selected_listing=selected)

    await callback.message.edit_reply_markup(
        reply_markup=country_keyboard("cl", set(selected))
    )
    await callback.answer()


# --- Step 1b: Enter listing count per country ---

@router.message(DailyReportFSM.enter_listing_count)
async def enter_listing_count(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return

    count = int(message.text.strip())
    if count < 0:
        await message.answer("⚠️ Число не может быть отрицательным.")
        return

    data = await state.get_data()
    selected = data["selected_listing"]
    idx = data["current_idx"]
    counts = data["listing_counts"]

    current_code = selected[idx]
    counts[current_code] = count
    idx += 1

    await state.update_data(listing_counts=counts, current_idx=idx)

    if idx < len(selected):
        # Ask for next country
        next_code = selected[idx]
        c = COUNTRIES[next_code]
        await message.answer(
            f"📦 Сколько листингов вы создали для <b>{c['flag']} {c['name']}</b>?"
        )
    else:
        # Move to Step 2: Instructions
        await state.set_state(DailyReportFSM.enter_total_instructions)
        await message.answer(
            "📝 <b>Шаг 2/2 — Инструкции</b>\n\n"
            "Сколько инструкций вы создали сегодня (всего)?"
        )


# --- Step 2a: Enter total instructions ---

@router.message(DailyReportFSM.enter_total_instructions)
async def enter_total_instructions(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return

    count = int(message.text.strip())
    if count < 0:
        await message.answer("⚠️ Число не может быть отрицательным.")
        return

    await state.update_data(total_instructions=count, selected_instruction=[], current_idx=0)
    await state.set_state(DailyReportFSM.select_instruction_countries)

    await message.answer(
        "📝 Выберите страны, в которые вы загрузили инструкции:",
        reply_markup=country_keyboard("ci"),
    )


# --- Step 2b: Select instruction countries ---

@router.callback_query(DailyReportFSM.select_instruction_countries, F.data.startswith("ci:"))
async def toggle_instruction_country(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":")[1]

    if code == "done":
        data = await state.get_data()
        selected = data["selected_instruction"]

        if not selected:
            # No instruction uploads — go straight to confirmation
            await state.update_data(instruction_counts={})
            await _show_confirmation(callback.message, state, edit=True)
            await callback.answer()
            return

        await state.update_data(current_idx=0)
        await state.set_state(DailyReportFSM.enter_instruction_count)

        first_code = selected[0]
        c = COUNTRIES[first_code]
        await callback.message.edit_text(
            f"📝 Сколько инструкций загружено для <b>{c['flag']} {c['name']}</b>?"
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

    await callback.message.edit_reply_markup(
        reply_markup=country_keyboard("ci", set(selected))
    )
    await callback.answer()


# --- Step 2c: Enter instruction count per country ---

@router.message(DailyReportFSM.enter_instruction_count)
async def enter_instruction_count(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return

    count = int(message.text.strip())
    if count < 0:
        await message.answer("⚠️ Число не может быть отрицательным.")
        return

    data = await state.get_data()
    selected = data["selected_instruction"]
    idx = data["current_idx"]
    counts = data["instruction_counts"]

    current_code = selected[idx]
    counts[current_code] = count
    idx += 1

    await state.update_data(instruction_counts=counts, current_idx=idx)

    if idx < len(selected):
        next_code = selected[idx]
        c = COUNTRIES[next_code]
        await message.answer(
            f"📝 Сколько инструкций загружено для <b>{c['flag']} {c['name']}</b>?"
        )
    else:
        await _show_confirmation(message, state)


# --- Confirmation ---

async def _show_confirmation(target: Message, state: FSMContext, edit: bool = False):
    data = await state.get_data()
    text = format_daily_report_preview(
        data["listing_counts"],
        data["total_instructions"],
        data["instruction_counts"],
    )
    text += "\n\nПодтвердить отправку?"
    await state.set_state(DailyReportFSM.confirm_report)

    if edit:
        await target.edit_text(text, reply_markup=confirm_cancel_keyboard("rpt"))
    else:
        await target.answer(text, reply_markup=confirm_cancel_keyboard("rpt"))


@router.callback_query(DailyReportFSM.confirm_report, F.data.startswith("rpt:"))
async def confirm_report(callback: CallbackQuery, state: FSMContext, session: AsyncSession, db_user: User, bot: Bot):
    action = callback.data.split(":")[1]

    if action == "no":
        await state.clear()
        await callback.message.edit_text("❌ Отчет отменен.")
        await callback.answer()
        return

    data = await state.get_data()
    today = _get_today()

    existing = await report_repo.get_report(session, db_user.id, today)
    if existing:
        await report_repo.update_report(
            session,
            existing,
            total_instructions=data["total_instructions"],
            listing_data=data["listing_counts"],
            instruction_data=data["instruction_counts"],
        )
    else:
        await report_repo.create_report(
            session,
            user_id=db_user.id,
            report_date=today,
            total_instructions=data["total_instructions"],
            listing_data=data["listing_counts"],
            instruction_data=data["instruction_counts"],
        )

    await state.clear()
    await callback.message.edit_text("✅ Отчет успешно сохранен!")
    await callback.answer("Сохранено!")

    # Notify admins
    await notify_admins_new_report(
        bot, session, db_user,
        report_date=today.strftime("%d.%m.%Y"),
        listing_data=data["listing_counts"],
        total_instructions=data["total_instructions"],
        instruction_data=data["instruction_counts"],
    )
