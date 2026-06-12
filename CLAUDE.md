# Optimizate Ya

Asistente conversacional "segunda memoria" en Telegram: recordatorios, listas, memoria (Memory Bubbles), calendarios, entradas multimodales (texto/voz/imagen) y gamificación. Backend Python (bot + API + worker + scheduler).

## Commands

- `uv sync` — instala dependencias
- `docker compose up -d` — Postgres(+pgvector) y Redis locales
- `alembic upgrade head` — aplica migraciones
- `uvicorn api.main:app --reload` — API + webhook (dev)
- `arq worker.main.WorkerSettings` — worker async
- `python -m scheduler.engine` — scheduler de recordatorios
- `pytest` — tests
- `ruff check . && mypy .` — lint + types

## Tech Stack

Python 3.12 + aiogram v3 (bot) + FastAPI (API) + PostgreSQL/pgvector + SQLAlchemy 2.0 async/Alembic + Redis/arq + APScheduler + LLM gratuito (Groq Llama / Ollama, OpenAI-compatible, NLU+tool-use) + Groq Whisper (STT) + Tesseract (OCR) + Cloudflare R2 (storage) + Railway (hosting).

## Architecture

### Procesos (un solo código, tres procesos)
- `api/` — FastAPI: webhook de Telegram + OAuth callbacks + (fase 2) dashboard.
- `worker/` — arq: transcripción, OCR, indexado de memoria, sync de calendario, outbox.
- `scheduler/` — APScheduler: disparo de recordatorios, briefing, reconciliación, retención.

### Capas
- `bot/` (aiogram) → `ai/nlu.py` (LLM tool-use, Groq/Ollama) → `domain/*` (lógica) → emite eventos.
- `gamification/` es un **subsistema independiente** suscripto a eventos (nunca acoplado al dominio).
- `core/` — config, db, redis, crypto (Fernet), event bus, models.

### Data Flow
update Telegram → webhook → (si voz/imagen) encola job STT/OCR → texto → NLU (tool-use) → servicio de dominio (Postgres) → evento → gamificación (+puntos, ZSET ranking) → respuesta al usuario.

### Key Patterns
- Todo input multimodal se normaliza a texto antes del NLU.
- Toda query de dominio se filtra por `user_id` (aislamiento multi-tenant).
- Tokens OAuth SIEMPRE cifrados con Fernet antes de persistir.
- Servicios stateless; estado en Postgres/Redis.
- Búsqueda de memoria por similitud vectorial (pgvector, cosine) filtrada por user.

## Code Organization Rules

1. Un modelo SQLAlchemy por archivo en `core/models/`.
2. Lógica de negocio en `domain/`, NUNCA en handlers del bot.
3. Gamificación solo reacciona a eventos; no la llames directamente desde el dominio.
4. Validación de toda entrada con Pydantic. Config validada al boot (`core/config.py`).
5. Async en todo el stack (no llamadas bloqueantes en handlers/endpoints).
6. Máx ~300 líneas por archivo; extraé si crece.

## Environment Variables

| Variable | Descripción |
|----------|-------------|
| `TELEGRAM_BOT_TOKEN` / `TELEGRAM_WEBHOOK_SECRET` | Bot y secret del webhook |
| `PUBLIC_BASE_URL` | URL pública HTTPS |
| `DATABASE_URL` / `REDIS_URL` | Postgres async / Redis |
| `LLM_PROVIDER` / `LLM_MODEL` / `LLM_MODEL_HEAVY` | Proveedor (groq/ollama) y modelos NLU |
| `GROQ_API_KEY` / `GROQ_BASE_URL` | NLU (Llama) + Whisper STT |
| `OLLAMA_BASE_URL` / `VISION_MODEL` / `EMBED_MODEL` | Ollama local: NLU, visión y embeddings |
| `R2_*` | Cloudflare R2 (storage) |
| `FERNET_KEY` | Cifrado de tokens OAuth |
| `GOOGLE_CLIENT_*` / `MS_CLIENT_*` | OAuth calendarios |
| `LLM_MONTHLY_BUDGET_TOKENS` | Presupuesto LLM por usuario |

## Reglas No Negociables

1. NUNCA loguear mensajes, transcripciones ni contenido sensible del usuario.
2. Tokens OAuth SIEMPRE cifrados (Fernet); nunca en claro en la DB.
3. Toda query filtrada por `user_id` — aislamiento estricto entre usuarios.
4. Gamificación desacoplada por eventos; el dominio no conoce los puntos.
5. Privacidad por diseño: recolectar solo lo imprescindible; honrar `/borrartodo`.
6. Validar toda entrada (Pydantic) y la config al arranque; fallar rápido.
