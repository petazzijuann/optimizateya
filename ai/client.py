"""Cliente LLM provider-agnostic (OpenAI-compatible: Groq u Ollama).

Un solo cliente `openai.AsyncOpenAI`; el proveedor se elige por env
(`LLM_PROVIDER`) cambiando base_url + api_key. Retries con backoff exponencial.
"""

import asyncio
from typing import Any

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError

from core.config import get_settings
from core.logging import get_logger

log = get_logger(__name__)

_RETRIES = 3
_BACKOFF_BASE = 1.5


class LLMClient:
    def __init__(self, client: AsyncOpenAI | None = None) -> None:
        s = get_settings()
        self._client = client or AsyncOpenAI(
            base_url=s.llm_base_url, api_key=s.llm_api_key or "missing"
        )
        self._model = s.llm_model
        self._model_heavy = s.llm_model_heavy

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        heavy: bool = False,
        temperature: float = 0.2,
        max_tokens: int = 1024,
    ) -> Any:
        """Devuelve el `message` de la primera choice (incluye tool_calls si hay)."""
        model = self._model_heavy if heavy else self._model
        last_exc: Exception | None = None
        for attempt in range(_RETRIES):
            try:
                kwargs: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                }
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"
                resp = await self._client.chat.completions.create(**kwargs)
                usage = getattr(resp, "usage", None)
                if usage:
                    log.info("llm_call", model=model, total_tokens=usage.total_tokens)
                return resp.choices[0].message
            except (APIConnectionError, RateLimitError, APIStatusError) as exc:
                last_exc = exc
                wait = _BACKOFF_BASE**attempt
                log.warning("llm_retry", attempt=attempt + 1, wait_s=wait, error=type(exc).__name__)
                await asyncio.sleep(wait)
        raise last_exc  # type: ignore[misc]


_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    global _client
    if _client is None:
        _client = LLMClient()
    return _client


def set_llm_client(client: LLMClient | None) -> None:
    """Inyección para tests."""
    global _client
    _client = client
