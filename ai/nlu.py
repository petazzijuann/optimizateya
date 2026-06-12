"""Router NLU: mensaje en lenguaje natural → DomainAction(s) vía tool-use."""

import json
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from ai.budget import check_budget, check_rate_limit, consume_tokens
from ai.client import get_llm_client
from ai.prompts import NLU_SYSTEM_PROMPT
from ai.tools import TOOL_NAMES, TOOLS
from core.logging import get_logger, hash_user_id
from core.models import User

log = get_logger(__name__)

_WEEKDAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


class DomainAction(BaseModel):
    tool: str
    arguments: dict = Field(default_factory=dict)


class NLUResult(BaseModel):
    actions: list[DomainAction] = Field(default_factory=list)
    reply_text: str | None = None


def _system_prompt(user: User) -> str:
    now = datetime.now(ZoneInfo(user.timezone))
    return NLU_SYSTEM_PROMPT.format(
        today=now.strftime("%Y-%m-%d"),
        weekday=_WEEKDAYS_ES[now.weekday()],
        local_time=now.strftime("%H:%M"),
        timezone=user.timezone,
    )


async def route(user: User, text: str) -> NLUResult:
    """Interpreta el mensaje del usuario. Aplica rate-limit y presupuesto antes de llamar."""
    await check_rate_limit(user.id)
    await check_budget(user.id)

    message = await get_llm_client().chat(
        messages=[
            {"role": "system", "content": _system_prompt(user)},
            {"role": "user", "content": text},
        ],
        tools=TOOLS,
    )
    # estimación conservadora si el provider no devuelve usage por mensaje
    await consume_tokens(user.id, max(len(text) // 3, 1) + 600)

    actions: list[DomainAction] = []
    for tc in message.tool_calls or []:
        name = tc.function.name
        if name not in TOOL_NAMES:
            log.warning("nlu_unknown_tool", tool=name, user=hash_user_id(user.id))
            continue
        try:
            args = json.loads(tc.function.arguments or "{}")
        except json.JSONDecodeError:
            log.warning("nlu_bad_arguments", tool=name, user=hash_user_id(user.id))
            continue
        actions.append(DomainAction(tool=name, arguments=args))

    log.info("nlu_routed", user=hash_user_id(user.id), n_actions=len(actions))
    return NLUResult(actions=actions, reply_text=message.content or None)
