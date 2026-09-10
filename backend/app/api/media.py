import logging
import re
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.session import get_db
from app.models import Memory, MemoryMedia, User
from app.schemas.memory import MemoryMediaResponse
from app.services.auth import get_current_user
from app.services.authorization import TandemAccess, require_tandem_member
from app.services.media_processing import InvalidImage, process_image
from app.services.media_storage import ObjectStorage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/tandems/{tandem_id}/memories/{memory_id}/media", tags=["media"])


def _storage(request: Request) -> ObjectStorage:
    storage = getattr(request.app.state, "object_storage", None)
    if storage is None:
        raise HTTPException(status_code=503, detail="Private media storage is not configured")
    return storage


def _memory(db: Session, access: TandemAccess, memory_id: UUID) -> Memory:
    memory = db.scalar(
        select(Memory).where(Memory.id == memory_id, Memory.tandem_id == access.tandem.id)
    )
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")
    return memory


def _safe_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    name = Path(filename).name
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("._")
    return name[:255] or None


def _response(media: MemoryMedia, storage: ObjectStorage | None) -> MemoryMediaResponse:
    url = None
    if storage:
        try:
            url = storage.create_read_url(media.object_key)
        except Exception:
            # A signed-read outage should degrade a thumbnail, not take down Timeline/Today.
            logger.warning("media_read_url_failed")
    return MemoryMediaResponse(
        id=media.id,
        memory_id=media.memory_id,
        content_type=media.content_type,
        byte_size=media.byte_size,
        width=media.width,
        height=media.height,
        created_at=media.created_at,
        display_order=media.display_order,
        url=url,
    )


@router.get("", response_model=list[MemoryMediaResponse])
def list_media(
    request: Request,
    memory_id: UUID,
    access: TandemAccess = Depends(require_tandem_member),
    db: Session = Depends(get_db),
) -> list[MemoryMediaResponse]:
    _memory(db, access, memory_id)
    storage = getattr(request.app.state, "object_storage", None)
    media = db.scalars(
        select(MemoryMedia)
        .where(MemoryMedia.memory_id == memory_id, MemoryMedia.tandem_id == access.tandem.id)
        .order_by(MemoryMedia.display_order, MemoryMedia.created_at, MemoryMedia.id)
    ).all()
    return [_response(item, storage) for item in media]


@router.post("", response_model=list[MemoryMediaResponse], status_code=status.HTTP_201_CREATED)
async def upload_media(
    request: Request,
    memory_id: UUID,
    files: list[UploadFile] = File(...),
    access: TandemAccess = Depends(require_tandem_member),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[MemoryMediaResponse]:
    settings: Settings = request.app.state.settings
    storage = _storage(request)
    _memory(db, access, memory_id)
    if not files or len(files) > settings.media_max_count:
        raise HTTPException(
            status_code=422, detail=f"Choose between 1 and {settings.media_max_count} photos"
        )
    existing_count = (
        db.scalar(
            select(func.count())
            .select_from(MemoryMedia)
            .where(MemoryMedia.memory_id == memory_id, MemoryMedia.tandem_id == access.tandem.id)
        )
        or 0
    )
    if existing_count + len(files) > settings.media_max_count:
        raise HTTPException(
            status_code=422, detail=f"A memory can have at most {settings.media_max_count} photos"
        )

    created: list[MemoryMedia] = []
    object_keys: list[str] = []
    try:
        next_order = existing_count
        for upload in files:
            raw = await upload.read(settings.media_max_bytes + 1)
            if len(raw) > settings.media_max_bytes:
                raise HTTPException(status_code=413, detail="Each photo must be 10 MB or smaller")
            try:
                processed, width, height = process_image(
                    raw, upload.content_type, settings.media_max_bytes, settings.media_max_dimension
                )
            except InvalidImage as exc:
                raise HTTPException(status_code=415, detail=str(exc)) from None
            object_key = f"media/{uuid4().hex}.webp"
            storage.put_object(object_key, processed, "image/webp")
            object_keys.append(object_key)
            media = MemoryMedia(
                memory_id=memory_id,
                tandem_id=access.tandem.id,
                object_key=object_key,
                content_type="image/webp",
                byte_size=len(processed),
                width=width,
                height=height,
                original_filename=_safe_filename(upload.filename),
                created_by=current_user.id,
                display_order=next_order,
            )
            next_order += 1
            db.add(media)
            created.append(media)
        # Flush while the transaction-local request identity is still set. A
        # post-commit refresh would run without app.current_user_id() and be
        # hidden by FORCE RLS.
        db.flush()
        db.commit()
        return [_response(media, storage) for media in created]
    except HTTPException:
        db.rollback()
        for object_key in object_keys:
            try:
                storage.delete_object(object_key)
            except Exception:
                logger.error("media_orphan_cleanup_failed")
        raise
    except Exception:
        db.rollback()
        for object_key in object_keys:
            try:
                storage.delete_object(object_key)
            except Exception:
                logger.error("media_orphan_cleanup_failed")
        logger.exception("media_upload_failed")
        raise HTTPException(
            status_code=503, detail="Photo upload failed; no photo was saved"
        ) from None


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_media(
    request: Request,
    memory_id: UUID,
    media_id: UUID,
    access: TandemAccess = Depends(require_tandem_member),
    db: Session = Depends(get_db),
) -> None:
    storage = _storage(request)
    media = db.scalar(
        select(MemoryMedia).where(
            MemoryMedia.id == media_id,
            MemoryMedia.memory_id == memory_id,
            MemoryMedia.tandem_id == access.tandem.id,
        )
    )
    if media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    try:
        storage.delete_object(media.object_key)
    except Exception:
        logger.error("media_delete_failed")
        raise HTTPException(
            status_code=503, detail="Photo storage is temporarily unavailable"
        ) from None
    db.delete(media)
    db.commit()
