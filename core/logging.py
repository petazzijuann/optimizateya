"""Logging estructurado con structlog.

Regla no negociable: NUNCA loguear mensajes, transcripciones ni contenido
sensible del usuario. Solo ids, tipos de evento y metadata técnica.
El user_id se loguea hasheado para correlación sin exponer identidad.
"""

import hashlib
import logging
import sys
import uuid
from contextvars import ContextVar

import structlog

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def hash_user_id(user_id: str | int) -> str:
    """Hash corto y estable para correlacionar logs sin exponer al usuario."""
    return hashlib.sha256(str(user_id).encode()).hexdigest()[:12]


def new_request_id() -> str:
    rid = uuid.uuid4().hex[:16]
    request_id_var.set(rid)
    return rid


def _add_request_id(_logger, _method, event_dict):
    rid = request_id_var.get()
    if rid:
        event_dict.setdefault("request_id", rid)
    return event_dict


def setup_logging(environment: str = "dev") -> None:
    logging.basicConfig(stream=sys.stdout, level=logging.INFO, format="%(message)s")
    renderer = (
        structlog.dev.ConsoleRenderer()
        if environment == "dev"
        else structlog.processors.JSONRenderer()
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            _add_request_id,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
