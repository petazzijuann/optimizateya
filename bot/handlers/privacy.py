"""Privacidad: /exportar, /borrartodo (con confirmación), /privacidad."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import BufferedInputFile, Message

from bot.keyboards import delete_all_confirm_kb
from domain.privacy import PRIVACY_POLICY_TEXT, export_user_data

router = Router(name="privacy")


@router.message(Command("privacidad"))
async def cmd_privacidad(message: Message) -> None:
    await message.answer(PRIVACY_POLICY_TEXT)


@router.message(Command("exportar"))
async def cmd_exportar(message: Message, user, session) -> None:
    data = await export_user_data(session, user)
    await message.answer_document(
        BufferedInputFile(data, filename="optimizateya-export.json"),
        caption="📦 Acá están todos tus datos. Son tuyos.",
    )


@router.message(Command("borrartodo"))
async def cmd_borrartodo(message: Message, user) -> None:
    await message.answer(
        "⚠️ Esto borra *TODO*: recordatorios, listas, memoria, archivos y puntos. "
        "No hay vuelta atrás.\n\n¿Estás seguro?",
        reply_markup=delete_all_confirm_kb(),
    )
