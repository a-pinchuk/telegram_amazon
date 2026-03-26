from bot.db.models import LISTING_PROCESSED, LISTING_PUBLISHED, LISTING_BLOCKED, LISTING_TYPE_LABELS
from bot.services.country_data import COUNTRIES, REGIONS


def format_country_stats(data: list[tuple[str, int]], title: str) -> str:
    """Format country statistics grouped by region."""
    if not data:
        return f"{title}\n  <i>Нет данных</i>\n"

    lines = [title]
    total = 0

    by_region: dict[str, list[tuple[str, int]]] = {}
    for code, count in data:
        c = COUNTRIES.get(code)
        if c:
            region = c["region"]
            by_region.setdefault(region, []).append((code, count))
            total += count

    for region_name in REGIONS:
        if region_name in by_region:
            lines.append(f"  <i>{region_name}:</i>")
            for code, count in by_region[region_name]:
                c = COUNTRIES[code]
                lines.append(f"    {c['flag']} {c['name']}: <b>{count}</b>")

    lines.append(f"  <b>Всего: {total}</b>")
    return "\n".join(lines)


def format_report_summary(
    period_label: str,
    listings_by_type: dict[str, list[tuple[str, int]]],
    total_instructions: int,
    instruction_countries: list[tuple[str, int]],
) -> str:
    """Format a full report summary."""
    parts = [f"📊 <b>Отчет: {period_label}</b>\n"]

    for lt in [LISTING_PROCESSED, LISTING_PUBLISHED, LISTING_BLOCKED]:
        label = LISTING_TYPE_LABELS[lt]
        data = listings_by_type.get(lt, [])
        parts.append(format_country_stats(data, f"📦 <b>{label}:</b>"))
        parts.append("")

    parts.append(f"📝 <b>Инструкций создано:</b> {total_instructions}")
    parts.append(format_country_stats(instruction_countries, "  <b>Загружено по странам:</b>"))

    return "\n".join(parts)


def format_daily_report_preview(
    processed: dict[str, int],
    published: dict[str, int],
    blocked: dict[str, int],
    blocked_reasons: dict[str, str],
    total_instructions: int,
    instruction_data: dict[str, int],
) -> str:
    """Format report preview for confirmation step."""
    lines = ["📋 <b>Ваш отчет:</b>\n"]

    # Processed
    if processed:
        lines.append("📋 <b>Обработано:</b>")
        p_total = 0
        for code, count in processed.items():
            c = COUNTRIES.get(code)
            if c:
                lines.append(f"  {c['flag']} {c['name']}: {count}")
                p_total += count
        lines.append(f"  <b>Всего: {p_total}</b>\n")

    # Published
    if published:
        lines.append("✅ <b>Выставлено:</b>")
        pub_total = 0
        for code, count in published.items():
            c = COUNTRIES.get(code)
            if c:
                lines.append(f"  {c['flag']} {c['name']}: {count}")
                pub_total += count
        lines.append(f"  <b>Всего: {pub_total}</b>\n")

    # Blocked
    if blocked:
        lines.append("🚫 <b>Заблокировано:</b>")
        b_total = 0
        for code, count in blocked.items():
            c = COUNTRIES.get(code)
            if c:
                reason = blocked_reasons.get(code, "")
                reason_str = f" — <i>{reason}</i>" if reason else ""
                lines.append(f"  {c['flag']} {c['name']}: {count}{reason_str}")
                b_total += count
        lines.append(f"  <b>Всего: {b_total}</b>\n")

    # Instructions
    lines.append(f"📝 <b>Инструкций создано:</b> {total_instructions}")
    if instruction_data:
        lines.append("  <b>Загружено по странам:</b>")
        for code, count in instruction_data.items():
            c = COUNTRIES.get(code)
            if c:
                lines.append(f"  {c['flag']} {c['name']}: {count}")

    return "\n".join(lines)
