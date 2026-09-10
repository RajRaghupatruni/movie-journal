from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import delete, exists, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session, aliased

from app.core.logging import request_id
from app.db.session import get_db, set_current_user_id
from app.models import (
    ActivityEvent,
    Memory,
    MemoryParticipant,
    MemoryTag,
    Tag,
    TandemMember,
    User,
)
from app.schemas.memory import (
    MemberSummary,
    MemoryCategory,
    MemoryCreate,
    MemoryListResponse,
    MemoryPatch,
    MemoryResponse,
    MemoryWrite,
    normalize_tag,
)
from app.services.auth import get_current_user
from app.services.authorization import TandemAccess, require_tandem_member

router = APIRouter(prefix="/tandems/{tandem_id}/memories", tags=["memories"])


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
        select(MemoryParticipant.memory_id, User.id, User.display_name, User.email, User.avatar_url)
        .join(User, User.id == MemoryParticipant.user_id)
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
    for memory_id, user_id, display_name, email, avatar_url in participant_rows:
        related[memory_id][0].append(
            MemberSummary(
                user_id=user_id,
                display_name=display_name,
                email=email,
                avatar_url=avatar_url,
            )
        )
    for memory_id, name in tag_rows:
        related[memory_id][1].append(name)
    for participants, _ in related.values():
        participants.sort(key=lambda member: (member.display_name.casefold(), member.user_id.hex))
    return related


def _responses(db: Session, memories: list[Memory]) -> list[MemoryResponse]:
    related = _load_related(db, memories)
    return [
        MemoryResponse(
            id=memory.id,
            tandem_id=memory.tandem_id,
            category=memory.category,
            title=memory.title,
            local_date=memory.local_date,
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
        )
        for memory in memories
    ]


def _one(db: Session, tandem_id: UUID, memory_id: UUID) -> Memory:
    memory = db.scalar(select(Memory).where(Memory.id == memory_id, Memory.tandem_id == tandem_id))
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


def _apply_write(memory: Memory, payload: MemoryWrite) -> None:
    memory.category = payload.category.value
    memory.title = payload.title
    memory.local_date = payload.local_date
    memory.occurred_at = payload.occurred_at
    memory.timezone = payload.timezone
    memory.notes = payload.notes
    memory.rating = payload.rating
    memory.memory_metadata = payload.metadata
    memory.nostalgia_eligible = payload.nostalgia_eligible


@router.post("", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
def create_memory(
    payload: MemoryCreate,
    access: TandemAccess = Depends(require_tandem_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemoryResponse:
    participants = _validate_participants(
        db, access.tandem.id, [current_user.id, *payload.participant_ids]
    )
    memory = Memory(
        tandem_id=access.tandem.id,
        created_by=current_user.id,
        category=payload.category.value,
        title=payload.title,
        local_date=payload.local_date,
        occurred_at=payload.occurred_at,
        timezone=payload.timezone,
        notes=payload.notes,
        rating=payload.rating,
        memory_metadata=payload.metadata,
        nostalgia_eligible=payload.nostalgia_eligible,
    )
    db.add(memory)
    db.flush()
    db.add_all(
        [
            MemoryParticipant(memory_id=memory.id, tandem_id=access.tandem.id, user_id=user_id)
            for user_id in participants
        ]
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
    db.commit()
    set_current_user_id(db, str(current_user.id))
    db.refresh(memory)
    return _responses(db, [memory])[0]


@router.get("", response_model=MemoryListResponse)
def list_memories(
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
    statement = select(Memory).where(Memory.tandem_id == access.tandem.id)
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
        items=_responses(db, memories),
        offset=offset,
        limit=limit,
        next_offset=offset + limit if has_more else None,
    )


@router.get("/{memory_id}", response_model=MemoryResponse)
def get_memory(
    memory_id: UUID,
    access: TandemAccess = Depends(require_tandem_member),
    db: Session = Depends(get_db),
) -> MemoryResponse:
    return _responses(db, [_one(db, access.tandem.id, memory_id)])[0]


@router.patch("/{memory_id}", response_model=MemoryResponse)
def update_memory(
    memory_id: UUID,
    payload: MemoryPatch,
    access: TandemAccess = Depends(require_tandem_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MemoryResponse:
    memory = _one(db, access.tandem.id, memory_id)
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
            MemoryParticipant(memory_id=memory.id, tandem_id=access.tandem.id, user_id=user_id)
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
    return _responses(db, [updated])[0]


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_memory(
    memory_id: UUID,
    expected_version: int | None = Query(default=None, ge=1),
    access: TandemAccess = Depends(require_tandem_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    memory = _one(db, access.tandem.id, memory_id)
    statement = delete(Memory).where(Memory.id == memory.id, Memory.tandem_id == access.tandem.id)
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
