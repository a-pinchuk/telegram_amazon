import logging

from aiogram import Bot
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import User
from bot.services.country_data import COUNTRIES

logger = logging.getLogger(__name__)


async def notify_admins_new_report(
    bot: Bot,
    session: AsyncSession,
    employee: User,
    report_date: str,
    listing_data: dict[str, int],
    total_instructions: int,
    instruction_data: dict[str, int],
    is_edit: bool = False,
):
    """Send notification to all admins when an employee submits/edits a report."""
    # Get all active admins
    result = await session.execute(
        select(User).where(User.role == "admin", User.is_active == True)
    )
    admins = result.scalars().all()

    if not admins:
        return

    # Build notification text
    action = "✏️ Отчет изменён" if is_edit else "📩 Новый отчет"

    lines = [f"{action} от <b>{employee.full_name}</b> ({report_date})\n"]

    # Listings
    listing_parts = []
    for code, count in listing_data.items():
        c = COUNTRIES.get(code)
        if c:
            listing_parts.append(f"{c['flag']} {count}")
    if listing_parts:
        lines.append(f"📦 Листинги: {', '.join(listing_parts)}")

    # Instructions
    instr_parts = []
    for code, count in instruction_data.items():
        c = COUNTRIES.get(code)
        if c:
            instr_parts.append(f"{c['flag']} {count}")
    instr_str = f" ({', '.join(instr_parts)})" if instr_parts else ""
    lines.append(f"📝 Инструкции: {total_instructions}{instr_str}")

    text = "\n".join(lines)

    # Send to each admin
    for admin in admins:
        try:
            await bot.send_message(admin.telegram_id, text)
        except Exception as e:
            logger.warning(f"Failed to notify admin {admin.telegram_id}: {e}")
