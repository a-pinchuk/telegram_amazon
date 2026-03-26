from datetime import datetime
import zoneinfo

from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User, LISTING_PROCESSED, LISTING_PUBLISHED, LISTING_BLOCKED, LISTING_TYPE_LABELS
from bot.db.repositories import report_repo
from bot.filters.role_filter import IsRegistered
from bot.services.notifications import notify_admins_new_report
from bot.keyboards.common import confirm_cancel_keyboard
from bot.keyboards.country_select import country_keyboard
from bot.keyboards.main_menu import BTN_SUBMIT_REPORT, participant_menu, admin_menu
from bot.services.country_data import COUNTRIES
from bot.states.report_states import DailyReportFSM
from bot.utils.formatting import format_daily_report_preview

router = Router()
router.message.filter(IsRegistered())
router.callback_query.filter(IsRegistered())

# Listing steps config: (fsm_select_state, fsm_count_state, data_key_selected, data_key_counts, callback_prefix, label)
LISTING_STEPS = [
    (LISTING_PROCESSED, "cp", "📋 <b>Шаг 1/4 — Обработано</b>\nВыберите страны, где обработали листинги:"),
    (LISTING_PUBLISHED, "cu", "✅ <b>Шаг 2/4 — Выставлено</b>\nВыберите страны, где выставили листинги:"),
    (LISTING_BLOCKED, "cb", "🚫 <b>Шаг 3/4 — Заблокировано</b>\nВыберите страны, где были блокировки:"),
]


def _get_today(tz_name: str = "Europe/Kyiv"):
    return datetime.now(zoneinfo.ZoneInfo(tz_name)).date()


def _get_menu(db_user: User):
    return admin_menu() if db_user.role == "admin" else participant_menu()


# --- Cancel handler ---

@router.message(DailyReportFSM(), F.text == "/cancel")
async def cancel_report(message: Message, state: FSMContext, db_user: User):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=_get_menu(db_user))


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

    await state.set_state(DailyReportFSM.select_processed_countries)
    await state.update_data(
        processed_countries=[], processed_counts={},
        published_countries=[], published_counts={},
        blocked_countries=[], blocked_counts={}, blocked_reasons={},
        total_instructions=0,
        instruction_countries=[], instruction_counts={},
        current_idx=0,
    )

    await message.answer(
        "📋 <b>Шаг 1/4 — Обработано</b>\n\n"
        "Выберите страны, где вы обработали листинги.\n"
        "Нажмите /cancel для отмены.",
        reply_markup=country_keyboard("cp"),
    )


# ==========================================
# STEP 1a: PROCESSED listings
# ==========================================

@router.callback_query(DailyReportFSM.select_processed_countries, F.data.startswith("cp:"))
async def toggle_processed(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":")[1]

    if code == "done":
        data = await state.get_data()
        selected = data["processed_countries"]
        if not selected:
            # Skip to next step
            await _start_published_step(callback.message, state, edit=True)
            await callback.answer()
            return

        await state.update_data(current_idx=0)
        await state.set_state(DailyReportFSM.enter_processed_count)
        c = COUNTRIES[selected[0]]
        await callback.message.edit_text(
            f"📋 Сколько листингов <b>обработано</b> для <b>{c['flag']} {c['name']}</b>?"
        )
        await callback.answer()
        return

    data = await state.get_data()
    selected = data["processed_countries"]
    if code in selected:
        selected.remove(code)
    else:
        selected.append(code)
    await state.update_data(processed_countries=selected)
    await callback.message.edit_reply_markup(reply_markup=country_keyboard("cp", set(selected)))
    await callback.answer()


@router.message(DailyReportFSM.enter_processed_count)
async def enter_processed_count(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return

    count = int(message.text.strip())
    data = await state.get_data()
    selected = data["processed_countries"]
    idx = data["current_idx"]
    counts = data["processed_counts"]
    counts[selected[idx]] = count
    idx += 1
    await state.update_data(processed_counts=counts, current_idx=idx)

    if idx < len(selected):
        c = COUNTRIES[selected[idx]]
        await message.answer(f"📋 Сколько листингов <b>обработано</b> для <b>{c['flag']} {c['name']}</b>?")
    else:
        await _start_published_step(message, state)


# ==========================================
# STEP 1b: PUBLISHED listings
# ==========================================

async def _start_published_step(target: Message, state: FSMContext, edit: bool = False):
    await state.set_state(DailyReportFSM.select_published_countries)
    await state.update_data(current_idx=0)
    text = "✅ <b>Шаг 2/4 — Выставлено</b>\n\nВыберите страны, где выставили листинги:"
    kb = country_keyboard("cu")
    if edit:
        await target.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(DailyReportFSM.select_published_countries, F.data.startswith("cu:"))
async def toggle_published(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":")[1]

    if code == "done":
        data = await state.get_data()
        selected = data["published_countries"]
        if not selected:
            await _start_blocked_step(callback.message, state, edit=True)
            await callback.answer()
            return

        await state.update_data(current_idx=0)
        await state.set_state(DailyReportFSM.enter_published_count)
        c = COUNTRIES[selected[0]]
        await callback.message.edit_text(
            f"✅ Сколько листингов <b>выставлено</b> для <b>{c['flag']} {c['name']}</b>?"
        )
        await callback.answer()
        return

    data = await state.get_data()
    selected = data["published_countries"]
    if code in selected:
        selected.remove(code)
    else:
        selected.append(code)
    await state.update_data(published_countries=selected)
    await callback.message.edit_reply_markup(reply_markup=country_keyboard("cu", set(selected)))
    await callback.answer()


@router.message(DailyReportFSM.enter_published_count)
async def enter_published_count(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return

    count = int(message.text.strip())
    data = await state.get_data()
    selected = data["published_countries"]
    idx = data["current_idx"]
    counts = data["published_counts"]
    counts[selected[idx]] = count
    idx += 1
    await state.update_data(published_counts=counts, current_idx=idx)

    if idx < len(selected):
        c = COUNTRIES[selected[idx]]
        await message.answer(f"✅ Сколько листингов <b>выставлено</b> для <b>{c['flag']} {c['name']}</b>?")
    else:
        await _start_blocked_step(message, state)


# ==========================================
# STEP 1c: BLOCKED listings
# ==========================================

async def _start_blocked_step(target: Message, state: FSMContext, edit: bool = False):
    await state.set_state(DailyReportFSM.select_blocked_countries)
    await state.update_data(current_idx=0)
    text = "🚫 <b>Шаг 3/4 — Заблокировано</b>\n\nВыберите страны, где были блокировки:"
    kb = country_keyboard("cb")
    if edit:
        await target.edit_text(text, reply_markup=kb)
    else:
        await target.answer(text, reply_markup=kb)


@router.callback_query(DailyReportFSM.select_blocked_countries, F.data.startswith("cb:"))
async def toggle_blocked(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":")[1]

    if code == "done":
        data = await state.get_data()
        selected = data["blocked_countries"]
        if not selected:
            await _start_instructions_step(callback.message, state, edit=True)
            await callback.answer()
            return

        await state.update_data(current_idx=0)
        await state.set_state(DailyReportFSM.enter_blocked_count)
        c = COUNTRIES[selected[0]]
        await callback.message.edit_text(
            f"🚫 Сколько листингов <b>заблокировано</b> для <b>{c['flag']} {c['name']}</b>?"
        )
        await callback.answer()
        return

    data = await state.get_data()
    selected = data["blocked_countries"]
    if code in selected:
        selected.remove(code)
    else:
        selected.append(code)
    await state.update_data(blocked_countries=selected)
    await callback.message.edit_reply_markup(reply_markup=country_keyboard("cb", set(selected)))
    await callback.answer()


@router.message(DailyReportFSM.enter_blocked_count)
async def enter_blocked_count(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return

    count = int(message.text.strip())
    data = await state.get_data()
    selected = data["blocked_countries"]
    idx = data["current_idx"]
    counts = data["blocked_counts"]
    counts[selected[idx]] = count
    await state.update_data(blocked_counts=counts)

    # Ask for block reason
    c = COUNTRIES[selected[idx]]
    await state.set_state(DailyReportFSM.enter_block_reason)
    await message.answer(
        f"🚫 Укажите причину блокировки для <b>{c['flag']} {c['name']}</b>:"
    )


@router.message(DailyReportFSM.enter_block_reason)
async def enter_block_reason(message: Message, state: FSMContext):
    if not message.text or not message.text.strip():
        await message.answer("⚠️ Введите причину блокировки.")
        return

    data = await state.get_data()
    selected = data["blocked_countries"]
    idx = data["current_idx"]
    reasons = data.get("blocked_reasons", {})
    reasons[selected[idx]] = message.text.strip()
    idx += 1
    await state.update_data(blocked_reasons=reasons, current_idx=idx)

    if idx < len(selected):
        c = COUNTRIES[selected[idx]]
        await state.set_state(DailyReportFSM.enter_blocked_count)
        await message.answer(f"🚫 Сколько листингов <b>заблокировано</b> для <b>{c['flag']} {c['name']}</b>?")
    else:
        await _start_instructions_step(message, state)


# ==========================================
# STEP 2: INSTRUCTIONS
# ==========================================

async def _start_instructions_step(target: Message, state: FSMContext, edit: bool = False):
    await state.set_state(DailyReportFSM.enter_total_instructions)
    text = "📝 <b>Шаг 4/4 — Инструкции</b>\n\nСколько инструкций вы создали сегодня (всего)?"
    if edit:
        await target.edit_text(text)
    else:
        await target.answer(text)


@router.message(DailyReportFSM.enter_total_instructions)
async def enter_total_instructions(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return

    count = int(message.text.strip())
    await state.update_data(total_instructions=count, instruction_countries=[], current_idx=0)
    await state.set_state(DailyReportFSM.select_instruction_countries)

    await message.answer(
        "📝 Выберите страны, в которые вы загрузили инструкции:",
        reply_markup=country_keyboard("ci"),
    )


@router.callback_query(DailyReportFSM.select_instruction_countries, F.data.startswith("ci:"))
async def toggle_instruction_country(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":")[1]

    if code == "done":
        data = await state.get_data()
        selected = data["instruction_countries"]

        if not selected:
            await state.update_data(instruction_counts={})
            await _show_confirmation(callback.message, state, edit=True)
            await callback.answer()
            return

        await state.update_data(current_idx=0)
        await state.set_state(DailyReportFSM.enter_instruction_count)
        c = COUNTRIES[selected[0]]
        await callback.message.edit_text(
            f"📝 Сколько инструкций загружено для <b>{c['flag']} {c['name']}</b>?"
        )
        await callback.answer()
        return

    data = await state.get_data()
    selected = data["instruction_countries"]
    if code in selected:
        selected.remove(code)
    else:
        selected.append(code)
    await state.update_data(instruction_countries=selected)
    await callback.message.edit_reply_markup(reply_markup=country_keyboard("ci", set(selected)))
    await callback.answer()


@router.message(DailyReportFSM.enter_instruction_count)
async def enter_instruction_count(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите целое число.")
        return

    count = int(message.text.strip())
    data = await state.get_data()
    selected = data["instruction_countries"]
    idx = data["current_idx"]
    counts = data["instruction_counts"]
    counts[selected[idx]] = count
    idx += 1
    await state.update_data(instruction_counts=counts, current_idx=idx)

    if idx < len(selected):
        c = COUNTRIES[selected[idx]]
        await message.answer(f"📝 Сколько инструкций загружено для <b>{c['flag']} {c['name']}</b>?")
    else:
        await _show_confirmation(message, state)


# ==========================================
# CONFIRMATION
# ==========================================

async def _show_confirmation(target: Message, state: FSMContext, edit: bool = False):
    data = await state.get_data()
    text = format_daily_report_preview(
        processed=data["processed_counts"],
        published=data["published_counts"],
        blocked=data["blocked_counts"],
        blocked_reasons=data.get("blocked_reasons", {}),
        total_instructions=data["total_instructions"],
        instruction_data=data["instruction_counts"],
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
    else:
        await report_repo.create_report(
            session,
            user_id=db_user.id,
            report_date=today,
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
    await callback.message.edit_text("✅ Отчет успешно сохранен!")
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
    )
