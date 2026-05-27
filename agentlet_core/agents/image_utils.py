# Copyright 2026 Emin Askerov
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Utilities for loading images and building multimodal content blocks."""

import base64
import re
import urllib.request
from pathlib import Path
from typing import Union
from urllib.parse import urlparse

from strands.types.content import ContentBlock
from strands.types.media import ImageFormat


# Maps file extensions to Strands ImageFormat literals
_EXT_TO_FORMAT: dict[str, ImageFormat] = {
    ".jpg": "jpeg",
    ".jpeg": "jpeg",
    ".png": "png",
    ".gif": "gif",
    ".webp": "webp",
}

# Maps MIME subtype to Strands ImageFormat literals
_MIME_TO_FORMAT: dict[str, ImageFormat] = {
    "jpg": "jpeg",
    "jpeg": "jpeg",
    "png": "png",
    "gif": "gif",
    "webp": "webp",
}

SUPPORTED_EXTENSIONS = list(_EXT_TO_FORMAT.keys())


def _detect_format_from_path(path: str) -> ImageFormat:
    """Detect image format from file extension.

    Args:
        path: File path or URL path segment

    Returns:
        Strands ImageFormat literal

    Raises:
        ValueError: If the extension is not a supported image format
    """
    ext = Path(path).suffix.lower()
    fmt = _EXT_TO_FORMAT.get(ext)
    if fmt is None:
        raise ValueError(
            f"Unsupported image extension '{ext}'. Supported: {SUPPORTED_EXTENSIONS}"
        )
    return fmt


def _load_from_data_url(source: str) -> tuple[bytes, ImageFormat]:
    """Parse a base64 data URL and return raw bytes + format.

    Expected format: ``data:image/<subtype>;base64,<data>``

    Args:
        source: Data URL string

    Returns:
        Tuple of (raw bytes, ImageFormat)

    Raises:
        ValueError: If the data URL is malformed or the MIME type is unsupported
    """
    match = re.match(r"data:image/([^;]+);base64,(.+)", source, re.DOTALL)
    if not match:
        raise ValueError(
            f"Invalid image data URL. Expected 'data:image/<type>;base64,<data>', "
            f"got: {source[:60]}..."
        )
    mime_subtype = match.group(1).lower()
    fmt = _MIME_TO_FORMAT.get(mime_subtype)
    if fmt is None:
        raise ValueError(
            f"Unsupported image MIME type 'image/{mime_subtype}'. "
            f"Supported: {list(_MIME_TO_FORMAT.keys())}"
        )
    raw_bytes = base64.b64decode(match.group(2))
    return raw_bytes, fmt


def _load_from_url(source: str) -> tuple[bytes, ImageFormat]:
    """Download an image from an HTTP/HTTPS URL.

    Format is inferred from the URL path extension.

    Args:
        source: HTTP or HTTPS URL string

    Returns:
        Tuple of (raw bytes, ImageFormat)

    Raises:
        ValueError: If the URL path has an unsupported extension
        urllib.error.URLError: On network errors
    """
    parsed = urlparse(source)
    fmt = _detect_format_from_path(parsed.path)
    with urllib.request.urlopen(source) as response:  # noqa: S310  # nosec B310
        return response.read(), fmt


def _load_from_file(source: str) -> tuple[bytes, ImageFormat]:
    """Load an image from a local file path.

    Args:
        source: Absolute or relative file path

    Returns:
        Tuple of (raw bytes, ImageFormat)

    Raises:
        FileNotFoundError: If the file does not exist
        ValueError: If the file extension is unsupported
    """
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Image file not found: {source}")
    fmt = _detect_format_from_path(str(path))
    return path.read_bytes(), fmt


def load_image(source: str) -> tuple[bytes, ImageFormat]:
    """Load image bytes and detect format from any supported source.

    Supports:
    - Local file paths (``/path/to/photo.jpg``, ``./relative.png``)
    - HTTP/HTTPS URLs (``https://example.com/image.png``)
    - Base64 data URLs (``data:image/jpeg;base64,...``)

    Args:
        source: Image source — file path, URL, or data URL

    Returns:
        Tuple of (raw bytes, ImageFormat)

    Raises:
        FileNotFoundError: If a local file path does not exist
        ValueError: If the format is unsupported or the source is invalid
    """
    if source.startswith("data:"):
        return _load_from_data_url(source)

    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        return _load_from_url(source)

    return _load_from_file(source)


def build_multimodal_content(
    prompt: str, images: list[str]
) -> Union[str, list[ContentBlock]]:
    """Build a Strands content block list from a text prompt and image sources.

    If no images are provided, returns the prompt string unchanged so the
    single-modality fast path is preserved.

    Args:
        prompt: Text prompt
        images: List of image sources (file paths, HTTP URLs, or data URLs).
                Supported formats: JPEG, PNG, GIF, WebP.

    Returns:
        Plain string when ``images`` is empty; otherwise a list of
        ``ContentBlock`` dicts with a leading text block followed by one
        image block per image.

    Raises:
        FileNotFoundError: If a local image file does not exist
        ValueError: If an image format is unsupported
    """
    if not images:
        return prompt

    content: list[ContentBlock] = [{"text": prompt}]
    for source in images:
        image_bytes, image_format = load_image(source)
        content.append(
            {
                "image": {
                    "format": image_format,
                    "source": {"bytes": image_bytes},
                }
            }
        )
    return content
