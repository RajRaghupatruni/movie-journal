"""Bounded image validation and privacy-preserving normalization."""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_WEBP_QUALITY = 85


class InvalidImage(Exception):
    pass


def process_image(
    raw: bytes, declared_content_type: str | None, max_bytes: int, max_dimension: int
) -> tuple[bytes, int, int]:
    if declared_content_type not in ALLOWED_CONTENT_TYPES:
        raise InvalidImage("Only JPEG, PNG, and WebP images are supported")
    if len(raw) > max_bytes:
        raise InvalidImage("Image is larger than the 10 MB upload limit")
    try:
        with Image.open(BytesIO(raw)) as source:
            source.verify()
        with Image.open(BytesIO(raw)) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
            image.thumbnail((max_dimension, max_dimension), Image.Resampling.LANCZOS)
            width, height = image.size
            output = BytesIO()
            image.save(output, format="WEBP", quality=MAX_WEBP_QUALITY, method=6)
            return output.getvalue(), width, height
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise InvalidImage("The upload is not a readable image") from exc
