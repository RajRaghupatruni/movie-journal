from io import BytesIO

import pytest
from PIL import Image

from app.services.media_processing import InvalidImage, process_image


def image_bytes(format_name: str = "JPEG", size: tuple[int, int] = (3200, 1800)) -> bytes:
    stream = BytesIO()
    Image.new("RGB", size, "#b86d57").save(stream, format=format_name)
    return stream.getvalue()


def test_valid_photo_is_oriented_resized_and_stripped_to_webp():
    output, width, height = process_image(image_bytes(), "image/jpeg", 10 * 1024 * 1024, 2400)
    assert output[:4] == b"RIFF"
    assert (width, height) == (2400, 1350)
    with Image.open(BytesIO(output)) as image:
        assert image.format == "WEBP"
        assert image.getexif() == {}


@pytest.mark.parametrize(
    "content_type", ["image/svg+xml", "text/html", "application/pdf", "application/octet-stream"]
)
def test_invalid_mime_is_rejected(content_type):
    with pytest.raises(InvalidImage):
        process_image(image_bytes(), content_type, 10 * 1024 * 1024, 2400)


def test_fake_extension_or_malformed_bytes_are_rejected():
    with pytest.raises(InvalidImage):
        process_image(b"not-an-image", "image/jpeg", 10 * 1024 * 1024, 2400)


def test_oversized_input_is_rejected_before_decoding():
    with pytest.raises(InvalidImage):
        process_image(b"x" * (10 * 1024 * 1024 + 1), "image/jpeg", 10 * 1024 * 1024, 2400)
