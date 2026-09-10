"""Bounded cleanup hook for the 30-day Recently Deleted retention window."""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Memory, MemoryMedia
from app.services.media_storage import ObjectStorage


def purge_expired_deleted_memories(db: Session, storage: ObjectStorage | None) -> int:
    """Purge expired rows and their private media in a scheduled worker run."""
    if storage is None:
        return 0
    expired = db.scalars(
        select(Memory).where(
            Memory.deleted_at.is_not(None),
            Memory.deletion_expires_at <= datetime.now(UTC),
        )
    ).all()
    purged = 0
    for memory in expired:
        for media in db.scalars(
            select(MemoryMedia).where(MemoryMedia.memory_id == memory.id)
        ).all():
            storage.delete_object(media.object_key)
        db.delete(memory)
        purged += 1
    db.commit()
    return purged
