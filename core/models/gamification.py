from datetime import date, datetime

from sqlalchemy import BigInteger, Date, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.models.base import Base, created_at_col, uuid_fk_type

# en SQLite (tests) BigInteger no autoincrementa como PK; Integer sí
_BigIntPk = BigInteger().with_variant(Integer(), "sqlite")


class GamificationState(Base):
    __tablename__ = "gamification_state"

    user_id: Mapped[str] = mapped_column(
        uuid_fk_type(), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    last_active_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    streak_shields: Mapped[int] = mapped_column(Integer, default=0)


class PointEvent(Base):
    """Append-only, auditable. Particionable si crece el volumen."""

    __tablename__ = "point_events"

    id: Mapped[int] = mapped_column(_BigIntPk, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(
        uuid_fk_type(), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    event_type: Mapped[str] = mapped_column(Text, index=True)
    points: Mapped[int] = mapped_column(Integer)
    ref_id: Mapped[str | None] = mapped_column(uuid_fk_type(), nullable=True)
    created_at: Mapped[datetime] = created_at_col()
