"""E2E del flujo crítico: nota de voz → STT → NLU → recordatorio → gamificación.

Recorre todas las capas con los servicios externos mockeados:
audio falso → transcripción mockeada → LLM mockeado (tool_call) →
domain.reminders → evento → engine de puntos → respuesta por el bot.
"""

from types import SimpleNamespace

from sqlalchemy import select

from ai.transcribe import set_groq_client
from core.models import GamificationState, PointEvent, Reminder
from gamification.engine import register, seed_achievements
from tests.conftest import make_tool_call
from worker.tasks.transcribe import transcribe_voice


class FakeBot:
    def __init__(self):
        self.sent: list[tuple[int, str]] = []

    async def get_file(self, file_id):
        return SimpleNamespace(file_path=f"voice/{file_id}.ogg")

    async def download_file(self, file_path, destination):
        destination.write(b"\x4f\x67\x67fake-ogg-audio")

    async def send_message(self, chat_id, text, **kwargs):
        self.sent.append((chat_id, text))


class FakeGroq:
    """Simula groq.AsyncGroq.audio.transcriptions.create."""

    def __init__(self, text: str):
        async def create(**kwargs):
            return text

        self.audio = SimpleNamespace(transcriptions=SimpleNamespace(create=create))


async def test_voice_note_creates_reminder_and_awards_points(session, user, redis, llm):
    # preparar mundo
    await seed_achievements(session)
    await session.commit()
    register()
    set_groq_client(FakeGroq("recordame el dentista mañana a las 9"))
    llm.tool_calls = [
        make_tool_call(
            "create_reminder",
            {"title": "dentista", "due_at_natural": "mañana a las 9", "recurrence": "none"},
        )
    ]
    bot = FakeBot()

    # ejecutar el task del worker tal cual lo haría arq
    await transcribe_voice({"bot": bot}, user_id=user.id, chat_id=4242, file_id="abc123")

    # 1) el recordatorio existe y es del usuario correcto
    rows = await session.execute(select(Reminder).where(Reminder.user_id == user.id))
    reminders = list(rows.scalars())
    assert len(reminders) == 1
    assert reminders[0].title == "dentista"
    assert reminders[0].status == "pending"

    # 2) la gamificación reaccionó al evento (+5 creado, +1 uso diario)
    rows = await session.execute(select(PointEvent).where(PointEvent.user_id == user.id))
    types = {p.event_type for p in rows.scalars()}
    assert "reminder.created" in types
    assert "daily.interaction" in types
    state = await session.get(GamificationState, user.id)
    await session.refresh(state)
    assert state.total_points == 6
    assert state.current_streak == 1

    # 3) el usuario recibió la transcripción + confirmación
    assert len(bot.sent) == 1
    chat_id, text = bot.sent[0]
    assert chat_id == 4242
    assert "Escuché" in text and "dentista" in text

    set_groq_client(None)


async def test_empty_audio_gives_friendly_error(session, user, redis, llm):
    set_groq_client(FakeGroq(""))
    bot = FakeBot()
    await transcribe_voice({"bot": bot}, user_id=user.id, chat_id=1, file_id="x")
    assert "vacío" in bot.sent[0][1]
    set_groq_client(None)
