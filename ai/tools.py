"""Definición de tools (function-calling OpenAI-compatible).

Cada tool mapea 1:1 a un servicio de dominio (ver domain/dispatcher.py).
"""

from typing import Any


def _tool(name: str, description: str, properties: dict, required: list[str]) -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


TOOLS: list[dict[str, Any]] = [
    _tool(
        "create_reminder",
        "Crea un recordatorio único o recurrente.",
        {
            "title": {"type": "string", "description": "qué hay que recordar"},
            "due_at_natural": {
                "type": "string",
                "description": "fecha/hora en lenguaje natural tal como la dijo el usuario, "
                "ej 'mañana 9am', 'el jueves a las 15'",
            },
            "recurrence": {
                "type": "string",
                "enum": ["none", "daily", "weekly", "monthly"],
                "description": "recurrencia; 'none' si es único",
            },
        },
        ["title", "due_at_natural"],
    ),
    _tool(
        "list_reminders",
        "Lista los recordatorios pendientes del usuario.",
        {},
        [],
    ),
    _tool(
        "complete_reminder",
        "Marca un recordatorio como cumplido.",
        {"query": {"type": "string", "description": "texto para identificar el recordatorio"}},
        ["query"],
    ),
    _tool(
        "delete_reminder",
        "Cancela/borra un recordatorio.",
        {"query": {"type": "string", "description": "texto para identificar el recordatorio"}},
        ["query"],
    ),
    _tool(
        "add_list_item",
        "Agrega ítem(s) a una lista (la crea si no existe).",
        {
            "list_name": {"type": "string", "description": "nombre de la lista, ej 'súper'"},
            "items": {"type": "array", "items": {"type": "string"}, "description": "ítems"},
        },
        ["list_name", "items"],
    ),
    _tool(
        "mark_list_item",
        "Marca un ítem de una lista como hecho/comprado.",
        {
            "list_name": {"type": "string"},
            "item": {"type": "string", "description": "ítem a marcar"},
        },
        ["list_name", "item"],
    ),
    _tool(
        "query_list",
        "Muestra el contenido de una lista (o todas si no se especifica).",
        {"list_name": {"type": "string", "description": "nombre de la lista; vacío = todas"}},
        [],
    ),
    _tool(
        "save_memory",
        "Guarda una nota, dato o información en la memoria de largo plazo del usuario.",
        {
            "title": {"type": "string", "description": "título corto"},
            "content": {"type": "string", "description": "contenido completo a recordar"},
        },
        ["title", "content"],
    ),
    _tool(
        "query_memory",
        "Busca en la memoria del usuario por consulta en lenguaje natural.",
        {"query": {"type": "string", "description": "qué busca el usuario"}},
        ["query"],
    ),
    _tool(
        "create_event",
        "Crea un evento en el calendario conectado del usuario.",
        {
            "title": {"type": "string"},
            "start_natural": {
                "type": "string",
                "description": "fecha/hora de inicio en lenguaje natural, ej 'martes 15hs'",
            },
            "duration_minutes": {"type": "integer", "description": "duración; default 60"},
        },
        ["title", "start_natural"],
    ),
    _tool(
        "query_agenda",
        "Consulta la agenda del día: eventos de calendario y recordatorios.",
        {
            "date_natural": {
                "type": "string",
                "description": "día consultado en lenguaje natural; vacío = hoy",
            }
        },
        [],
    ),
]

TOOL_NAMES = {t["function"]["name"] for t in TOOLS}
