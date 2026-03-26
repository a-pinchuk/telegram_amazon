from datetime import date

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.db.models import (
    DailyReport, ListingEntry, InstructionEntry,
    LISTING_PROCESSED, LISTING_PUBLISHED, LISTING_BLOCKED,
)


async def get_report(session: AsyncSession, user_id: int, report_date: date) -> DailyReport | None:
    result = await session.execute(
        select(DailyReport)
        .options(selectinload(DailyReport.listing_entries), selectinload(DailyReport.instruction_entries))
        .where(DailyReport.user_id == user_id, DailyReport.report_date == report_date)
    )
    return result.scalar_one_or_none()


async def create_report(
    session: AsyncSession,
    user_id: int,
    report_date: date,
    total_instructions: int,
    listing_data: dict[str, dict[str, int]],
    blocked_reasons: dict[str, str],
    instruction_data: dict[str, int],
) -> DailyReport:
    """
    listing_data: {listing_type: {country_code: count}}
    e.g. {"processed": {"UK": 5, "FR": 3}, "published": {"UK": 2}, "blocked": {"ES": 1}}
    """
    report = DailyReport(
        user_id=user_id,
        report_date=report_date,
        total_instructions=total_instructions,
        is_complete=True,
    )
    session.add(report)
    await session.flush()

    for listing_type, countries in listing_data.items():
        for code, count in countries.items():
            if count > 0:
                entry = ListingEntry(
                    report_id=report.id,
                    country_code=code,
                    listing_type=listing_type,
                    count=count,
                    block_reason=blocked_reasons.get(code) if listing_type == LISTING_BLOCKED else None,
                )
                session.add(entry)

    for code, count in instruction_data.items():
        if count > 0:
            session.add(InstructionEntry(report_id=report.id, country_code=code, count=count))

    await session.flush()
    return report


async def update_report(
    session: AsyncSession,
    report: DailyReport,
    total_instructions: int,
    listing_data: dict[str, dict[str, int]],
    blocked_reasons: dict[str, str],
    instruction_data: dict[str, int],
) -> DailyReport:
    report.total_instructions = total_instructions
    report.is_complete = True

    # Delete old entries
    for entry in list(report.listing_entries):
        await session.delete(entry)
    for entry in list(report.instruction_entries):
        await session.delete(entry)
    await session.flush()

    # Insert new entries
    for listing_type, countries in listing_data.items():
        for code, count in countries.items():
            if count > 0:
                session.add(ListingEntry(
                    report_id=report.id,
                    country_code=code,
                    listing_type=listing_type,
                    count=count,
                    block_reason=blocked_reasons.get(code) if listing_type == LISTING_BLOCKED else None,
                ))

    for code, count in instruction_data.items():
        if count > 0:
            session.add(InstructionEntry(report_id=report.id, country_code=code, count=count))

    await session.flush()
    return report


async def get_reports_for_period(
    session: AsyncSession,
    start_date: date,
    end_date: date,
    user_id: int | None = None,
) -> list[DailyReport]:
    query = (
        select(DailyReport)
        .options(
            selectinload(DailyReport.listing_entries),
            selectinload(DailyReport.instruction_entries),
            selectinload(DailyReport.user),
        )
        .where(
            DailyReport.report_date >= start_date,
            DailyReport.report_date <= end_date,
            DailyReport.is_complete == True,
        )
        .order_by(DailyReport.report_date)
    )
    if user_id is not None:
        query = query.where(DailyReport.user_id == user_id)

    result = await session.execute(query)
    return list(result.scalars().all())


async def get_aggregated_listings(
    session: AsyncSession,
    start_date: date,
    end_date: date,
    user_id: int | None = None,
    listing_type: str | None = None,
) -> list[tuple[str, int]]:
    """Returns list of (country_code, total_count) for listings."""
    query = (
        select(ListingEntry.country_code, func.sum(ListingEntry.count))
        .join(DailyReport)
        .where(
            DailyReport.report_date >= start_date,
            DailyReport.report_date <= end_date,
            DailyReport.is_complete == True,
        )
        .group_by(ListingEntry.country_code)
        .order_by(func.sum(ListingEntry.count).desc())
    )
    if user_id is not None:
        query = query.where(DailyReport.user_id == user_id)
    if listing_type is not None:
        query = query.where(ListingEntry.listing_type == listing_type)

    result = await session.execute(query)
    return list(result.all())


async def get_aggregated_instructions(
    session: AsyncSession,
    start_date: date,
    end_date: date,
    user_id: int | None = None,
) -> tuple[int, list[tuple[str, int]]]:
    """Returns (total_instructions, [(country_code, total_count)])."""
    total_query = (
        select(func.sum(DailyReport.total_instructions))
        .where(
            DailyReport.report_date >= start_date,
            DailyReport.report_date <= end_date,
            DailyReport.is_complete == True,
        )
    )
    if user_id is not None:
        total_query = total_query.where(DailyReport.user_id == user_id)

    total_result = await session.execute(total_query)
    total = total_result.scalar() or 0

    country_query = (
        select(InstructionEntry.country_code, func.sum(InstructionEntry.count))
        .join(DailyReport)
        .where(
            DailyReport.report_date >= start_date,
            DailyReport.report_date <= end_date,
            DailyReport.is_complete == True,
        )
        .group_by(InstructionEntry.country_code)
        .order_by(func.sum(InstructionEntry.count).desc())
    )
    if user_id is not None:
        country_query = country_query.where(DailyReport.user_id == user_id)

    country_result = await session.execute(country_query)
    return total, list(country_result.all())
