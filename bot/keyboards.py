"""Teclados inline del bot."""

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TIMEZONES = [
    ("🇦🇷 Buenos Aires", "America/Argentina/Buenos_Aires"),
    ("🇺🇾 Montevideo", "America/Montevideo"),
    ("🇨🇱 Santiago", "America/Santiago"),
    ("🇲🇽 CDMX", "America/Mexico_City"),
    ("🇨🇴 Bogotá", "America/Bogota"),
    ("🇪🇸 Madrid", "Europe/Madrid"),
]


def timezone_kb() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label, callback_data=f"tz:{tz}")]
        for label, tz in TIMEZONES
    ]
    rows.append([InlineKeyboardButton(text="🌍 Otra (escribirla)", callback_data="tz:other")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def briefing_hour_kb() -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="7:00", callback_data="bh:7"),
            InlineKeyboardButton(text="8:00", callback_data="bh:8"),
            InlineKeyboardButton(text="9:00", callback_data="bh:9"),
        ],
        [InlineKeyboardButton(text="🚫 Sin briefing diario", callback_data="bh:off")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reminder_fire_kb(reminder_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Hecho", callback_data=f"rem:done:{reminder_id}"),
                InlineKeyboardButton(text="😴 +15 min", callback_data=f"rem:snooze:{reminder_id}"),
                InlineKeyboardButton(text="🗑 Cancelar", callback_data=f"rem:cancel:{reminder_id}"),
            ]
        ]
    )


def delete_all_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⚠️ Sí, borrar TODO", callback_data="wipe:confirm"
                ),
                InlineKeyboardButton(text="❌ No, cancelar", callback_data="wipe:cancel"),
            ]
        ]
    )
