import logging

# ruff: noqa: E501
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.core.logging import request_id
from app.db.session import get_db, set_current_user_id
from app.models import (
    ActivityEvent,
    Memory,
    MemoryMedia,
    MemoryParticipant,
    MemoryReflection,
    MemoryTag,
    Tag,
    Tandem,
    TandemMember,
    TandemUserPreference,
    User,
)
from app.schemas.memory import (
    DuplicateMemoryResponse,
    MemberSummary,
    MemoryCategory,
    MemoryCreate,
    MemoryListResponse,
    MemoryMediaResponse,
    MemoryPatch,
    MemoryResponse,
    MemoryWrite,
    ReflectionResponse,
    ReflectionWrite,
    normalize_tag,
)
from app.services.auth import get_current_user
from app.services.authorization import TandemAccess, require_tandem_member
from app.services.media_storage import ObjectStorage
from app.services.notifications import create_notification

router = APIRouter(prefix="/tandems/{tandem_id}/memories", tags=["memories"])
logger = logging.getLogger(__name__)


def _event(
    db: Session,
    *,
    tandem_id: UUID,
    actor_user_id: UUID,
    entity_id: UUID,
    event_type: str,
    payload: dict | None = None,
) -> None:
    db.add(
        ActivityEvent(
            tandem_id=tandem_id,
            entity_type="memory",
            entity_id=entity_id,
            event_type=event_type,
            actor_user_id=actor_user_id,
            correlation_id=request_id.get(),
            payload=payload or {},
        )
    )


def _validate_participants(db: Session, tandem_id: UUID, participant_ids: list[UUID]) -> list[UUID]:
    unique_ids = list(dict.fromkeys(participant_ids))
    if not unique_ids:
        return []
    found = set(
        db.scalars(
            select(TandemMember.user_id).where(
                TandemMember.tandem_id == tandem_id, TandemMember.user_id.in_(unique_ids)
            )
        ).all()
    )
    if len(found) != len(unique_ids):
        raise HTTPException(
            status_code=422, detail="All participants must be members of this tandem"
        )
    return unique_ids


def _tag_ids(db: Session, tandem_id: UUID, names: list[str]) -> list[UUID]:
    ids: list[UUID] = []
    for name in names:
        normalized = normalize_tag(name)
        db.execute(
            pg_insert(Tag)
            .values(tandem_id=tandem_id, name=normalized, normalized_name=normalized)
            .on_conflict_do_nothing(index_elements=["tandem_id", "normalized_name"])
        )
        tag_id = db.scalar(
            select(Tag.id).where(Tag.tandem_id == tandem_id, Tag.normalized_name == normalized)
        )
        if tag_id is not None:
            ids.append(tag_id)
    return ids


def _load_related(
    db: Session, memories: list[Memory]
) -> dict[UUID, tuple[list[MemberSummary], list[str]]]:
    memory_ids = [memory.id for memory in memories]
    if not memory_ids:
        return {}
    participant_rows = db.execute(
        select(
            MemoryParticipant.memory_id,
            MemoryParticipant.user_id,
            User.display_name,
            MemoryParticipant.participant_display_name,
        )
        .outerjoin(User, User.id == MemoryParticipant.user_id)
        .where(MemoryParticipant.memory_id.in_(memory_ids))
    ).all()
    tag_rows = db.execute(
        select(MemoryTag.memory_id, Tag.name)
        .join(Tag, Tag.id == MemoryTag.tag_id)
        .where(MemoryTag.memory_id.in_(memory_ids))
        .order_by(Tag.name)
    ).all()
    related: dict[UUID, tuple[list[MemberSummary], list[str]]] = {
        memory_id: ([], []) for memory_id in memory_ids
    }
    for memory_id, user_id, display_name, saved_name in participant_rows:
        related[memory_id][0].append(
            MemberSummary(
                user_id=user_id,
                display_name=display_name or saved_name or "Former member",
            )
        )
    for memory_id, name in tag_rows:
        related[memory_id][1].append(name)
    for participants, _ in related.values():
        participants.sort(key=lambda member: (member.display_name.casefold(), member.user_id.hex))
    return related


def _responses(
    db: Session,
    memories: list[Memory],
    storage: ObjectStorage | None = None,
    current_user_id: UUID | None = None,
) -> list[MemoryResponse]:
    related = _load_related(db, memories)
    memory_ids = [memory.id for memory in memories]
    media_by_memory: dict[UUID, list[MemoryMediaResponse]] = {
        memory_id: [] for memory_id in memory_ids
    }
    if memory_ids:
        media = db.scalars(
            select(MemoryMedia)
            .where(MemoryMedia.memory_id.in_(memory_ids))
            .order_by(MemoryMedia.display_order, MemoryMedia.created_at, MemoryMedia.id)
        ).all()
        for item in media:
            url = None
            if storage:
                try:
                    url = storage.create_read_url(item.object_key)
                except Exception:
                    # A signed-read outage should degrade Timeline/Today thumbnails only.
                    logger.warning("media_read_url_failed")
            media_by_memory[item.memory_id].append(
                MemoryMediaResponse(
                    id=item.id,
                    memory_id=item.memory_id,
                    content_type=item.content_type,
                    byte_size=item.byte_size,
                    width=item.width,
                    height=item.height,
                    created_at=item.created_at,
                    display_order=item.display_order,
                    url=url,
                )
            )
    tandem_names = (
        dict(
            db.execute(
                select(Tandem.id, Tandem.name).where(Tandem.id.in_({m.tandem_id for m in memories}))
            ).all()
        )
        if memories
        else {}
    )
    reflections_by_memory: dict[UUID, list[ReflectionResponse]] = {
        memory_id: [] for memory_id in memory_ids
    }
    if memory_ids:
        reflection_rows = db.execute(
            select(MemoryReflection, User.display_name)
            .outerjoin(User, User.id == MemoryReflection.user_id)
            .where(MemoryReflection.memory_id.in_(memory_ids))
            .order_by(MemoryReflection.created_at, MemoryReflection.id)
        ).all()
        for reflection, display_name in reflection_rows:
            reflections_by_memory[reflection.memory_id].append(
                ReflectionResponse(
                    id=reflection.id,
                    user_id=reflection.user_id,
                    display_name=display_name or "Former member",
                    rating=reflection.rating,
                    note=reflection.note,
                    reaction=reflection.reaction,
                    created_at=reflection.created_at,
                    updated_at=reflection.updated_at,
                )
            )
    return [
        MemoryResponse(
            id=memory.id,
            tandem_id=memory.tandem_id,
            tandem_name=tandem_names.get(memory.tandem_id),
            category=memory.category,
            title=memory.title,
            local_date=memory.local_date,
            end_date=memory.end_date,
            occurred_at=memory.occurred_at,
            timezone=memory.timezone,
            notes=memory.notes,
            rating=memory.rating,
            created_by=memory.created_by,
            created_at=memory.created_at,
            updated_at=memory.updated_at,
            version=memory.version,
            nostalgia_eligible=memory.nostalgia_eligible,
            schema_version=memory.schema_version,
            metadata=memory.memory_metadata,
            participants=related[memory.id][0],
            tags=related[memory.id][1],
            media=media_by_memory[memory.id],
            reflections=reflections_by_memory[memory.id],
            my_reflection=next(
                (
                    item
                    for item in reflections_by_memory[memory.id]
                    if item.user_id == current_user_id
                ),
                None,
            ),
            deleted_at=memory.deleted_at,
            deletion_expires_at=memory.deletion_expires_at,
        )
        for memory in memories
    ]


def _one(db: Session, tandem_id: UUID, memory_id: UUID, *, include_deleted: bool = False) -> Memory:
    statement = select(Memory).where(Memory.id == memory_id, Memory.tandem_id == tandem_id)
    if not include_deleted:
        statement = statement.where(Memory.deleted_at.is_(None))
    memory = db.scalar(statement)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


def _apply_write(memory: Memory, payload: MemoryWrite) -> None:
    memory.category = payload.category.value
    memory.title = payload.title
    memory.local_date = payload.local_date
    memory.end_date = payload.end_date
    memory.occurred_at = payload.occurred_at
    memory.timezone = payload.timezone
    memory.notes = payload.notes
    memory.rating = payload.rating
    memory.memory_metadata = payload.metadata
    memory.nostalgia_eligible = payload.nostalgia_eligible


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
def create_memory(
    request: Request,
    payload: MemoryCreate,
    access: TandemAccess = Depends(require_tandem_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemoryResponse:
    participants = _validate_participants(db, access.tandem.id, payload.participant_ids)
    memory = Memory(
        tandem_id=access.tandem.id,
        created_by=current_user.id,
        category=payload.category.value,
        title=payload.title,
        local_date=payload.local_date,
        end_date=payload.end_date,
        occurred_at=payload.occurred_at,
        timezone=payload.timezone,
        notes=payload.notes,
        rating=payload.rating,
        memory_metadata=payload.metadata,
        nostalgia_eligible=payload.nostalgia_eligible,
    )
    db.add(memory)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=(
                "A movie memory for this title already exists on that date; use a different "
                "date for a repeat watch"
            ),
        ) from None
    db.add_all(
        [
            MemoryParticipant(
                memory_id=memory.id,
                tandem_id=access.tandem.id,
                user_id=user_id,
                participant_display_name=db.scalar(
                    select(User.display_name).where(User.id == user_id)
                ),
            )
            for user_id in participants
        ]
    )
    if payload.rating is not None or payload.notes:
        db.add(
            MemoryReflection(
                memory_id=memory.id,
                tandem_id=access.tandem.id,
                user_id=current_user.id,
                rating=payload.rating,
                note=payload.notes,
            )
        )
    for tag_id in _tag_ids(db, access.tandem.id, payload.tags):
        db.add(MemoryTag(memory_id=memory.id, tag_id=tag_id, tandem_id=access.tandem.id))
    _event(
        db,
        tandem_id=access.tandem.id,
        actor_user_id=current_user.id,
        entity_id=memory.id,
        event_type="MemoryCreated",
    )
    for user_id in participants:
        if user_id != current_user.id:
            _event(
                db,
                tandem_id=access.tandem.id,
                actor_user_id=current_user.id,
                entity_id=memory.id,
                event_type="ParticipantAdded",
                payload={"user_id": str(user_id)},
            )
    for tag in payload.tags:
        _event(
            db,
            tandem_id=access.tandem.id,
            actor_user_id=current_user.id,
            entity_id=memory.id,
            event_type="TagAdded",
            payload={"tag": tag},
        )
    recipients = db.scalars(
        select(TandemMember.user_id)
        .outerjoin(
            TandemUserPreference,
            (TandemUserPreference.tandem_id == TandemMember.tandem_id)
            & (TandemUserPreference.user_id == TandemMember.user_id),
        )
        .where(
            TandemMember.tandem_id == access.tandem.id,
            TandemMember.user_id != current_user.id,
            (
                TandemUserPreference.routine_notifications_enabled.is_(True)
                | TandemUserPreference.id.is_(None)
            ),
        )
    ).all()
    for recipient_id in recipients:
        create_notification(
            db,
            user_id=recipient_id,
            notification_type="memory_added",
            actor_user_id=current_user.id,
            tandem_id=access.tandem.id,
            memory_id=memory.id,
            payload={"memory_title": memory.title, "tandem_name": access.tandem.name},
            dedupe_key=f"memory-added:{memory.id}:{recipient_id}",
        )
    db.commit()
    set_current_user_id(db, str(current_user.id))
    db.refresh(memory)
    return _responses(
        db, [memory], getattr(request.app.state, "object_storage", None), current_user.id
    )[0]


@router.get("", response_model=MemoryListResponse)
def list_memories(
    request: Request,
    tandem_id: UUID,
    access: TandemAccess = Depends(require_tandem_member),
    db: Session = Depends(get_db),
    category: MemoryCategory | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    year: int | None = Query(default=None, ge=1900, le=2200),
    participant: UUID | None = None,
    rating_min: int | None = Query(default=None, ge=1, le=10),
    rating_max: int | None = Query(default=None, ge=1, le=10),
    tag: str | None = Query(default=None, max_length=64),
    q: str | None = Query(default=None, max_length=100),
    offset: int = Query(default=0, ge=0, le=10000),
    limit: int = Query(default=50, ge=1, le=100),
) -> MemoryListResponse:
    if from_date and to_date and to_date < from_date:
        raise HTTPException(status_code=422, detail="to_date must be on or after from_date")
    if rating_min and rating_max and rating_max < rating_min:
        raise HTTPException(status_code=422, detail="rating_max must be at least rating_min")
    statement = select(Memory).where(
        Memory.tandem_id == access.tandem.id,
        Memory.deleted_at.is_(None),
    )
    if category:
        statement = statement.where(Memory.category == category.value)
    if from_date:
        statement = statement.where(Memory.local_date >= from_date)
    if to_date:
        statement = statement.where(Memory.local_date <= to_date)
    if year:
        statement = statement.where(
            Memory.local_date >= date(year, 1, 1), Memory.local_date < date(year + 1, 1, 1)
        )
    if participant:
        statement = statement.where(
            exists().where(
                MemoryParticipant.memory_id == Memory.id,
                MemoryParticipant.user_id == participant,
            )
        )
    if rating_min:
        statement = statement.where(Memory.rating >= rating_min)
    if rating_max:
        statement = statement.where(Memory.rating <= rating_max)
    if tag:
        normalized = normalize_tag(tag)
        tag_filter = aliased(Tag)
        statement = statement.where(
            exists()
            .where(MemoryTag.memory_id == Memory.id)
            .where(MemoryTag.tag_id == tag_filter.id)
            .where(
                tag_filter.tandem_id == access.tandem.id,
                tag_filter.normalized_name == normalized,
            )
        )
    if q and q.strip():
        search_query = func.plainto_tsquery("simple", q.strip())
        statement = (
            statement.where(
                or_(
                    Memory.search_vector.op("@@")(search_query),
                    Tag.normalized_name.ilike(f"%{q.strip()}%"),
                )
            )
            .outerjoin(MemoryTag, MemoryTag.memory_id == Memory.id)
            .outerjoin(Tag, Tag.id == MemoryTag.tag_id)
        )
    statement = (
        statement.order_by(Memory.local_date.desc(), Memory.id.desc())
        .offset(offset)
        .limit(limit + 1)
    )
    memories = db.scalars(statement).unique().all()
    has_more = len(memories) > limit
    memories = memories[:limit]
    return MemoryListResponse(
        items=_responses(
            db, memories, getattr(request.app.state, "object_storage", None), access.member.user_id
        ),
        offset=offset,
        limit=limit,
        next_offset=offset + limit if has_more else None,
    )


@router.get("/duplicates", response_model=list[DuplicateMemoryResponse])
def find_duplicates(
    tandem_id: UUID,
    category: MemoryCategory,
    local_date: date,
    title: str,
    provider_id: str | None = None,
    access: TandemAccess = Depends(require_tandem_member),
    db: Session = Depends(get_db),
) -> list[DuplicateMemoryResponse]:
    """Return only likely duplicates within the authorized destination Tandem."""
    statement = select(Memory).where(
        Memory.tandem_id == access.tandem.id,
        Memory.deleted_at.is_(None),
        Memory.category == category.value,
        Memory.local_date.between(local_date - timedelta(days=1), local_date + timedelta(days=1)),
    )
    if category is MemoryCategory.MOVIE and provider_id:
        statement = statement.where(
            Memory.memory_metadata["provider_movie_id"].astext == provider_id
        )
    else:
        normalized = " ".join(title.casefold().split())
        statement = statement.where(func.lower(Memory.title) == normalized)
    return [
        DuplicateMemoryResponse(
            id=item.id,
            title=item.title,
            local_date=item.local_date,
            category=item.category,
            tandem_id=item.tandem_id,
        )
        for item in db.scalars(statement.order_by(Memory.local_date.desc(), Memory.id)).all()
    ]


@router.get("/deleted", response_model=MemoryListResponse)
def list_deleted_memories(
    request: Request,
    tandem_id: UUID,
    access: TandemAccess = Depends(require_tandem_member),
    db: Session = Depends(get_db),
) -> MemoryListResponse:
    statement = (
        select(Memory)
        .where(
            Memory.tandem_id == access.tandem.id,
            Memory.deleted_at.is_not(None),
            Memory.deletion_expires_at > datetime.now(UTC),
        )
        .order_by(Memory.deleted_at.desc(), Memory.id.desc())
    )
    items = db.scalars(statement.limit(100)).all()
    return MemoryListResponse(
        items=_responses(
            db, items, getattr(request.app.state, "object_storage", None), access.member.user_id
        ),
        offset=0,
        limit=100,
        next_offset=None,
    )


@router.get("/{memory_id}", response_model=MemoryResponse)
def get_memory(
    request: Request,
    memory_id: UUID,
    access: TandemAccess = Depends(require_tandem_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemoryResponse:
    return _responses(
        db,
        [_one(db, access.tandem.id, memory_id)],
        getattr(request.app.state, "object_storage", None),
        current_user.id,
    )[0]


@router.patch("/{memory_id}", response_model=MemoryResponse)
def update_memory(
    request: Request,
    memory_id: UUID,
    payload: MemoryPatch,
    access: TandemAccess = Depends(require_tandem_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemoryResponse:
    memory = _one(db, access.tandem.id, memory_id)
    if access.member.role != "OWNER" and memory.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="You can only edit memories you created")
    changes = payload.model_dump(exclude_unset=True)
    if payload.category is not None and payload.category.value != memory.category:
        raise HTTPException(status_code=422, detail="memory category cannot be changed")
    participant_ids = changes.pop("participant_ids", None)
    tags = changes.pop("tags", None)
    changes.pop("expected_version", None)
    merged = {
        "category": memory.category,
        "title": memory.title,
        "local_date": memory.local_date,
        "end_date": memory.end_date,
        "occurred_at": memory.occurred_at,
        "timezone": memory.timezone,
        "notes": memory.notes,
        "rating": memory.rating,
        "metadata": memory.memory_metadata,
        "nostalgia_eligible": memory.nostalgia_eligible,
        "participant_ids": [],
        "tags": [],
        **changes,
    }
    if participant_ids is None:
        participant_ids = [
            row.user_id
            for row in db.scalars(
                select(MemoryParticipant).where(MemoryParticipant.memory_id == memory.id)
            ).all()
        ]
    if tags is None:
        tags = list(
            db.scalars(
                select(Tag.name)
                .join(MemoryTag, MemoryTag.tag_id == Tag.id)
                .where(MemoryTag.memory_id == memory.id)
            ).all()
        )
    merged["participant_ids"] = participant_ids
    merged["tags"] = tags
    validated = MemoryWrite.model_validate(merged)
    participants = _validate_participants(db, access.tandem.id, validated.participant_ids)
    old_date = memory.local_date
    old_participants = set(participant_ids)
    old_tags = set(tags)
    result = db.execute(
        update(Memory)
        .where(
            Memory.id == memory.id,
            Memory.tandem_id == access.tandem.id,
            Memory.version == payload.expected_version,
        )
        .values(
            category=validated.category.value,
            title=validated.title,
            local_date=validated.local_date,
            end_date=validated.end_date,
            occurred_at=validated.occurred_at,
            timezone=validated.timezone,
            notes=validated.notes,
            rating=validated.rating,
            memory_metadata=validated.metadata,
            nostalgia_eligible=validated.nostalgia_eligible,
            version=Memory.version + 1,
        )
        .returning(Memory.id)
    )
    if result.scalar_one_or_none() is None:
        current = db.scalar(select(Memory.version).where(Memory.id == memory.id))
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"message": "Memory changed since it was loaded", "current_version": current},
        )
    db.execute(delete(MemoryParticipant).where(MemoryParticipant.memory_id == memory.id))
    db.add_all(
        [
            MemoryParticipant(
                memory_id=memory.id,
                tandem_id=access.tandem.id,
                user_id=user_id,
                participant_display_name=db.scalar(
                    select(User.display_name).where(User.id == user_id)
                ),
            )
            for user_id in participants
        ]
    )
    db.execute(delete(MemoryTag).where(MemoryTag.memory_id == memory.id))
    for tag_id in _tag_ids(db, access.tandem.id, validated.tags):
        db.add(MemoryTag(memory_id=memory.id, tag_id=tag_id, tandem_id=access.tandem.id))
    changed_fields = [field for field in changes if field not in {"category"}]
    _event(
        db,
        tandem_id=access.tandem.id,
        actor_user_id=current_user.id,
        entity_id=memory.id,
        event_type="MemoryUpdated",
        payload={"changed_fields": changed_fields},
    )
    if old_date != validated.local_date:
        _event(
            db,
            tandem_id=access.tandem.id,
            actor_user_id=current_user.id,
            entity_id=memory.id,
            event_type="MemoryDateChanged",
        )
    for user_id in set(participants) - old_participants:
        _event(
            db,
            tandem_id=access.tandem.id,
            actor_user_id=current_user.id,
            entity_id=memory.id,
            event_type="ParticipantAdded",
            payload={"user_id": str(user_id)},
        )
    for user_id in old_participants - set(participants):
        _event(
            db,
            tandem_id=access.tandem.id,
            actor_user_id=current_user.id,
            entity_id=memory.id,
            event_type="ParticipantRemoved",
            payload={"user_id": str(user_id)},
        )
    for tag in set(validated.tags) - old_tags:
        _event(
            db,
            tandem_id=access.tandem.id,
            actor_user_id=current_user.id,
            entity_id=memory.id,
            event_type="TagAdded",
            payload={"tag": tag},
        )
    for tag in old_tags - set(validated.tags):
        _event(
            db,
            tandem_id=access.tandem.id,
            actor_user_id=current_user.id,
            entity_id=memory.id,
            event_type="TagRemoved",
            payload={"tag": tag},
        )
    db.commit()
    set_current_user_id(db, str(current_user.id))
    db.refresh(memory)
    updated = _one(db, access.tandem.id, memory.id)
    return _responses(
        db, [updated], getattr(request.app.state, "object_storage", None), current_user.id
    )[0]


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    request: Request,
    memory_id: UUID,
    expected_version: int | None = Query(default=None, ge=1),
    access: TandemAccess = Depends(require_tandem_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    memory = _one(db, access.tandem.id, memory_id)
    if access.member.role != "OWNER" and memory.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="You can only delete memories you created")
    if expected_version is not None and memory.version != expected_version:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Memory changed since it was loaded",
                "current_version": memory.version,
            },
        )
    statement = (
        update(Memory)
        .where(Memory.id == memory.id, Memory.tandem_id == access.tandem.id)
        .values(
            deleted_at=datetime.now(UTC),
            deletion_expires_at=datetime.now(UTC) + timedelta(days=30),
            version=Memory.version + 1,
        )
    )
    if expected_version is not None:
        statement = statement.where(Memory.version == expected_version)
    deleted = db.execute(statement).rowcount
    if not deleted:
        current = db.scalar(select(Memory.version).where(Memory.id == memory.id))
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail={"message": "Memory changed since it was loaded", "current_version": current},
        )
    _event(
        db,
        tandem_id=access.tandem.id,
        actor_user_id=current_user.id,
        entity_id=memory.id,
        event_type="MemoryDeleted",
    )
    db.commit()


@router.post("/{memory_id}/restore", response_model=MemoryResponse)
def restore_memory(
    request: Request,
    memory_id: UUID,
    access: TandemAccess = Depends(require_tandem_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemoryResponse:
    memory = _one(db, access.tandem.id, memory_id, include_deleted=True)
    if memory.deleted_at is None:
        return _responses(
            db, [memory], getattr(request.app.state, "object_storage", None), current_user.id
        )[0]
    if memory.deletion_expires_at and memory.deletion_expires_at <= datetime.now(UTC):
        raise HTTPException(status_code=410, detail="Memory has passed its restore window")
    if access.member.role != "OWNER" and memory.created_by != current_user.id:
        raise HTTPException(
            status_code=403, detail="Only the creator or a Tandem owner can restore this memory"
        )
    memory.deleted_at = None
    memory.deletion_expires_at = None
    memory.version += 1
    db.commit()
    db.refresh(memory)
    return _responses(
        db, [memory], getattr(request.app.state, "object_storage", None), current_user.id
    )[0]


@router.delete("/{memory_id}/permanent", status_code=status.HTTP_204_NO_CONTENT)
def permanently_delete_memory(
    request: Request,
    memory_id: UUID,
    access: TandemAccess = Depends(require_tandem_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    memory = _one(db, access.tandem.id, memory_id, include_deleted=True)
    if memory.deleted_at is None:
        raise HTTPException(status_code=409, detail="Memory is not in Recently Deleted")
    if access.member.role != "OWNER" and memory.created_by != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the creator or a Tandem owner can permanently delete this memory",
        )
    media = db.scalars(select(MemoryMedia).where(MemoryMedia.memory_id == memory.id)).all()
    storage: ObjectStorage | None = getattr(request.app.state, "object_storage", None)
    if media and storage is None:
        raise HTTPException(status_code=503, detail="Private media storage is not configured")
    if storage:
        for item in media:
            storage.delete_object(item.object_key)
    db.delete(memory)
    db.commit()


@router.put("/{memory_id}/reflections/me", response_model=ReflectionResponse)
def save_my_reflection(
    memory_id: UUID,
    payload: ReflectionWrite,
    access: TandemAccess = Depends(require_tandem_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReflectionResponse:
    memory = _one(db, access.tandem.id, memory_id)
    reflection = db.scalar(
        select(MemoryReflection).where(
            MemoryReflection.memory_id == memory.id, MemoryReflection.user_id == current_user.id
        )
    )
    if reflection is None:
        reflection = MemoryReflection(
            memory_id=memory.id, tandem_id=memory.tandem_id, user_id=current_user.id
        )
        db.add(reflection)
    reflection.rating = payload.rating
    reflection.note = payload.note
    reflection.reaction = payload.reaction
    db.commit()
    db.refresh(reflection)
    return ReflectionResponse(
        id=reflection.id,
        user_id=current_user.id,
        display_name=current_user.display_name,
        rating=reflection.rating,
        note=reflection.note,
        reaction=reflection.reaction,
        created_at=reflection.created_at,
        updated_at=reflection.updated_at,
    )


@router.delete("/{memory_id}/reflections/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_my_reflection(
    memory_id: UUID,
    access: TandemAccess = Depends(require_tandem_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    memory = _one(db, access.tandem.id, memory_id)
    db.execute(
        delete(MemoryReflection).where(
            MemoryReflection.memory_id == memory.id, MemoryReflection.user_id == current_user.id
        )
    )
    db.commit()
