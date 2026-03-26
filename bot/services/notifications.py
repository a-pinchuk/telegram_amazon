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
    processed: dict[str, int],
    published: dict[str, int],
    blocked: dict[str, int],
    blocked_reasons: dict[str, str],
    total_instructions: int,
    instruction_data: dict[str, int],
    is_edit: bool = False,
):
    """Send notification to all admins when an employee submits/edits a report."""
    result = await session.execute(
        select(User).where(User.role == "admin", User.is_active == True)
    )
    admins = result.scalars().all()

    if not admins:
        return

    action = "✏️ Отчет изменён" if is_edit else "📩 Новый отчет"
    lines = [f"{action} от <b>{employee.full_name}</b> ({report_date})\n"]

    def _format_countries(data: dict[str, int]) -> str:
        parts = []
        for code, count in data.items():
            c = COUNTRIES.get(code)
            if c:
                parts.append(f"{c['flag']} {count}")
        return ", ".join(parts) if parts else "—"

    if processed:
        lines.append(f"📋 Обработано: {_format_countries(processed)}")
    if published:
        lines.append(f"✅ Выставлено: {_format_countries(published)}")
    if blocked:
        blocked_parts = []
        for code, count in blocked.items():
            c = COUNTRIES.get(code)
            if c:
                reason = blocked_reasons.get(code, "")
                r = f" ({reason})" if reason else ""
                blocked_parts.append(f"{c['flag']} {count}{r}")
        lines.append(f"🚫 Заблокировано: {', '.join(blocked_parts)}")

    instr_parts = []
    for code, count in instruction_data.items():
        c = COUNTRIES.get(code)
        if c:
            instr_parts.append(f"{c['flag']} {count}")
    instr_str = f" ({', '.join(instr_parts)})" if instr_parts else ""
    lines.append(f"📝 Инструкции: {total_instructions}{instr_str}")

    text = "\n".join(lines)

    for admin in admins:
        if admin.telegram_id == employee.telegram_id:
            continue  # Don't notify admin about their own report
        try:
            await bot.send_message(admin.telegram_id, text)
        except Exception as e:
            logger.warning(f"Failed to notify admin {admin.telegram_id}: {e}")
