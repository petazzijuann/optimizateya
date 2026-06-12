"""Onboarding: /start → timezone → hora del briefing → listo."""

from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import briefing_hour_kb, timezone_kb
from bot.states import Onboarding

router = Router(name="start")

WELCOME = (
    "¡Hola{name}! 👋 Soy *Optimizate Ya*, tu segunda memoria.\n\n"
    "Me podés escribir, mandarme audios o fotos y me encargo de:\n"
    "⏰ Recordatorios — _\"recordame llamar al médico mañana 9am\"_\n"
    "📋 Listas — _\"agregá leche a la lista del súper\"_\n"
    "🫧 Memoria — _\"acordate que el wifi es FIBER-123\"_\n"
    "🗓 Agenda — _\"reunión con Juan el martes 15hs\"_\n\n"
    "Primero, ¿desde dónde me escribís? (para tus horarios)"
)

DONE = (
    "¡Listo! 🎉 Ya estamos.\n\n"
    "Probá ahora mismo: mandame _\"recordame algo en 2 horas\"_ o una nota de voz.\n"
    "Cada cosa que hagas suma puntos 🏆 — mirá /puntos, /racha y /ranking.\n"
    "Tus datos son tuyos: /privacidad, /exportar, /borrartodo."
)

HELP = (
    "*Comandos:*\n"
    "/puntos /racha /ranking /stats /logros /historial — tu progreso\n"
    "/exportar /borrartodo /privacidad — tus datos\n\n"
    "Y para todo lo demás: escribime como a un amigo. Texto, voz o foto."
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, user, session) -> None:
    name = f", {user.first_name}" if user.first_name else ""
    await state.set_state(Onboarding.choosing_timezone)
    await message.answer(WELCOME.format(name=name), reply_markup=timezone_kb())


@router.message(Command("ayuda", "help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP)


@router.message(Command("calendario"))
async def cmd_calendario(message: Message, user, session) -> None:
    from api.routers.oauth import make_state
    from core.config import get_settings

    base = get_settings().public_base_url.rstrip("/")
    state = make_state(user.id)
    await message.answer(
        "🗓 *Conectá tu calendario* (elegí uno):\n\n"
        f"[Google Calendar]({base}/oauth/google/connect?state={state})\n"
        f"[Outlook]({base}/oauth/outlook/connect?state={state})\n\n"
        "_El enlace vence en 15 minutos._",
        disable_web_page_preview=True,
    )


@router.callback_query(Onboarding.choosing_timezone, F.data.startswith("tz:"))
async def cb_timezone(callback: CallbackQuery, state: FSMContext, user, session) -> None:
    choice = callback.data.removeprefix("tz:")
    if choice == "other":
        await state.set_state(Onboarding.typing_timezone)
        await callback.message.edit_text(
            "Escribime tu zona horaria en formato IANA, ej: `America/Lima` o `Europe/Berlin`."
        )
        await callback.answer()
        return
    user.timezone = choice
    await state.set_state(Onboarding.choosing_briefing_hour)
    await callback.message.edit_text(
        "📬 ¿A qué hora querés tu *briefing diario*? (resumen de agenda y pendientes)",
        reply_markup=briefing_hour_kb(),
    )
    await callback.answer()


@router.message(Onboarding.typing_timezone, F.text)
async def msg_timezone(message: Message, state: FSMContext, user, session) -> None:
    tz_name = (message.text or "").strip()
    try:
        ZoneInfo(tz_name)
    except Exception:
        await message.answer("No conozco esa zona 😅 Probá de nuevo, ej: `America/Lima`.")
        return
    user.timezone = tz_name
    await state.set_state(Onboarding.choosing_briefing_hour)
    await message.answer(
        "📬 ¿A qué hora querés tu *briefing diario*?", reply_markup=briefing_hour_kb()
    )


@router.callback_query(Onboarding.choosing_briefing_hour, F.data.startswith("bh:"))
async def cb_briefing(callback: CallbackQuery, state: FSMContext, user, session) -> None:
    choice = callback.data.removeprefix("bh:")
    user.briefing_hour = None if choice == "off" else int(choice)
    user.onboarded = True
    await state.clear()
    await callback.message.edit_text(DONE)
    await callback.answer("¡A organizarte! 🚀")
