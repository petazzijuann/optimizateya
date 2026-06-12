"""NLU con el LLM mockeado: intención → tool_call correcto."""

import pytest

from ai import nlu
from core.errors import RateLimitedError
from tests.conftest import make_tool_call


async def test_recordame_mapea_a_create_reminder(user, redis, llm):
    llm.tool_calls = [
        make_tool_call(
            "create_reminder",
            {"title": "comprar pan", "due_at_natural": "mañana 9am", "recurrence": "none"},
        )
    ]
    result = await nlu.route(user, "recordame comprar pan mañana 9am")

    assert len(result.actions) == 1
    action = result.actions[0]
    assert action.tool == "create_reminder"
    assert action.arguments["title"] == "comprar pan"
    assert action.arguments["due_at_natural"] == "mañana 9am"

    # el system prompt lleva el contexto temporal del usuario
    system = llm.calls[0]["messages"][0]["content"]
    assert user.timezone in system
    # y las tools van en el request
    assert any(t["function"]["name"] == "create_reminder" for t in llm.calls[0]["tools"])


async def test_charla_sin_tools_devuelve_texto(user, redis, llm):
    llm.content = "¡Hola! ¿En qué te ayudo?"
    result = await nlu.route(user, "hola")
    assert result.actions == []
    assert result.reply_text == "¡Hola! ¿En qué te ayudo?"


async def test_tool_desconocida_se_ignora(user, redis, llm):
    llm.tool_calls = [make_tool_call("hack_the_planet", {})]
    result = await nlu.route(user, "hacé algo raro")
    assert result.actions == []


async def test_rate_limit(user, redis, llm):
    llm.content = "ok"
    from ai.budget import RATE_LIMIT_PER_MINUTE

    for _ in range(RATE_LIMIT_PER_MINUTE):
        await nlu.route(user, "hola")
    with pytest.raises(RateLimitedError):
        await nlu.route(user, "hola")


async def test_budget_consumed(user, redis, llm):
    llm.content = "ok"
    await nlu.route(user, "hola")
    keys = await redis.keys("llm:budget:*")
    assert keys
    assert int(await redis.get(keys[0])) > 0
