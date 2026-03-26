from bot.services.country_data import COUNTRIES, REGIONS


def format_country_stats(data: list[tuple[str, int]], title: str) -> str:
    """Format country statistics grouped by region."""
    if not data:
        return f"{title}\n  <i>Нет данных</i>\n"

    lines = [title]
    total = 0

    # Group by region
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
    listings: list[tuple[str, int]],
    total_instructions: int,
    instruction_countries: list[tuple[str, int]],
) -> str:
    """Format a full report summary."""
    parts = [f"📊 <b>Отчет: {period_label}</b>\n"]

    parts.append(format_country_stats(listings, "📦 <b>Листинги по странам:</b>"))
    parts.append("")
    parts.append(f"📝 <b>Инструкций создано:</b> {total_instructions}")
    parts.append(format_country_stats(instruction_countries, "  <b>Загружено по странам:</b>"))

    return "\n".join(parts)


def format_employee_report_line(
    name: str,
    listings: list[tuple[str, int]],
    total_instructions: int,
    instruction_countries: list[tuple[str, int]],
) -> str:
    """Format a one-line summary for an employee."""
    listing_parts = []
    for code, count in listings:
        c = COUNTRIES.get(code)
        if c:
            listing_parts.append(f"{c['flag']}{count}")

    instr_parts = []
    for code, count in instruction_countries:
        c = COUNTRIES.get(code)
        if c:
            instr_parts.append(f"{c['flag']}{count}")

    listing_str = ", ".join(listing_parts) if listing_parts else "—"
    instr_str = ", ".join(instr_parts) if instr_parts else "—"

    return f"  <b>{name}:</b> Листинги: {listing_str} | Инструкции: {total_instructions} ({instr_str})"


def format_daily_report_preview(
    listing_data: dict[str, int],
    total_instructions: int,
    instruction_data: dict[str, int],
) -> str:
    """Format report preview for confirmation step."""
    lines = ["📋 <b>Ваш отчет:</b>\n"]

    lines.append("📦 <b>Листинги:</b>")
    listing_total = 0
    for code, count in listing_data.items():
        c = COUNTRIES.get(code)
        if c:
            lines.append(f"  {c['flag']} {c['name']}: {count}")
            listing_total += count
    lines.append(f"  <b>Всего: {listing_total}</b>\n")

    lines.append(f"📝 <b>Инструкций создано:</b> {total_instructions}")
    if instruction_data:
        lines.append("  <b>Загружено по странам:</b>")
        for code, count in instruction_data.items():
            c = COUNTRIES.get(code)
            if c:
                lines.append(f"  {c['flag']} {c['name']}: {count}")

    return "\n".join(lines)
