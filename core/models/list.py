from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from core.models.base import Base, created_at_col, uuid_fk_type, uuid_pk


class List(Base):
    __tablename__ = "lists"

    id: Mapped[str] = uuid_pk()
    user_id: Mapped[str] = mapped_column(
        uuid_fk_type(), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = created_at_col()

    items: Mapped[list["ListItem"]] = relationship(
        back_populates="list", cascade="all, delete-orphan", lazy="selectin"
    )


class ListItem(Base):
    __tablename__ = "list_items"

    id: Mapped[str] = uuid_pk()
    list_id: Mapped[str] = mapped_column(
        uuid_fk_type(), ForeignKey("lists.id", ondelete="CASCADE"), index=True
    )
    content: Mapped[str] = mapped_column(Text)
    is_done: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = created_at_col()
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    list: Mapped["List"] = relationship(back_populates="items")
