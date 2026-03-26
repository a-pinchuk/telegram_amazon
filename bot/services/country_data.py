REGIONS: dict[str, list[dict]] = {
    "Европа": [
        {"code": "UK", "flag": "🇬🇧", "name": "Великобритания"},
        {"code": "IE", "flag": "🇮🇪", "name": "Ирландия"},
        {"code": "FR", "flag": "🇫🇷", "name": "Франция"},
        {"code": "BE", "flag": "🇧🇪", "name": "Бельгия"},
        {"code": "IT", "flag": "🇮🇹", "name": "Италия"},
        {"code": "ES", "flag": "🇪🇸", "name": "Испания"},
        {"code": "NL", "flag": "🇳🇱", "name": "Нидерланды"},
        {"code": "SE", "flag": "🇸🇪", "name": "Швеция"},
        {"code": "PL", "flag": "🇵🇱", "name": "Польша"},
    ],
    "Америка": [
        {"code": "US", "flag": "🇺🇸", "name": "США"},
        {"code": "CA", "flag": "🇨🇦", "name": "Канада"},
        {"code": "MX", "flag": "🇲🇽", "name": "Мексика"},
    ],
}

# Flat lookup: code -> {flag, name, region}
COUNTRIES: dict[str, dict] = {}
for _region, _items in REGIONS.items():
    for _c in _items:
        COUNTRIES[_c["code"]] = {**_c, "region": _region}

# Ordered list of all country codes (for keyboard layout)
ALL_COUNTRY_CODES: list[str] = [c["code"] for items in REGIONS.values() for c in items]


def country_label(code: str, selected: bool = False) -> str:
    """Return display label for a country button."""
    c = COUNTRIES[code]
    prefix = "✅ " if selected else ""
    return f"{prefix}{c['flag']} {c['name']}"
