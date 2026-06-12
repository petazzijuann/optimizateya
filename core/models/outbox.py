from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from core.models.base import Base, created_at_col, uuid_fk_type, uuid_pk

OUTBOX_STATUSES = ("pending", "done", "failed")


class OutboxAction(Base):
    """Acción contra un servicio externo caído; el worker la reintenta con backoff."""

    __tablename__ = "outbox_actions"

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(
        uuid_fk_type(), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    action_type: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON(), "sqlite"), default=dict
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)
    created_at: Mapped[datetime] = created_at_col()
