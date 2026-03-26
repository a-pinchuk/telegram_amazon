from datetime import datetime
import zoneinfo

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User, LISTING_PROCESSED, LISTING_PUBLISHED, LISTING_BLOCKED
from bot.db.repositories import report_repo
from bot.filters.role_filter import IsRegistered
from bot.services.notifications import notify_admins_new_report
from bot.keyboards.country_select import country_keyboard
from bot.keyboards.main_menu import BTN_EDIT_REPORT, participant_menu, admin_menu
from bot.states.report_states import EditReportFSM
from bot.services.country_data import COUNTRIES
from bot.keyboards.common import confirm_cancel_keyboard
from bot.utils.formatting import format_daily_report_preview

router = Router()
router.message.filter(IsRegistered())
router.callback_query.filter(IsRegistered())


def _get_today(tz_name: str = "Europe/Kyiv"):
    return datetime.now(zoneinfo.ZoneInfo(tz_name)).date()


def _get_menu(db_user: User):
    return admin_menu() if db_user.role == "admin" else participant_menu()


@router.message(F.text == BTN_EDIT_REPORT)
async def start_edit(message: Message, state: FSMContext, session: AsyncSession, db_user: User):
    today = _get_today()
    existing = await report_repo.get_report(session, db_user.id, today)

    if not existing or not existing.is_complete:
        await message.answer("⚠️ У вас нет отчета за сегодня. Сначала отправьте отчет.")
        return

    # Pre-populate from existing
    processed_sel = [e.country_code for e in existing.listing_entries if e.listing_type == LISTING_PROCESSED]
    published_sel = [e.country_code for e in existing.listing_entries if e.listing_type == LISTING_PUBLISHED]
    blocked_sel = [e.country_code for e in existing.listing_entries if e.listing_type == LISTING_BLOCKED]
    instr_sel = [e.country_code for e in existing.instruction_entries]

    await state.set_state(EditReportFSM.select_processed_countries)
    await state.update_data(
        processed_countries=processed_sel, processed_counts={},
        published_countries=published_sel, published_counts={},
        blocked_countries=blocked_sel, blocked_counts={}, blocked_reasons={},
        total_instructions=existing.total_instructions,
        instruction_countries=instr_sel, instruction_counts={},
        current_idx=0,
    )

    await message.answer(
        "✏️ <b>Редактирование отчета за сегодня</b>\n\n"
        "📋 <b>Шаг 1/4 — Обработано</b>\n"
        "Выберите страны (предыдущий выбор сохранен).\n"
        "Нажмите /cancel для отмены.",
        reply_markup=country_keyboard("ecp", set(processed_sel)),
    )


# --- Cancel ---

@router.message(EditReportFSM(), F.text == "/cancel")
async def cancel_edit(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    await message.answer("❌ Редактирование отменено.", reply_markup=_get_menu(db_user))


# ==========================================
# STEP 1a: PROCESSED
# ==========================================

@router.callback_query(EditReportFSM.select_processed_countries, F.data.startswith("ecp:"))
async def toggle_processed(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":")[1]
    if code == "done":
        data = await state.get_data()
        selected = data["processed_countries"]
        if not selected:
            await _start_edit_published(callback.message, state, edit=True)
            await callback.answer()
            return
        await state.update_data(current_idx=0)
        await state.set_state(EditReportFSM.enter_processed_count)
        c = COUNTRIES[selected[0]]
        await callback.message.edit_text(f"📋 Обработано для <b>{c['flag']} {c['name']}</b>?")
        await callback.answer()
        return

    data = await state.get_data()
    selected = data["processed_countries"]
    if code in selected:
        selected.remove(code)
    else:
        selected.append(code)
    await state.update_data(processed_countries=selected)
    await callback.message.edit_reply_markup(reply_markup=country_keyboard("ecp", set(selected)))
    await callback.answer()


@router.message(EditReportFSM.enter_processed_count)
async def enter_processed(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return
    count = int(message.text.strip())
    data = await state.get_data()
    sel = data["processed_countries"]
    idx = data["current_idx"]
    counts = data["processed_counts"]
    counts[sel[idx]] = count
    idx += 1
    await state.update_data(processed_counts=counts, current_idx=idx)
    if idx < len(sel):
        c = COUNTRIES[sel[idx]]
        await message.answer(f"📋 Обработано для <b>{c['flag']} {c['name']}</b>?")
    else:
        await _start_edit_published(message, state)


# ==========================================
# STEP 1b: PUBLISHED
# ==========================================

async def _start_edit_published(target: Message, state: FSMContext, edit: bool = False):
    data = await state.get_data()
    await state.set_state(EditReportFSM.select_published_countries)
    await state.update_data(current_idx=0)
    text = "✅ <b>Шаг 2/4 — Выставлено</b>\nВыберите страны:"
    kb = country_keyboard("ecu", set(data.get("published_countries", [])))
    if edit:
        await target.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(EditReportFSM.select_published_countries, F.data.startswith("ecu:"))
async def toggle_published(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":")[1]
    if code == "done":
        data = await state.get_data()
        selected = data["published_countries"]
        if not selected:
            await _start_edit_blocked(callback.message, state, edit=True)
            await callback.answer()
            return
        await state.update_data(current_idx=0)
        await state.set_state(EditReportFSM.enter_published_count)
        c = COUNTRIES[selected[0]]
        await callback.message.edit_text(f"✅ Выставлено для <b>{c['flag']} {c['name']}</b>?")
        await callback.answer()
        return
    data = await state.get_data()
    selected = data["published_countries"]
    if code in selected:
        selected.remove(code)
    else:
        selected.append(code)
    await state.update_data(published_countries=selected)
    await callback.message.edit_reply_markup(reply_markup=country_keyboard("ecu", set(selected)))
    await callback.answer()


@router.message(EditReportFSM.enter_published_count)
async def enter_published(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return
    count = int(message.text.strip())
    data = await state.get_data()
    sel = data["published_countries"]
    idx = data["current_idx"]
    counts = data["published_counts"]
    counts[sel[idx]] = count
    idx += 1
    await state.update_data(published_counts=counts, current_idx=idx)
    if idx < len(sel):
        c = COUNTRIES[sel[idx]]
        await message.answer(f"✅ Выставлено для <b>{c['flag']} {c['name']}</b>?")
    else:
        await _start_edit_blocked(message, state)


# ==========================================
# STEP 1c: BLOCKED
# ==========================================

async def _start_edit_blocked(target: Message, state: FSMContext, edit: bool = False):
    data = await state.get_data()
    await state.set_state(EditReportFSM.select_blocked_countries)
    await state.update_data(current_idx=0)
    text = "🚫 <b>Шаг 3/4 — Заблокировано</b>\nВыберите страны:"
    kb = country_keyboard("ecb", set(data.get("blocked_countries", [])))
    if edit:
        await target.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(EditReportFSM.select_blocked_countries, F.data.startswith("ecb:"))
async def toggle_blocked(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":")[1]
    if code == "done":
        data = await state.get_data()
        selected = data["blocked_countries"]
        if not selected:
            await _start_edit_instructions(callback.message, state, edit=True)
            await callback.answer()
            return
        await state.update_data(current_idx=0)
        await state.set_state(EditReportFSM.enter_blocked_count)
        c = COUNTRIES[selected[0]]
        await callback.message.edit_text(f"🚫 Заблокировано для <b>{c['flag']} {c['name']}</b>?")
        await callback.answer()
        return
    data = await state.get_data()
    selected = data["blocked_countries"]
    if code in selected:
        selected.remove(code)
    else:
        selected.append(code)
    await state.update_data(blocked_countries=selected)
    await callback.message.edit_reply_markup(reply_markup=country_keyboard("ecb", set(selected)))
    await callback.answer()


@router.message(EditReportFSM.enter_blocked_count)
async def enter_blocked(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return
    count = int(message.text.strip())
    data = await state.get_data()
    sel = data["blocked_countries"]
    idx = data["current_idx"]
    counts = data["blocked_counts"]
    counts[sel[idx]] = count
    await state.update_data(blocked_counts=counts)
    c = COUNTRIES[sel[idx]]
    await state.set_state(EditReportFSM.enter_block_reason)
    await message.answer(f"🚫 Причина блокировки для <b>{c['flag']} {c['name']}</b>:")


@router.message(EditReportFSM.enter_block_reason)
async def enter_block_reason(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("⚠️ Введите причину блокировки.")
        return
    data = await state.get_data()
    sel = data["blocked_countries"]
    idx = data["current_idx"]
    reasons = data.get("blocked_reasons", {})
    reasons[sel[idx]] = message.text.strip()
    idx += 1
    await state.update_data(blocked_reasons=reasons, current_idx=idx)
    if idx < len(sel):
        c = COUNTRIES[sel[idx]]
        await state.set_state(EditReportFSM.enter_blocked_count)
        await message.answer(f"🚫 Заблокировано для <b>{c['flag']} {c['name']}</b>?")
    else:
        await _start_edit_instructions(message, state)


# ==========================================
# STEP 2: INSTRUCTIONS
# ==========================================

async def _start_edit_instructions(target: Message, state: FSMContext, edit: bool = False):
    await state.set_state(EditReportFSM.enter_total_instructions)
    text = "📝 <b>Шаг 4/4 — Инструкции</b>\nСколько инструкций создано всего?"
    if edit:
        await target.edit_text(text)
    else:
        await target.answer(text)


@router.message(EditReportFSM.enter_total_instructions)
async def enter_total(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return
    count = int(message.text.strip())
    data = await state.get_data()
    await state.update_data(total_instructions=count, instruction_countries=[], current_idx=0)
    await state.set_state(EditReportFSM.select_instruction_countries)
    await message.answer(
        "📝 Выберите страны для инструкций:",
        reply_markup=country_keyboard("eci", set(data.get("instruction_countries", []))),
    )


@router.callback_query(EditReportFSM.select_instruction_countries, F.data.startswith("eci:"))
async def toggle_instr(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":")[1]
    if code == "done":
        data = await state.get_data()
        selected = data["instruction_countries"]
        if not selected:
            await state.update_data(instruction_counts={})
            await _show_edit_confirmation(callback.message, state, edit=True)
            await callback.answer()
            return
        await state.update_data(current_idx=0)
        await state.set_state(EditReportFSM.enter_instruction_count)
        c = COUNTRIES[selected[0]]
        await callback.message.edit_text(f"📝 Инструкций для <b>{c['flag']} {c['name']}</b>?")
        await callback.answer()
        return
    data = await state.get_data()
    selected = data["instruction_countries"]
    if code in selected:
        selected.remove(code)
    else:
        selected.append(code)
    await state.update_data(instruction_countries=selected)
    await callback.message.edit_reply_markup(reply_markup=country_keyboard("eci", set(selected)))
    await callback.answer()


@router.message(EditReportFSM.enter_instruction_count)
async def enter_instr_count(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return
    count = int(message.text.strip())
    data = await state.get_data()
    sel = data["instruction_countries"]
    idx = data["current_idx"]
    counts = data["instruction_counts"]
    counts[sel[idx]] = count
    idx += 1
    await state.update_data(instruction_counts=counts, current_idx=idx)
    if idx < len(sel):
        c = COUNTRIES[sel[idx]]
        await message.answer(f"📝 Инструкций для <b>{c['flag']} {c['name']}</b>?")
    else:
        await _show_edit_confirmation(message, state)


# ==========================================
# CONFIRMATION
# ==========================================

async def _show_edit_confirmation(target: Message, state: FSMContext, edit: bool = False):
    data = await state.get_data()
    text = format_daily_report_preview(
        processed=data["processed_counts"],
        published=data["published_counts"],
        blocked=data["blocked_counts"],
        blocked_reasons=data.get("blocked_reasons", {}),
        total_instructions=data["total_instructions"],
        instruction_data=data["instruction_counts"],
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
            listing_data={
                LISTING_PROCESSED: data["processed_counts"],
                LISTING_PUBLISHED: data["published_counts"],
                LISTING_BLOCKED: data["blocked_counts"],
            },
            blocked_reasons=data.get("blocked_reasons", {}),
            instruction_data=data["instruction_counts"],
        )

    await state.clear()
    await callback.message.edit_text("✅ Отчет обновлен!")
    await callback.answer("Сохранено!")

    await notify_admins_new_report(
        bot, session, db_user,
        report_date=today.strftime("%d.%m.%Y"),
        processed=data["processed_counts"],
        published=data["published_counts"],
        blocked=data["blocked_counts"],
        blocked_reasons=data.get("blocked_reasons", {}),
        total_instructions=data["total_instructions"],
        instruction_data=data["instruction_counts"],
        is_edit=True,
    )
