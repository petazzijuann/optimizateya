# Optimizate Ya — Blueprint

> Generado por The Architect el 2026-06-11
> Archetype: API / Backend Service (bot conversacional + servicios de dominio)
> Basado en: *Brief funcional y técnico · Optimizate Ya v1.0 (Junio 2026)*

---

## 0. Cómo usar este blueprint

Este documento es **autocontenido**. Una instancia de Claude Code sin contexto previo puede construir el MVP completo siguiendo el **Build Order (sección 9)** paso a paso. Antes de escribir código:

1. Leé las secciones 1–8 para entender el producto y la arquitectura.
2. Seguí la sección 9 (Build Order) en orden estricto. No saltees pasos.
3. Pegá el contenido de la sección 16 como `CLAUDE.md` en la raíz del proyecto target.
4. Respetá las Reglas No Negociables (sección 17).

Idioma del producto y del bot: **español rioplatense** por defecto, con soporte multi-región.

---

## 1. Project Overview

### Vision

**Optimizate Ya** es un asistente personal conversacional que funciona como **"segunda memoria"** del usuario, viviendo dentro de Telegram —la app que la gente ya usa todos los días—. Permite gestionar **recordatorios, listas, archivos, calendarios y notas** sin abrir múltiples aplicaciones. Acepta **texto, notas de voz e imágenes** como entrada equivalente, y responde de forma conversacional. Su diferenciador es un **subsistema de gamificación nativo** (puntos, rachas diarias, ranking global) que convierte la organización personal en un hábito sostenido.

El MVP se acota a un único bot de Telegram con las funcionalidades suficientes para validar la propuesta de valor central. El roadmap posterior abre canales (WhatsApp, email, dashboard web), productividad avanzada (clasificación de correos, Google Workspace) y una capa social/plataforma.

### Propuesta de valor

> Una segunda memoria conversacional que vive en Telegram, escucha en texto, voz e imagen, recuerda todo lo que importa y premia el uso constante.

### Goals

- Que el usuario gestione su vida (recordatorios, listas, memoria, agenda) **sin salir del chat** y sin formularios.
- **Mínima fricción**: texto natural, voz e imagen son entradas de primera clase.
- **Privacidad por diseño**: solo se recolectan los datos imprescindibles para la tarea.
- **Hábito sostenido**: la gamificación recompensa la constancia con feedback positivo inmediato.
- **MVP delgado y de costo predecible**: managed services, sin over-engineering inicial.

### Success Metrics

- ≥ 60% de los usuarios que completan onboarding crean su primer recordatorio/lista/memoria.
- Retención semanal ≥ 40% (al menos 3 días activos por semana).
- Racha promedio > 5 días en usuarios activos.
- Latencia conversacional p95 < 3 s (texto) / < 8 s (voz con transcripción).
- Disponibilidad ≥ 99.5% en MVP.

### Alcance MVP (fase 1)

| Capacidad | Incluye |
|-----------|---------|
| Canal | Bot de Telegram funcional con onboarding básico |
| Entradas | Texto, nota de voz (transcripción), imagen (OCR) |
| Recordatorios | Crear, listar, editar, borrar; recurrencia (diaria, semanal, mensual, custom) |
| Listas | Crear listas; agregar / marcar / borrar ítems en lenguaje natural |
| Memoria (Memory Bubbles) | Guardar archivos/fotos/notas; recuperación por consulta natural |
| Calendarios | Sync con Google Calendar y Outlook (OAuth, lectura y escritura) |
| Briefing diario | Resumen automático de tareas y eventos del día |
| Gamificación | Puntos, racha, ranking global, comandos de consulta |
| Privacidad | Política clara + comandos de exportación/borrado a pedido |

Fases 2–5 (multicanal, productividad+, social, plataforma) quedan referenciadas en la sección 18.

---

## 2. Tech Stack

> Todas las decisiones de stack quedaban abiertas en el brief (cap. 9). Estas son las recomendaciones del arquitecto, con su rationale.

| Capa | Tecnología | Por qué |
|------|-----------|---------|
| Lenguaje | **Python 3.12** | Mejor ecosistema bot + LLM + multimodal; un solo lenguaje para bot, API, worker y scheduler |
| Bot | **aiogram v3** | Async-first, FSM integrado, la mejor librería de Telegram en Python |
| API / Web | **FastAPI** | Async, validación Pydantic v2, OpenAPI automática, webhooks |
| Servidor ASGI | **uvicorn** (+ gunicorn en prod) | Estándar para FastAPI async |
| Base de datos | **PostgreSQL 16 + pgvector** | Resuelve el caso mixto: relacional (users/recordatorios) **y** memoria semántica (Memory Bubbles) en un solo motor |
| ORM / migraciones | **SQLAlchemy 2.0 (async) + Alembic** | Python-nativo, migraciones versionadas y limpias |
| Cola / jobs | **Redis + arq** | Async-native; mismo Redis para cache, rate-limit y leaderboard. Jobs: transcripción, OCR, sync calendario, indexado |
| Scheduler | **APScheduler 3.x (jobstore SQLAlchemy/Postgres)** | Jobs persistentes por usuario, precisión ±1 min, simple para MVP |
| Object storage | **Cloudflare R2** | S3-compatible, **sin costos de egress** → costo predecible |
| LLM (NLU) | **Groq — Llama 3.1 8B Instant** (default) + **Llama 3.3 70B Versatile** (escalado). Local/dev: **Ollama** (`llama3.1` / `qwen2.5`) | **Gratuito** (Groq free tier / Ollama local), tool-use soportado, baja latencia. $0 por token |
| SDK LLM | **`openai` (Python), apuntado a Groq u Ollama** | Ambos exponen API **OpenAI-compatible**: un solo cliente, se cambia `base_url` + `model` por env (`LLM_PROVIDER`) |
| Speech-to-Text | **Groq Whisper large-v3-turbo** (fallback: `faster-whisper` local) | Free tier de Groq; multilingüe y rápido en notas cortas |
| OCR / Vision | **Tesseract** local (`pytesseract`) para extraer texto + modelo de visión open (`llama3.2-vision`/`qwen2.5-vl` en Ollama, o visión de Groq) para análisis semántico | Todo gratuito; OCR local sin costo, visión open para clasificar la imagen |
| Embeddings | **Ollama `nomic-embed-text`** (local, gratis, 768 dims) | Indexado semántico de Memory Bubbles sin costo |
| Vault OAuth | **Tokens cifrados con Fernet** en tabla dedicada; clave en secret manager | Cumple RNF: nunca en claro en la DB principal |
| Auth web (fase 2) | **JWT + bcrypt** | Email/password vinculado a la cuenta del bot, sin vendor lock-in |
| Calendarios | **Google Calendar API + Microsoft Graph (Outlook)** | OAuth2, lectura/escritura, permisos mínimos |
| Hosting | **Railway** (alt. Fly.io para regiones AR) | Postgres + Redis managed, deploy simple, costo predecible |
| Frontend (fase 2) | **React + Vite + Tailwind CSS** | SPA liviana para el dashboard, reusa la API FastAPI |
| Tests | **pytest + pytest-asyncio + httpx** | Estándar async para FastAPI/aiogram |
| Package manager | **uv** (alt. Poetry) | Resolución e instalación de dependencias ultrarrápida |
| Observabilidad | **structlog + Sentry + Prometheus client** | Logging estructurado, errores, métricas |

### Notas de uso de modelos (LLM gratuito)

- **Estrategia:** LLM **gratuito y provider-agnostic**. Por defecto **Groq** (free tier, inferencia rapidísima de modelos Llama abiertos); para desarrollo local o autohospedado sin costo, **Ollama**. Ambos exponen una API **OpenAI-compatible**, así que se usa el cliente `openai` cambiando solo `base_url` + `model` según `LLM_PROVIDER`.
- **NLU / orquestación:** `llama-3.1-8b-instant` (Groq) como router por defecto — rápido y suficiente para clasificar intención y ejecutar tool-use. Escalá a `llama-3.3-70b-versatile` (Groq) cuando la tarea es ambigua. Local: `llama3.1` o `qwen2.5` en Ollama (ambos soportan tool calling).
- **Vision/OCR:** OCR de texto con **Tesseract** local (gratis); para análisis semántico de la imagen, modelo de visión open (`llama3.2-vision` / `qwen2.5-vl` en Ollama, o el modelo de visión de Groq). Ver sección 7.
- **Tool-use** es el corazón del NLU: definí herramientas (`create_reminder`, `add_list_item`, `save_memory`, `query_memory`, `create_event`, etc.) en formato function-calling OpenAI y dejá que el modelo elija. Ver sección 5.
- **Costo:** Groq free tier + Ollama local = **$0 por token**. El rate-limit / presupuesto (sección 6 / RNF) se mantiene para no exceder los límites de rate del free tier de Groq.

---

## 3. Directory Structure

```
optimizateya/
├── pyproject.toml                # deps (uv/Poetry), config de ruff/pytest
├── uv.lock
├── .env.example                  # plantilla de variables (sin secretos)
├── Dockerfile                    # imagen única, multi-proceso vía comando
├── railway.toml                  # config de servicios (api, worker, scheduler)
├── alembic.ini
├── README.md
│
├── core/                         # Código compartido por todos los procesos
│   ├── __init__.py
│   ├── config.py                 # Settings con pydantic-settings (valida .env al boot)
│   ├── database.py               # async engine + async_session factory
│   ├── redis.py                  # cliente Redis compartido (cache, ZSET, rate-limit)
│   ├── crypto.py                 # Fernet encrypt/decrypt para tokens OAuth
│   ├── security.py               # bcrypt + JWT (fase 2)
│   ├── events.py                 # Event bus: publish/subscribe de eventos de dominio
│   ├── logging.py                # structlog: correlación por request_id + user_id (hash)
│   ├── errors.py                 # excepciones de dominio
│   └── models/                   # SQLAlchemy models (una entidad por archivo)
│       ├── __init__.py
│       ├── user.py
│       ├── reminder.py
│       ├── list.py               # List + ListItem
│       ├── memory.py             # MemoryItem (embedding + ocr_text)
│       ├── calendar.py           # CalendarConnection + CalendarEventCache
│       ├── gamification.py       # GamificationState + PointEvent
│       ├── achievement.py        # Achievement + UserAchievement
│       ├── outbox.py             # OutboxAction (modo offline)
│       └── feature_flag.py
│
├── bot/                          # aiogram v3 — interfaz Telegram
│   ├── __init__.py
│   ├── dispatcher.py             # crea Dispatcher, registra routers + middlewares
│   ├── commands.py               # set_my_commands (/puntos, /racha, ...)
│   ├── middleware/
│   │   ├── user.py               # resuelve telegram_id → User, lo inyecta al handler
│   │   ├── rate_limit.py         # throttling por usuario (Redis)
│   │   └── i18n.py               # detección de idioma / región
│   ├── handlers/
│   │   ├── start.py              # /start, onboarding (FSM: timezone, hora briefing)
│   │   ├── text.py               # mensaje de texto → NLU
│   │   ├── voice.py              # nota de voz → encola STT → NLU
│   │   ├── photo.py              # imagen → encola OCR/vision → NLU
│   │   ├── document.py           # archivo/PDF → guardar en memoria
│   │   ├── gamification.py       # /puntos /racha /ranking /stats /logros /historial
│   │   ├── privacy.py            # /exportar /borrartodo /privacidad
│   │   └── callbacks.py          # inline buttons (confirmar, snooze, marcar hecho)
│   ├── keyboards.py              # inline + reply keyboards
│   └── states.py                 # StatesGroup del FSM de onboarding
│
├── api/                          # FastAPI — webhooks + dashboard (fase 2)
│   ├── __init__.py
│   ├── main.py                   # app, CORS, health, monta routers, registra webhook
│   ├── dependencies.py           # get_db, get_current_user
│   └── routers/
│       ├── telegram.py           # POST /webhook/telegram (entrega updates a aiogram)
│       ├── oauth.py              # GET /oauth/google/{connect,callback}, idem outlook
│       ├── health.py             # GET /health, GET /ready
│       ├── auth.py               # (fase 2) register/login/refresh
│       └── dashboard.py          # (fase 2) stats, listas, memoria, gamificación
│
├── ai/                           # Capa de IA — provider-agnostic
│   ├── __init__.py
│   ├── client.py                 # LLMClient: OpenAI-compatible (Groq/Ollama) — retries, budget, fallback
│   ├── nlu.py                    # router NLU con tool-use → DomainAction
│   ├── tools.py                  # definición de tools (JSON schema) que mapean a dominio
│   ├── transcribe.py             # Groq Whisper (fallback faster-whisper local)
│   ├── vision.py                 # OCR + análisis semántico de imagen
│   ├── embeddings.py             # generar embeddings para memoria
│   ├── budget.py                 # rate-limit + presupuesto mensual de tokens (Redis)
│   └── prompts.py                # system prompts + few-shot (es rioplatense)
│
├── domain/                       # Servicios de dominio (lógica de negocio)
│   ├── __init__.py
│   ├── reminders.py              # crear/editar/borrar/listar; recurrencia; snooze
│   ├── lists.py                  # listas e ítems
│   ├── memory.py                 # guardar/indexar/recuperar (búsqueda vectorial)
│   ├── calendar.py               # crear/mover/cancelar eventos; detección de conflictos
│   ├── briefing.py               # arma el resumen diario
│   └── privacy.py                # export + borrado (tombstone / hard delete)
│
├── gamification/                 # SUBSISTEMA INDEPENDIENTE (event-driven)
│   ├── __init__.py
│   ├── engine.py                 # consume eventos → aplica puntos / racha / logros
│   ├── points.py                 # catálogo de puntos (tabla del brief, configurable)
│   ├── streaks.py                # cálculo de racha por timezone; récord histórico
│   ├── leaderboard.py            # Redis ZSET: rank, top-N, posición; snapshot a DB
│   ├── achievements.py           # evaluación de condiciones de logros
│   └── catalog.py                # definición declarativa de logros
│
├── scheduler/                    # APScheduler — jobs temporizados
│   ├── __init__.py
│   ├── engine.py                 # APScheduler con jobstore Postgres + Redis
│   ├── manager.py                # programar/cancelar/reprogramar por recordatorio
│   └── jobs/
│       ├── reminder_fire.py      # dispara recordatorio al usuario (con snooze/hecho)
│       ├── daily_briefing.py     # arma y envía el briefing diario a la hora del user
│       ├── calendar_reconcile.py # sync inverso periódico de cambios externos
│       ├── leaderboard_snapshot.py # persiste ranking desde Redis a Postgres
│       └── retention_gc.py       # hard-delete de tombstones vencidos (grace period)
│
├── worker/                       # arq — procesamiento asíncrono pesado
│   ├── __init__.py
│   ├── main.py                   # WorkerSettings (registra funciones)
│   └── tasks/
│       ├── transcribe.py         # descarga audio → STT → reinyecta a NLU
│       ├── ocr.py                # descarga imagen → vision/OCR → reinyecta a NLU
│       ├── index_memory.py       # genera embedding y persiste vector
│       ├── calendar_sync.py      # sincroniza eventos (push/pull) con backoff
│       └── outbox_flush.py       # reintenta acciones encoladas (modo offline)
│
├── alembic/
│   ├── env.py
│   └── versions/                 # migraciones
│
├── web/                          # (fase 2) React + Vite + Tailwind dashboard
│   └── ...
│
└── tests/
    ├── conftest.py               # fixtures: db de test, redis fake, cliente httpx
    ├── domain/                   # tests unitarios de servicios de dominio
    ├── gamification/             # tests del motor de puntos/racha/leaderboard
    ├── ai/                       # tests del NLU con tools mockeadas
    └── flows/                    # test e2e del flujo voz → recordatorio
```

---

## 4. Data Model

### Entidades principales

**users**
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID PK | id interno (aislamiento multi-tenant) |
| telegram_id | BIGINT UNIQUE | identidad del canal Telegram |
| username | TEXT NULL | @handle de Telegram |
| first_name | TEXT | |
| timezone | TEXT | IANA, ej. `America/Argentina/Buenos_Aires` |
| locale | TEXT | `es-AR` por defecto |
| briefing_hour | SMALLINT | hora local del briefing (0–23), NULL = off |
| leaderboard_opt_out | BOOLEAN | privacidad del ranking |
| created_at / updated_at | TIMESTAMPTZ | |
| deleted_at | TIMESTAMPTZ NULL | soft-delete (tombstone) |

**reminders**
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID PK | |
| user_id | UUID FK → users | indexado |
| title | TEXT | |
| due_at | TIMESTAMPTZ | próxima ejecución (en UTC) |
| recurrence | JSONB NULL | `{type: daily/weekly/monthly/cron, ...}` |
| status | ENUM | `pending`, `done`, `cancelled` |
| completed_at | TIMESTAMPTZ NULL | |
| completed_on_time | BOOLEAN NULL | para puntos (en hora vs tarde) |
| job_id | TEXT NULL | id del job en APScheduler |
| created_at / updated_at | TIMESTAMPTZ | |

**lists** / **list_items**
| lists | | | **list_items** | | |
|---|---|---|---|---|---|
| id UUID PK | | | id UUID PK | | |
| user_id FK | | | list_id FK → lists | | |
| name TEXT | | | content TEXT | | |
| created_at | | | is_done BOOLEAN | | conserva historial |
| | | | created_at / done_at | | |

**memory_items** (Memory Bubbles)
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID PK | |
| user_id | UUID FK | |
| kind | ENUM | `note`, `image`, `pdf`, `document`, `link` |
| storage_key | TEXT NULL | clave en R2 (NULL para notas de texto puro) |
| title | TEXT | |
| raw_text | TEXT NULL | nota o texto extraído (OCR/PDF) |
| ocr_text | TEXT NULL | texto crudo de OCR |
| tags | TEXT[] | sugeridos por LLM, editables |
| embedding | VECTOR(768) | pgvector (768 dims = `nomic-embed-text`); índice HNSW |
| created_at | TIMESTAMPTZ | |
| deleted_at | TIMESTAMPTZ NULL | tombstone |

**calendar_connections**
| Campo | Tipo | Notas |
|-------|------|-------|
| id | UUID PK | |
| user_id | UUID FK | |
| provider | ENUM | `google`, `outlook` |
| access_token_enc | BYTEA | **cifrado con Fernet** |
| refresh_token_enc | BYTEA | **cifrado** |
| expires_at | TIMESTAMPTZ | |
| scope | TEXT | permisos mínimos otorgados |
| sync_token | TEXT NULL | para sync incremental |

**calendar_events_cache** — espejo local liviano para detección de conflictos y briefing (id, user_id, provider, external_id, title, start_at, end_at, updated_at).

**gamification_state**
| Campo | Tipo | Notas |
|-------|------|-------|
| user_id | UUID PK FK | 1:1 con users |
| total_points | INT | |
| current_streak | INT | días consecutivos |
| longest_streak | INT | récord histórico |
| last_active_date | DATE | en timezone del user |
| streak_shields | INT | consumible (fase 4) |

**point_events** (append-only, auditable / particionable)
| Campo | Tipo | Notas |
|-------|------|-------|
| id | BIGSERIAL PK | |
| user_id | UUID FK | |
| event_type | TEXT | `reminder.created`, `reminder.completed_on_time`, ... |
| points | INT | |
| ref_id | UUID NULL | entidad relacionada |
| created_at | TIMESTAMPTZ | |

**achievements** (catálogo) / **user_achievements** (desbloqueos: user_id, achievement_id, unlocked_at).

**outbox_actions** — acciones encoladas cuando un servicio externo está caído (id, user_id, action_type, payload JSONB, attempts, next_retry_at, status).

**feature_flags** — (key TEXT PK, enabled BOOLEAN, rollout JSONB) con override por variable de entorno.

### Relaciones

- `users` 1—N `reminders`, `lists`, `memory_items`, `calendar_connections`, `point_events`, `user_achievements`.
- `lists` 1—N `list_items`.
- `users` 1—1 `gamification_state`.
- `achievements` N—N `users` vía `user_achievements`.

### Schema (extracto SQLAlchemy + pgvector)

```python
# core/models/memory.py
from pgvector.sqlalchemy import Vector
from sqlalchemy import String, Text, ARRAY, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from core.models.base import Base, uuid_pk, ts

class MemoryItem(Base):
    __tablename__ = "memory_items"
    id:          Mapped[str]  = uuid_pk()
    user_id:     Mapped[str]  = mapped_column(ForeignKey("users.id"), index=True)
    kind:        Mapped[str]  = mapped_column(String(16))
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    title:       Mapped[str]  = mapped_column(Text)
    raw_text:    Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_text:    Mapped[str | None] = mapped_column(Text, nullable=True)
    tags:        Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    embedding:   Mapped[list[float]] = mapped_column(Vector(768))  # nomic-embed-text
    created_at:  Mapped["ts"]
    deleted_at:  Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

```sql
-- Habilitar pgvector e índice de búsqueda semántica (migración Alembic)
CREATE EXTENSION IF NOT EXISTS vector;
CREATE INDEX ix_memory_embedding ON memory_items
  USING hnsw (embedding vector_cosine_ops);
-- Recuperación: SELECT ... WHERE user_id = :uid AND deleted_at IS NULL
--               ORDER BY embedding <=> :query_vec LIMIT 5;
```

---

## 5. API / Bot Surface

### Webhook & endpoints (FastAPI)

| Método | Path | Descripción | Auth |
|--------|------|-------------|------|
| POST | `/webhook/telegram/{secret}` | Recibe updates de Telegram y los entrega a aiogram | secret en path |
| GET | `/oauth/google/connect` | Inicia OAuth Google Calendar (state firmado) | bot-linked |
| GET | `/oauth/google/callback` | Callback: intercambia code, cifra y guarda tokens | — |
| GET | `/oauth/outlook/connect` | Idem Microsoft Graph | bot-linked |
| GET | `/oauth/outlook/callback` | Callback Outlook | — |
| GET | `/health` | Liveness | público |
| GET | `/ready` | Readiness (DB + Redis) | público |
| *(fase 2)* | `/auth/*`, `/dashboard/*` | Dashboard web | JWT |

**Modo webhook recomendado** para Telegram (no polling) en producción: menor latencia y escalado horizontal stateless. El secret en el path valida que el request viene de Telegram.

### Comandos del bot

| Comando | Pregunta natural equivalente | Respuesta |
|---------|------------------------------|-----------|
| `/start` | — | Onboarding (timezone, hora de briefing) |
| `/puntos` | "¿cuántos puntos tengo?" | Total acumulado + últimos sumados |
| `/racha` | "¿cómo va mi racha?" | Días actuales + récord histórico |
| `/ranking` | "¿en qué puesto voy?" | Posición global + top 10 |
| `/stats` | "dame mis estadísticas" | Puntos, racha, logros, % cumplimiento |
| `/logros` | "¿qué logros desbloqueé?" | Conseguidos + próximos a desbloquear |
| `/historial` | "mostrame mis últimas actividades" | Últimos eventos generadores de puntos |
| `/exportar` | "exportá mis datos" | Genera y envía export del usuario |
| `/borrartodo` | "borrá todo lo mío" | Confirmación → hard delete |
| `/privacidad` | — | Política de datos resumida |

Todo lo que se puede hacer por comando se puede hacer también por **lenguaje natural** (texto o voz): el NLU resuelve la intención.

### NLU con tool-use (corazón del sistema)

El módulo `ai/nlu.py` envía el mensaje del usuario al LLM (Groq Llama, u Ollama en local) con un conjunto de **tools** (function-calling OpenAI-compatible). El modelo elige cuál(es) invocar; cada tool mapea a un servicio de dominio.

```python
# ai/tools.py (extracto del schema de tools)
TOOLS = [
  {"name": "create_reminder", "description": "Crea un recordatorio único o recurrente.",
   "input_schema": {"type": "object", "properties": {
       "title": {"type": "string"},
       "due_at_natural": {"type": "string", "description": "fecha/hora en lenguaje natural, ej 'mañana 9am'"},
       "recurrence": {"type": "string", "enum": ["none","daily","weekly","monthly","custom"]}},
     "required": ["title", "due_at_natural"]}},
  {"name": "add_list_item", "description": "Agrega ítem(s) a una lista (la crea si no existe)."},
  {"name": "save_memory",   "description": "Guarda una nota/archivo en la memoria del usuario."},
  {"name": "query_memory",  "description": "Recupera de la memoria por consulta natural."},
  {"name": "create_event",  "description": "Crea un evento de calendario."},
  {"name": "query_agenda",  "description": "Consulta agenda/recordatorios del día."},
  # ... edit_reminder, complete_reminder, mark_list_item, etc.
]
```

Flujo: `update → (si voz/imagen) worker STT/OCR → texto → nlu.route() → tool_call → domain.* → evento → gamificación → respuesta`. Si la confianza de una inferencia multimodal es baja, el bot **pide confirmación** antes de ejecutar (RNF del brief).

### API Response Shape (dashboard fase 2)

```json
{ "success": true, "data": { }, "meta": { } }
{ "success": false, "error": { "code": "NOT_FOUND", "message": "...", "details": null } }
```

---

## 6. Subsistema de gamificación

> **Pieza diferenciadora.** Se diseña como **subsistema independiente, event-driven**, integrable con el resto vía eventos de dominio. Nunca acopla puntos dentro de la lógica de recordatorios/listas.

### Integración por eventos

Cada servicio de dominio **emite un evento** al event bus (`core/events.py`) tras una acción relevante. El `gamification/engine.py` está suscripto y reacciona:

```
domain.reminders.complete() ──emit──> "reminder.completed_on_time"
                                          │
                          gamification.engine consume
                                          ├── points.award(+10)
                                          ├── streaks.touch(user, date)
                                          ├── achievements.evaluate(user)
                                          └── leaderboard.incr(user, +10)  # Redis ZSET
```

### Catálogo de puntos (configurable; valores del brief, a calibrar en beta)

| Evento | Puntos | Notas |
|--------|--------|-------|
| Crear recordatorio | +5 | una vez por recordatorio |
| Cumplir recordatorio en hora | +10 | dentro de margen razonable |
| Cumplir recordatorio tarde | +3 | sigue contando, menos |
| Crear lista | +3 | |
| Completar lista entera | +15 | todos los ítems marcados |
| Guardar archivo / nota | +2 | |
| Conectar calendario | +20 | una sola vez |
| Uso diario (cualquier interacción) | +1 | suma para la racha |
| Bonus de racha (cada 7 días) | +25 | recompensa por constancia |
| Logro desbloqueado | variable | según catálogo |

Los valores viven en `gamification/points.py` como diccionario configurable (sin redeploy si se mueve a `feature_flags`/config).

### Rachas

- Una **interacción significativa** = crear, cumplir o consultar al menos una entidad.
- Se cuenta por **día calendario en la timezone del usuario**.
- Se rompe si pasa un día completo sin actividad.
- Se persiste `current_streak` y `longest_streak`. Cada 7 días → bonus.
- *(Fase 4)* "escudo de racha" consumible (`streak_shields`) para no penalizar un día aislado.

### Ranking global (resuelve Q3 del brief)

- **Leaderboard materializado en Redis Sorted Set** (`ZSET leaderboard:global`, score = `total_points`).
  - `ZINCRBY` al sumar puntos → O(log n).
  - `ZREVRANK` → posición del usuario instantánea ("estás 47°").
  - `ZREVRANGE 0 9 WITHSCORES` → top 10.
- **Snapshot periódico** a Postgres (`scheduler/jobs/leaderboard_snapshot.py`) para durabilidad y analytics.
- Usuarios con `leaderboard_opt_out = true` se excluyen del ZSET público.
- *(A definir con producto)* ligas por rango (bronce/plata/oro) y reseteo mensual/semanal.

### Logros (achievements)

Definidos de forma declarativa en `gamification/catalog.py`. Iniciales:

| Logro | Condición |
|-------|-----------|
| Primera memoria | guarda tu primer archivo/nota |
| Semana perfecta | 7 días seguidos cumpliendo todos los recordatorios |
| Centurión | 100 recordatorios cumplidos |
| Madrugador | cumple un recordatorio antes de las 8 AM, 5 veces |
| Cerebro maestro | guarda 50 elementos en la memoria |

`achievements.evaluate(user)` corre tras cada evento relevante y desbloquea los que cumplan condición.

---

## 7. Procesamiento multimodal

| Entrada | Pipeline | Proveedor |
|---------|----------|-----------|
| Voz | descarga audio Telegram → `worker/tasks/transcribe.py` → STT → texto → NLU | Groq Whisper large-v3-turbo (fallback `faster-whisper` local) |
| Imagen | descarga → `worker/tasks/ocr.py` → OCR (Tesseract) + análisis semántico (visión open) → NLU | Tesseract local + Groq/Ollama vision |
| PDF / documento | descarga → extracción de texto (pypdf) → guardar en memoria + indexar | local + embeddings |

Reglas:
- **STT con detección de idioma** (notas cortas). Latencia objetivo < 8 s end-to-end.
- **OCR** sobre tickets, capturas, pizarras, IBANs.
- **Análisis semántico**: clasificar la imagen como tarea / nota / ticket y proponer acción.
- **Confirmación previa** cuando la confianza es baja: el bot pregunta antes de crear/guardar.
- El audio/imagen original se procesa y **no se loguea contenido sensible** (RNF 8.1).

---

## 8. Integración de calendarios

- **OAuth2** con permisos mínimos (Google Calendar API + Microsoft Graph). Tokens **cifrados (Fernet)** en `calendar_connections`, nunca en claro.
- **Crear/mover/cancelar** eventos por lenguaje natural ("reunión con Juan el martes 15hs").
- **Detección de conflictos**: contra `calendar_events_cache`; el bot propone horarios alternativos.
- **Notificación previa** al evento por el canal del usuario (programada en APScheduler).
- **Reconciliación periódica** (`scheduler/jobs/calendar_reconcile.py`) con sync incremental (`sync_token`).
- **Modo offline (resuelve Q7):** si Google/Outlook está caído, la acción se persiste en `outbox_actions` y `worker/tasks/outbox_flush.py` reintenta con backoff exponencial.

---

## 9. Build Order

> **Sección más crítica.** Seguí los pasos en orden. Cada paso deja algo ejecutable/verificable.

**Step 1 — Scaffolding**
`uv init optimizateya`; configurar `pyproject.toml` (Python 3.12), `ruff`, `pytest`. Crear estructura de carpetas de la sección 3. Instalar deps base: `fastapi uvicorn aiogram sqlalchemy[asyncio] asyncpg alembic pydantic-settings redis arq apscheduler openai groq ollama pytesseract structlog cryptography pgvector`.

**Step 2 — Config & arranque**
`core/config.py` con `pydantic-settings` que valida TODAS las env vars al boot (falla rápido si falta una). `core/logging.py` con structlog (correlación `request_id` + `user_id` hasheado). `api/main.py` con `/health` y `/ready`. Verificación: `uvicorn api.main:app` responde 200 en `/health`.

**Step 3 — Base de datos & modelos**
`core/database.py` (async engine + session). Definir todos los modelos de la sección 4. Inicializar Alembic; primera migración: `CREATE EXTENSION vector` + todas las tablas + índice HNSW. Verificación: `alembic upgrade head` corre limpio contra Postgres local (Docker).

**Step 4 — Event bus & errores**
`core/events.py` (publish/subscribe in-process; interfaz que luego puede ir a Redis Streams). `core/errors.py` con excepciones de dominio. `core/crypto.py` (Fernet) con tests de round-trip.

**Step 5 — Bot esqueleto + webhook**
`bot/dispatcher.py`, `bot/commands.py`, middleware `user.py` (resuelve/crea `User` por `telegram_id`). `api/routers/telegram.py` (webhook con secret). Handler `/start` con FSM de onboarding (timezone + hora briefing). Verificación: con un bot de prueba, `/start` completa onboarding y persiste el user.

**Step 6 — Capa AI / NLU**
`ai/client.py` (wrapper LLM OpenAI-compatible con retries y selección Groq/Ollama por env), `ai/tools.py` (schemas), `ai/nlu.py` (router tool-use), `ai/prompts.py` (system prompt es-AR), `ai/budget.py` (rate-limit + presupuesto en Redis). Verificación: test que envía "recordame comprar pan mañana 9am" y el NLU devuelve un `create_reminder` tool_call con los campos correctos.

**Step 7 — Dominio: Recordatorios + Scheduler**
`domain/reminders.py` (crear/editar/borrar/listar, recurrencia, parsing de fecha relativa con la timezone del user). `scheduler/engine.py` (APScheduler + jobstore Postgres). `scheduler/manager.py` + `jobs/reminder_fire.py` (dispara con inline keyboard hecho/snooze/cancelar). Conectar `handlers/text.py` → NLU → dominio. Verificación: crear recordatorio por texto programa un job y dispara a la hora (±1 min).

**Step 8 — Dominio: Listas**
`domain/lists.py` + tools `add_list_item`, `mark_list_item`, `query_list`. Handler conectado. Verificación: "agregá leche a la lista del super" crea lista+ítem; "¿qué tengo en el super?" lo lista.

**Step 9 — Worker (arq) + Multimodal**
`worker/main.py` + `tasks/transcribe.py`, `tasks/ocr.py`, `tasks/index_memory.py`. Handlers `voice.py` y `photo.py` encolan jobs. `ai/transcribe.py` (Groq Whisper) y `ai/vision.py` (Tesseract + modelo de visión open Groq/Ollama). Verificación: nota de voz "recordame el dentista el jueves" crea el recordatorio (flujo e2e voz).

**Step 10 — Dominio: Memoria (Memory Bubbles)**
`domain/memory.py` (guardar en R2, generar embedding, indexar; recuperar por similitud vectorial filtrando por `user_id`). Storage R2 vía `boto3`/`aioboto3`. Tags automáticos por LLM. Verificación: guardar una imagen de factura y luego "¿dónde guardé la factura de luz?" la recupera.

**Step 11 — Calendarios + OAuth**
`api/routers/oauth.py` (Google + Outlook, tokens cifrados). `domain/calendar.py` (crear/mover/cancelar, conflictos). `worker/tasks/calendar_sync.py` + `scheduler/jobs/calendar_reconcile.py`. `outbox_actions` + `outbox_flush.py` (modo offline). Verificación: conectar Google Calendar y crear un evento por lenguaje natural; aparece en el calendario real.

**Step 12 — Gamificación**
`gamification/*`: engine suscripto a eventos, points, streaks, leaderboard (Redis ZSET), achievements, catalog. `handlers/gamification.py` (`/puntos`, `/racha`, `/ranking`, `/stats`, `/logros`, `/historial`). `scheduler/jobs/leaderboard_snapshot.py`. Verificación: cumplir un recordatorio suma +10, mueve el ZSET y `/ranking` muestra la posición.

**Step 13 — Briefing diario**
`domain/briefing.py` + `scheduler/jobs/daily_briefing.py` (a la hora local del user: agenda + recordatorios + estado de racha, tono conversacional). Verificación: programar briefing a +2 min y recibirlo.

**Step 14 — Privacidad**
`domain/privacy.py` + `handlers/privacy.py`: `/exportar` (dump del user), `/borrartodo` (hard delete inmediato), tombstone + `scheduler/jobs/retention_gc.py` (grace 30 días). Logs sin contenido sensible. Verificación: `/borrartodo` elimina datos y archivos en R2.

**Step 15 — Tests, observabilidad y deploy**
Tests de la sección 13 (incluido el flujo voz→recordatorio). Sentry + métricas Prometheus. `Dockerfile` + `railway.toml` con 3 procesos (api, worker, scheduler) + Postgres + Redis. Registrar webhook de Telegram a la URL pública. Verificación: deploy en Railway, `/health` OK, bot responde en producción.

*(Fase 2+)* Dashboard web React/Vite, WhatsApp, email — fuera del MVP.

---

## 10. Environment Setup

### Prerrequisitos
- Python 3.12, `uv`
- Docker (Postgres 16 + pgvector, Redis) para desarrollo local
- Cuenta de bot de Telegram (vía @BotFather)
- Túnel HTTPS para webhook en dev (ngrok / cloudflared)

### Variables de entorno

| Variable | Descripción | Dónde obtenerla |
|----------|-------------|-----------------|
| `TELEGRAM_BOT_TOKEN` | Token del bot | @BotFather |
| `TELEGRAM_WEBHOOK_SECRET` | Secret del path del webhook | generar (uuid) |
| `PUBLIC_BASE_URL` | URL pública HTTPS | ngrok / Railway |
| `DATABASE_URL` | Postgres async (`postgresql+asyncpg://...`) | Railway / Docker local |
| `REDIS_URL` | Conexión Redis | Railway / Docker local |
| `LLM_PROVIDER` | `groq` (default) u `ollama` | config |
| `GROQ_API_KEY` | NLU (Llama) + Whisper STT — free tier | console.groq.com |
| `GROQ_BASE_URL` | `https://api.groq.com/openai/v1` | fijo |
| `OLLAMA_BASE_URL` | Endpoint local Ollama, ej. `http://localhost:11434/v1` | instalación local |
| `LLM_MODEL` / `LLM_MODEL_HEAVY` | Modelos NLU, ej. `llama-3.1-8b-instant` / `llama-3.3-70b-versatile` | config |
| `VISION_MODEL` | Modelo de visión open, ej. `llama3.2-vision` | config |
| `EMBED_MODEL` | Embeddings, ej. `nomic-embed-text` (Ollama) | config |
| `R2_ACCOUNT_ID` / `R2_ACCESS_KEY_ID` / `R2_SECRET_ACCESS_KEY` / `R2_BUCKET` | Cloudflare R2 | dash.cloudflare.com |
| `FERNET_KEY` | Clave de cifrado de tokens OAuth | `Fernet.generate_key()` |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` | OAuth Google Calendar | console.cloud.google.com |
| `MS_CLIENT_ID` / `MS_CLIENT_SECRET` | OAuth Outlook (Graph) | portal.azure.com |
| `JWT_SECRET` | (fase 2) tokens del dashboard | generar |
| `SENTRY_DSN` | Errores (opcional) | sentry.io |
| `LLM_MONTHLY_BUDGET_TOKENS` | Presupuesto mensual por usuario | config |

### Comandos iniciales

```bash
uv sync                                   # instala dependencias
docker compose up -d                      # Postgres(+pgvector) y Redis locales
cp .env.example .env                       # completar credenciales
alembic upgrade head                       # migra el schema
# 3 procesos (en dev, terminales separadas):
uvicorn api.main:app --reload              # API + webhook
arq worker.main.WorkerSettings             # worker async
python -m scheduler.engine                 # scheduler
# registrar webhook de Telegram:
python -m bot.commands set-webhook
```

---

## 11. Dependencies

### Core
| Paquete | Propósito |
|---------|-----------|
| fastapi, uvicorn, gunicorn | API + webhook ASGI |
| aiogram (v3) | Bot de Telegram |
| sqlalchemy[asyncio], asyncpg, alembic | ORM async + migraciones |
| pgvector | Tipo vector + búsqueda semántica |
| pydantic, pydantic-settings | Modelos y validación de config |
| redis, arq | Cache/ZSET + cola de jobs |
| apscheduler | Scheduler de recordatorios |
| openai | Cliente OpenAI-compatible para Groq y Ollama (NLU + tool-use) |
| groq | Whisper STT (free tier) |
| ollama | Cliente local: NLU / visión / embeddings autohospedados |
| pytesseract | OCR local gratuito |
| faster-whisper | Fallback STT local (opcional) |
| aioboto3 | Cloudflare R2 (S3) |
| cryptography | Fernet (vault OAuth) |
| google-api-python-client, msal | Calendarios Google / Outlook |
| pypdf | Extracción de texto de PDFs |
| structlog, sentry-sdk, prometheus-client | Observabilidad |
| python-dateutil, pytz/zoneinfo | Fechas relativas + timezones |

### Dev
| Paquete | Propósito |
|---------|-----------|
| pytest, pytest-asyncio, httpx | Tests async |
| ruff | Lint + format |
| mypy | Type checking |
| testcontainers | Postgres/Redis efímeros en tests |
| fakeredis | Redis en memoria para unit tests |

---

## 12. Deployment Strategy

### Hosting — Railway
Una imagen Docker, **tres servicios/procesos** sobre el mismo código:
- `api` — `gunicorn -k uvicorn.workers.UvicornWorker api.main:app` (webhook + endpoints)
- `worker` — `arq worker.main.WorkerSettings`
- `scheduler` — `python -m scheduler.engine`

Addons managed: **Postgres** (con pgvector) y **Redis**. Object storage en **Cloudflare R2** (externo).

### CI/CD (minimal para MVP)
- Push a `main` → build + deploy automático.
- PR → lint (`ruff`) + `mypy` + `pytest`.
- Migraciones: `alembic upgrade head` como release command antes de levantar la app.

### Health checks & observabilidad (RNF 8.4)
- `/health` (liveness) y `/ready` (DB + Redis) configurados en Railway.
- Logging estructurado con correlación `request_id` + `user_id` (hash). **Nunca** loguear mensajes ni transcripciones completas.
- Métricas de negocio: DAU, recordatorios creados/cumplidos, racha promedio, retención.
- Métricas técnicas: latencia por endpoint, tasa de error del LLM, tiempo de cola de jobs.
- Alertas sobre degradación de Telegram, proveedor LLM y Google/Outlook APIs.

### Entornos
- **dev**: local (Docker + ngrok). **prod**: Railway. Preview deploys = staging (sin entorno staging dedicado en MVP).

---

## 13. Testing Strategy

### Unit
- `domain/*`: recurrencia, parsing de fechas relativas por timezone, transiciones de estado de recordatorios.
- `gamification/*`: cálculo de puntos, racha (rotura por timezone), rank en ZSET, evaluación de logros.
- `ai/nlu.py`: con el LLM mockeado, verificar mapeo de intención → tool_call correcto.

### Integration
- Rutas FastAPI con `httpx` + DB de test (testcontainers). OAuth callbacks (tokens cifrados round-trip). Webhook → dispatch de aiogram.

### E2E (flujo crítico del brief)
- **Voz → recordatorio**: audio simulado → `transcribe` (mock STT) → NLU → `create_reminder` → job programado → disparo → evento → gamificación (+puntos) → confirmación. Es el caso de uso que recorre todas las capas; debe tener test e2e.

Framework: **pytest + pytest-asyncio**. Objetivo: cobertura alta en `domain/` y `gamification/`.

---

## 14. Requerimientos No Funcionales (mapeo del cap. 8 del brief)

**Privacidad y seguridad (8.1)**
- Data minimization: recolectar solo lo imprescindible.
- TLS en tránsito; cifrado en reposo de archivos del usuario (R2).
- Tokens OAuth en **vault cifrado (Fernet)**, nunca en claro en la DB principal.
- Comandos `/exportar` y `/borrartodo`.
- Logs de auditoría sin contenido sensible. Cumplimiento GDPR / leyes locales.

**Disponibilidad y rendimiento (8.2)**
- 99.5% MVP → 99.9% al escalar. Latencia < 3 s (texto) / < 8 s (voz).
- Scheduler con precisión ±1 min. Reintentos automáticos en envíos a canales externos.

**Escalabilidad (8.3)**
- Servicios de aplicación **stateless** → escalado horizontal.
- Cola desacoplada (arq) para transcripción/OCR/sync.
- `point_events` particionable si crece el volumen.
- Caché de lecturas frecuentes (ranking, estado de usuario) en Redis.

---

## 15. Skills to Use During Build

| Skill | Cuándo usar | Por qué |
|-------|-------------|---------|
| `/deep-research` | Step 6/11 — calibrar prompts es-AR, comparar STT/OCR, OAuth de Graph | Datos actuales sobre APIs y proveedores |
| `/find-skills` | Antes del Step 1 | Descubrir skills útiles para el build |
| `/frontend-design` | Fase 2 (dashboard web) | UI distintiva y production-grade |
| `/shadcn-ui` | Fase 2 (si se adopta shadcn) | Componentes del dashboard |
| `/ui-ux-pro-max` | Fase 2 | Sistema visual del dashboard |
| `/playwright-cli` | Fase 2 (E2E del dashboard) | Automatización de browser |

Durante el MVP (bot backend) el foco es Python/infra; las skills de UI se activan en la fase 2.

---

## 16. CLAUDE.md para el proyecto target

```markdown
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
```

---

## 17. Reglas No Negociables (builder)

1. **Seguí el Build Order en orden.** Cada paso debe quedar verificable antes de avanzar.
2. **Privacidad por diseño.** Nunca loguear contenido sensible; tokens OAuth siempre cifrados; honrar export/borrado.
3. **Aislamiento multi-tenant.** Toda query de dominio filtra por `user_id`. Sin excepciones.
4. **Gamificación event-driven.** El subsistema reacciona a eventos; jamás se acopla dentro del dominio.
5. **Todo async.** Sin llamadas bloqueantes en handlers/endpoints; trabajo pesado va al worker.
6. **Validación estricta.** Pydantic en toda entrada; config validada al boot (falla rápido si falta una env var).
7. **Multimodal → texto → NLU.** Voz e imagen se normalizan a texto antes de resolver intención; pedir confirmación si la confianza es baja.
8. **Costo predecible.** Rate-limit y presupuesto mensual de tokens por usuario; managed services; sin over-engineering.

---

## 18. Roadmap posterior (referencia)

| Fase | Foco | Entregable |
|------|------|------------|
| Fase 2 — Multicanal | WhatsApp Business API, ingestión de email, dashboard web (Memory Bubbles visuales) | Acceso desde 3 canales + visión global |
| Fase 3 — Productividad+ | Clasificación de correos, redacción asistida (autopilot con confirmación), Google Workspace | Inbox inteligente |
| Fase 4 — Social | Recordatorios entre amigos/grupos, memoria a largo plazo, perfiles compartidos, escudo de racha | Funcionalidades entre usuarios |
| Fase 5 — Plataforma | API pública, integraciones de terceros, marketplace de plugins | Extensibilidad |

---

*Fin del blueprint — Optimizate Ya · generado por The Architect a partir del brief v1.0.*
