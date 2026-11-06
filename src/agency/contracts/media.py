"""The image formats the harness accepts from a sandbox, and the one place that opens them.

Pillow picks a decoder from the content, not from the file name. A `.png` that holds EPS would make it run
Ghostscript on the host. Every image a sandbox wrote is therefore opened here, restricted to a short list of
safe formats.
"""

from __future__ import annotations

import io

from PIL import Image

IMAGE_MEDIA_TYPES: dict[str, str] = {
    "PNG": "image/png",
    "JPEG": "image/jpeg",
    "WEBP": "image/webp",
    "GIF": "image/gif",
}


def open_image(data: bytes) -> Image.Image:
    """Opens `data` only if it is one of `IMAGE_MEDIA_TYPES`; raises `UnidentifiedImageError` otherwise."""
    return Image.open(io.BytesIO(data), formats=list(IMAGE_MEDIA_TYPES))


def media_type(image: Image.Image) -> str:
    """The media type of an image opened with `open_image`, taken from its content."""
    if image.format not in IMAGE_MEDIA_TYPES:
        raise ValueError(f"unsupported image format: {image.format}")
    return IMAGE_MEDIA_TYPES[image.format]
