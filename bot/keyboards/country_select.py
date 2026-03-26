from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.services.country_data import ALL_COUNTRY_CODES, country_label

COLUMNS = 3


def country_keyboard(
    prefix: str,
    selected: set[str] | None = None,
) -> InlineKeyboardMarkup:
    """
    Build an inline keyboard grid for country selection.

    prefix: callback data prefix, e.g. "cl" (country listing) or "ci" (country instruction)
    selected: set of currently selected country codes
    """
    selected = selected or set()
    buttons = []
    row = []

    for code in ALL_COUNTRY_CODES:
        is_selected = code in selected
        label = country_label(code, selected=is_selected)
        row.append(InlineKeyboardButton(text=label, callback_data=f"{prefix}:{code}"))
        if len(row) == COLUMNS:
            buttons.append(row)
            row = []

    if row:
        buttons.append(row)

    # Done button
    buttons.append([InlineKeyboardButton(text="✅ Готово", callback_data=f"{prefix}:done")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
