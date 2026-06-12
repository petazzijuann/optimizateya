from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, SmallInteger, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.models.base import Base, created_at_col, updated_at_col, uuid_pk


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = uuid_pk()
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    username: Mapped[str | None] = mapped_column(Text, nullable=True)
    first_name: Mapped[str] = mapped_column(Text, default="")
    timezone: Mapped[str] = mapped_column(Text, default="America/Argentina/Buenos_Aires")
    locale: Mapped[str] = mapped_column(Text, default="es-AR")
    briefing_hour: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    leaderboard_opt_out: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarded: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created_at_col()
    updated_at: Mapped[datetime] = updated_at_col()
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
