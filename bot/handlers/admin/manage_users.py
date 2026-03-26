from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.repositories.user_repo import (
    create_user,
    deactivate_user,
    get_all_active_participants,
)
from bot.filters.role_filter import IsAdmin
from bot.keyboards.main_menu import BTN_MANAGE_USERS, admin_menu
from bot.keyboards.report_views import user_manage_keyboard
from bot.states.report_states import AddUserFSM

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == BTN_MANAGE_USERS)
async def manage_users(message: Message, session: AsyncSession):
    participants = await get_all_active_participants(session)

    if participants:
        text = "👥 <b>Управление участниками</b>\n\nНажмите на сотрудника, чтобы удалить его:"
        kb = user_manage_keyboard(participants)
    else:
        text = "👥 <b>Управление участниками</b>\n\nСписок пуст."
        kb = InlineKeyboardMarkup(inline_keyboard=[])

    # Add "Add" button at the top
    kb.inline_keyboard.insert(0, [
        InlineKeyboardButton(text="➕ Добавить участника", callback_data="add_user")
    ])

    await message.answer(text, reply_markup=kb)


# --- Remove user ---

@router.callback_query(F.data.startswith("rm_user:"))
async def remove_user_cb(callback: CallbackQuery, session: AsyncSession):
    value = callback.data.split(":")[1]

    if value == "cancel":
        await callback.message.edit_text("🔙 Отменено.")
        await callback.answer()
        return

    user_id = int(value)
    await deactivate_user(session, user_id)
    await callback.message.edit_text("✅ Участник удален.")
    await callback.answer("Удалено!")


# --- Add user ---

@router.callback_query(F.data == "add_user")
async def start_add_user(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddUserFSM.enter_telegram_id)
    await callback.message.edit_text(
        "➕ <b>Добавление участника</b>\n\n"
        "Введите Telegram ID нового сотрудника (число).\n"
        "Нажмите /cancel для отмены."
    )
    await callback.answer()


@router.message(AddUserFSM(), F.text == "/cancel")
async def cancel_add(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=admin_menu())


@router.message(AddUserFSM.enter_telegram_id)
async def enter_tg_id(message: Message, state: FSMContext):
    if not message.text or not message.text.strip().isdigit():
        await message.answer("⚠️ Введите числовой Telegram ID.")
        return

    tg_id = int(message.text.strip())
    await state.update_data(telegram_id=tg_id)
    await state.set_state(AddUserFSM.enter_name)
    await message.answer("Введите имя сотрудника:")


@router.message(AddUserFSM.enter_name)
async def enter_name(message: Message, state: FSMContext, session: AsyncSession):
    if not message.text or not message.text.strip():
        await message.answer("⚠️ Введите имя.")
        return

    data = await state.get_data()
    name = message.text.strip()

    await create_user(session, telegram_id=data["telegram_id"], full_name=name)
    await state.clear()

    await message.answer(
        f"✅ Участник <b>{name}</b> (ID: {data['telegram_id']}) добавлен!",
        reply_markup=admin_menu(),
    )
