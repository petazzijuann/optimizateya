# Optimizate Ya 🧠

> Tu segunda memoria, viviendo en Telegram. Recordatorios, listas, memoria semántica,
> calendarios y gamificación — por texto, voz o imagen, en español rioplatense.

Construido según `optimizateya-blueprint.md` (MVP fase 1).

## Stack

Python 3.12 · aiogram v3 · FastAPI · PostgreSQL 16 + pgvector · SQLAlchemy 2.0 async + Alembic ·
Redis + arq · APScheduler · LLM gratuito (Groq Llama / Ollama vía cliente OpenAI-compatible) ·
Groq Whisper (STT) · Tesseract (OCR) · Cloudflare R2 · Railway.

## Quick start (desarrollo)

```bash
uv sync                          # dependencias (instala Python 3.12 si falta)
docker compose up -d             # Postgres(+pgvector) :5433 y Redis :6380
cp .env.example .env             # completar credenciales (ver tabla abajo)
uv run alembic upgrade head      # migra el schema

# 3 procesos (terminales separadas):
uv run uvicorn api.main:app --reload      # API + webhook
uv run arq worker.main.WorkerSettings     # worker (STT/OCR/sync/outbox)
uv run python -m scheduler.engine         # scheduler (recordatorios/briefing)

# con un túnel HTTPS (ngrok http 8000) y PUBLIC_BASE_URL seteado:
uv run python -m bot.commands set-webhook
```

> **Windows sin Docker:** los tests corren igual (`uv run pytest`, usan SQLite+fakeredis).
> Para Postgres/Redis locales hace falta WSL2 (`wsl --install`) + Docker Desktop.

## Verificación

```bash
uv run pytest          # 62 tests (unit + e2e voz→recordatorio con mocks)
uv run ruff check .    # lint
uv run mypy .          # types
```

## Credenciales necesarias (.env)

| Variable | De dónde sale |
|----------|---------------|
| `TELEGRAM_BOT_TOKEN` | @BotFather en Telegram |
| `TELEGRAM_WEBHOOK_SECRET` | generá un uuid (`python -c "import uuid;print(uuid.uuid4())"`) |
| `PUBLIC_BASE_URL` | URL de ngrok (dev) o de Railway (prod) |
| `GROQ_API_KEY` | console.groq.com (free tier — NLU + Whisper) |
| `FERNET_KEY` | `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
| `R2_*` | dash.cloudflare.com → R2 (opcional: sin esto, los archivos no se suben pero las notas funcionan) |
| `GOOGLE_CLIENT_*` / `MS_CLIENT_*` | console.cloud.google.com / portal.azure.com (opcional: calendarios) |
| `OLLAMA_BASE_URL` | Ollama local para embeddings (`ollama pull nomic-embed-text`); sin él, la memoria busca por texto |

## Deploy en Railway

1. Crear proyecto con **Postgres** (plugin con pgvector) y **Redis**.
2. Tres servicios sobre este repo (misma imagen Docker):
   - `api` → comando default del Dockerfile (corre `alembic upgrade head` y gunicorn).
   - `worker` → `arq worker.main.WorkerSettings`
   - `scheduler` → `python -m scheduler.engine`
3. Setear las env vars en los 3 servicios (`DATABASE_URL` con `postgresql+asyncpg://`).
4. Con la URL pública: `python -m bot.commands set-webhook`.
5. Healthcheck: `/health` (liveness) y `/ready` (DB+Redis).

## Arquitectura

```
update Telegram → webhook FastAPI → aiogram
   ├─ texto ──────────────→ NLU (tool-use, Groq/Ollama) → domain/* → evento
   ├─ voz ──→ arq worker → Whisper STT ─┘                              │
   └─ imagen → arq worker → Tesseract OCR + visión ─┘                  ▼
                                              gamification/engine (suscripto)
                                              puntos · racha · logros · ZSET ranking
```

- `core/` — config (falla rápido), DB async, Redis, Fernet, event bus, modelos.
- `domain/` — recordatorios, listas, memoria (pgvector), calendario (+outbox offline), briefing, privacidad.
- `gamification/` — subsistema independiente, solo reacciona a eventos.
- `scheduler/` — dispara recordatorios (poll DB cada 30 s, la DB es fuente de verdad), briefing diario por timezone, snapshot de ranking, GC de retención.
- `worker/` — STT, OCR, PDFs, reindexado de embeddings, sync de calendario, outbox.

### Decisiones de implementación (vs. blueprint)

- **Recordatorios sin jobstore compartido:** en lugar de jobs APScheduler por recordatorio
  (frágil entre procesos), el scheduler consulta la DB cada 30 s (`fired_at IS NULL AND due_at <= now`).
  Misma precisión (±1 min del RNF), cero estado duplicado.
- **Calendarios por REST (httpx):** los SDKs oficiales de Google/Microsoft son sync y
  bloquearían el event loop; se llama a las APIs REST directo, todo async.
- **`/calendario`:** comando extra para emitir el enlace OAuth firmado (state = user_id cifrado con Fernet, TTL 15 min).

## Comandos del bot

`/start` onboarding · `/puntos` `/racha` `/ranking` `/stats` `/logros` `/historial` gamificación ·
`/calendario` conectar Google/Outlook · `/exportar` `/borrartodo` `/privacidad` datos ·
y **lenguaje natural** para todo lo demás (texto, voz o foto).
