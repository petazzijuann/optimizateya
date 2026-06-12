"""Núcleo del flujo conversacional: texto normalizado → NLU → dominio → respuesta.

Lo usan el handler de texto y los workers (voz/imagen ya transcriptas).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from ai import nlu
from core.errors import BudgetExceededError, DomainError, RateLimitedError
from core.models import User
from domain import dispatcher


async def handle_text(session: AsyncSession, user: User, text: str) -> str:
    """Devuelve la respuesta (Markdown) para el usuario."""
    text = (text or "").strip()
    if not text:
        return "No te entendí 🤔 ¿me lo repetís?"
    try:
        result = await nlu.route(user, text)
    except (RateLimitedError, BudgetExceededError) as exc:
        return str(exc)
    except DomainError as exc:
        return str(exc)
    except Exception:
        return "Uy, se me cruzaron los cables 🤖 Probá de nuevo en un ratito."

    replies: list[str] = []
    for action in result.actions:
        replies.append(await dispatcher.execute(session, user, action))

    if replies:
        return "\n\n".join(replies)
    return result.reply_text or "Contame qué necesitás: recordatorios, listas, notas o tu agenda."
