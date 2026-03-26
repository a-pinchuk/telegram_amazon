from datetime import date, timedelta, datetime
import zoneinfo

from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import LISTING_PROCESSED, LISTING_PUBLISHED, LISTING_BLOCKED
from bot.db.repositories import report_repo
from bot.db.repositories.user_repo import get_all_active_participants
from bot.utils.formatting import format_report_summary


def get_period_dates(period: str, tz_name: str = "Europe/Kyiv") -> tuple[date, date, str]:
    """Return (start_date, end_date, label) for a named period."""
    tz = zoneinfo.ZoneInfo(tz_name)
    today = datetime.now(tz).date()

    if period == "today":
        return today, today, f"{today.strftime('%d.%m.%Y')}"
    elif period == "yesterday":
        yesterday = today - timedelta(days=1)
        return yesterday, yesterday, f"{yesterday.strftime('%d.%m.%Y')}"
    elif period == "week":
        start = today - timedelta(days=today.weekday())
        return start, today, f"{start.strftime('%d.%m')} — {today.strftime('%d.%m.%Y')}"
    elif period == "month":
        start = today.replace(day=1)
        return start, today, f"{start.strftime('%d.%m')} — {today.strftime('%d.%m.%Y')}"
    else:
        return today, today, f"{today.strftime('%d.%m.%Y')}"


async def build_report(
    session: AsyncSession,
    start_date: date,
    end_date: date,
    user_id: int | None = None,
) -> str:
    """Build a formatted report for a period."""
    if start_date == end_date:
        period_label = start_date.strftime("%d.%m.%Y")
    else:
        period_label = f"{start_date.strftime('%d.%m')} — {end_date.strftime('%d.%m.%Y')}"

    listings_by_type = {}
    for lt in [LISTING_PROCESSED, LISTING_PUBLISHED, LISTING_BLOCKED]:
        listings_by_type[lt] = await report_repo.get_aggregated_listings(
            session, start_date, end_date, user_id, listing_type=lt
        )

    total_instr, instr_countries = await report_repo.get_aggregated_instructions(
        session, start_date, end_date, user_id
    )

    return format_report_summary(period_label, listings_by_type, total_instr, instr_countries)


async def build_employee_breakdown(
    session: AsyncSession,
    start_date: date,
    end_date: date,
) -> str:
    """Build per-employee breakdown."""
    participants = await get_all_active_participants(session)
    if not participants:
        return "\n👥 <b>По сотрудникам:</b>\n  <i>Нет данных</i>"

    lines = ["\n👥 <b>По сотрудникам:</b>"]

    for user in participants:
        processed = await report_repo.get_aggregated_listings(
            session, start_date, end_date, user.id, listing_type=LISTING_PROCESSED
        )
        published = await report_repo.get_aggregated_listings(
            session, start_date, end_date, user.id, listing_type=LISTING_PUBLISHED
        )
        blocked = await report_repo.get_aggregated_listings(
            session, start_date, end_date, user.id, listing_type=LISTING_BLOCKED
        )
        total_instr, instr_countries = await report_repo.get_aggregated_instructions(
            session, start_date, end_date, user.id
        )

        if processed or published or blocked or total_instr > 0:
            from bot.services.country_data import COUNTRIES
            parts = []

            def _fmt(data, label):
                if data:
                    items = []
                    for code, count in data:
                        c = COUNTRIES.get(code)
                        if c:
                            items.append(f"{c['flag']}{count}")
                    return f"{label}: {', '.join(items)}"
                return None

            p = _fmt(processed, "📋")
            if p:
                parts.append(p)
            u = _fmt(published, "✅")
            if u:
                parts.append(u)
            b = _fmt(blocked, "🚫")
            if b:
                parts.append(b)

            parts.append(f"📝 {total_instr}")
            lines.append(f"  <b>{user.full_name}:</b> {' | '.join(parts)}")

    if len(lines) == 1:
        lines.append("  <i>Нет данных за период</i>")

    return "\n".join(lines)
