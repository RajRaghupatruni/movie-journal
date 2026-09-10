from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Computed,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.db.base import Base

MEMORY_SEARCH_EXPRESSION = (
    "to_tsvector('simple'::regconfig, title || ' ' || coalesce(notes, '') || ' ' || "
    "coalesce(metadata::text, ''))"
)


class Memory(Base):
    __tablename__ = "memories"
    __table_args__ = (
        Index("ix_memories_tandem_local_date", "tandem_id", "local_date", "id"),
        Index("ix_memories_tandem_category", "tandem_id", "category"),
        Index("ix_memories_tandem_updated_at", "tandem_id", "updated_at"),
        Index("ix_memories_search_vector", "search_vector", postgresql_using="gin"),
        UniqueConstraint("id", "tandem_id", name="uq_memories_id_tandem"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tandem_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tandems.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    local_date: Mapped[date] = mapped_column(Date, nullable=False)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_by: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1", default=1)
    nostalgia_eligible: Mapped[bool] = mapped_column(
        nullable=False, server_default="true", default=True
    )
    schema_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="1", default=1
    )
    memory_metadata: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )
    search_vector: Mapped[object] = mapped_column(
        TSVECTOR,
        Computed(MEMORY_SEARCH_EXPRESSION, persisted=True),
        nullable=False,
    )


class MemoryParticipant(Base):
    __tablename__ = "memory_participants"
    __table_args__ = (
        ForeignKeyConstraint(
            ["memory_id", "tandem_id"],
            ["memories.id", "memories.tandem_id"],
            ondelete="CASCADE",
            name="fk_memory_participants_memory_tandem",
        ),
        ForeignKeyConstraint(
            ["tandem_id", "user_id"],
            ["tandem_members.tandem_id", "tandem_members.user_id"],
            ondelete="RESTRICT",
            name="fk_memory_participants_membership",
        ),
        Index("ix_memory_participants_tandem_user", "tandem_id", "user_id"),
    )

    memory_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tandem_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, nullable=False)


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (
        UniqueConstraint("id", "tandem_id", name="uq_tags_id_tandem"),
        UniqueConstraint("tandem_id", "normalized_name", name="uq_tags_tandem_normalized_name"),
        Index("ix_tags_tandem_name", "tandem_id", "name"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tandem_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tandems.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MemoryTag(Base):
    __tablename__ = "memory_tags"
    __table_args__ = (
        ForeignKeyConstraint(
            ["memory_id", "tandem_id"],
            ["memories.id", "memories.tandem_id"],
            ondelete="CASCADE",
            name="fk_memory_tags_memory_tandem",
        ),
        ForeignKeyConstraint(
            ["tag_id", "tandem_id"],
            ["tags.id", "tags.tandem_id"],
            ondelete="CASCADE",
            name="fk_memory_tags_tag_tandem",
        ),
        Index("ix_memory_tags_tandem_tag", "tandem_id", "tag_id"),
    )

    memory_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tag_id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    tandem_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)


class ActivityEvent(Base):
    __tablename__ = "activity_events"
    __table_args__ = (
        Index("ix_activity_events_tandem_created_at", "tandem_id", "created_at", "id"),
        Index("ix_activity_events_entity", "entity_type", "entity_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    tandem_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("tandems.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    entity_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    correlation_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
