"""Unit tests for agentlet_core.agents.image_utils."""

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agentlet_core.agents.image_utils import (
    build_multimodal_content,
    load_image,
    _detect_format_from_path,
    _load_from_data_url,
)


# ---------------------------------------------------------------------------
# _detect_format_from_path
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path, expected",
    [
        ("photo.jpg", "jpeg"),
        ("photo.jpeg", "jpeg"),
        ("photo.JPG", "jpeg"),
        ("photo.JPEG", "jpeg"),
        ("/abs/path/image.png", "png"),
        ("anim.gif", "gif"),
        ("icon.webp", "webp"),
        ("./relative/image.PNG", "png"),
    ],
)
def test_detect_format_from_path(path: str, expected: str) -> None:
    assert _detect_format_from_path(path) == expected


def test_detect_format_from_path_unsupported() -> None:
    with pytest.raises(ValueError, match="Unsupported image extension"):
        _detect_format_from_path("document.pdf")


def test_detect_format_from_path_no_extension() -> None:
    with pytest.raises(ValueError, match="Unsupported image extension"):
        _detect_format_from_path("image_without_ext")


# ---------------------------------------------------------------------------
# _load_from_data_url
# ---------------------------------------------------------------------------


def test_load_from_data_url_jpeg() -> None:
    raw = b"\xff\xd8\xff\xe0fake_jpeg_bytes"
    encoded = base64.b64encode(raw).decode()
    data_url = f"data:image/jpeg;base64,{encoded}"

    result_bytes, result_fmt = _load_from_data_url(data_url)
    assert result_bytes == raw
    assert result_fmt == "jpeg"


def test_load_from_data_url_png() -> None:
    raw = b"\x89PNGfake"
    encoded = base64.b64encode(raw).decode()
    data_url = f"data:image/png;base64,{encoded}"

    result_bytes, result_fmt = _load_from_data_url(data_url)
    assert result_bytes == raw
    assert result_fmt == "png"


def test_load_from_data_url_jpg_alias() -> None:
    """'image/jpg' should map to 'jpeg' format."""
    raw = b"fake"
    encoded = base64.b64encode(raw).decode()
    data_url = f"data:image/jpg;base64,{encoded}"

    result_bytes, result_fmt = _load_from_data_url(data_url)
    assert result_bytes == raw
    assert result_fmt == "jpeg"


def test_load_from_data_url_malformed() -> None:
    with pytest.raises(ValueError, match="Invalid image data URL"):
        _load_from_data_url("data:text/plain;base64,aGVsbG8=")


def test_load_from_data_url_unsupported_mime() -> None:
    raw = b"fake"
    encoded = base64.b64encode(raw).decode()
    with pytest.raises(ValueError, match="Unsupported image MIME type"):
        _load_from_data_url(f"data:image/bmp;base64,{encoded}")


# ---------------------------------------------------------------------------
# load_image — local file
# ---------------------------------------------------------------------------


def test_load_image_local_file(tmp_path: Path) -> None:
    img_file = tmp_path / "test.png"
    raw = b"\x89PNGfake_bytes"
    img_file.write_bytes(raw)

    result_bytes, result_fmt = load_image(str(img_file))
    assert result_bytes == raw
    assert result_fmt == "png"


def test_load_image_local_file_jpeg(tmp_path: Path) -> None:
    img_file = tmp_path / "photo.jpg"
    raw = b"\xff\xd8\xff\xe0fake"
    img_file.write_bytes(raw)

    result_bytes, result_fmt = load_image(str(img_file))
    assert result_bytes == raw
    assert result_fmt == "jpeg"


def test_load_image_file_not_found() -> None:
    with pytest.raises(FileNotFoundError, match="Image file not found"):
        load_image("/nonexistent/path/image.png")


def test_load_image_unsupported_extension(tmp_path: Path) -> None:
    bad_file = tmp_path / "document.bmp"
    bad_file.write_bytes(b"fake")

    with pytest.raises(ValueError, match="Unsupported image extension"):
        load_image(str(bad_file))


# ---------------------------------------------------------------------------
# load_image — data URL
# ---------------------------------------------------------------------------


def test_load_image_data_url() -> None:
    raw = b"fake_gif_data"
    encoded = base64.b64encode(raw).decode()
    data_url = f"data:image/gif;base64,{encoded}"

    result_bytes, result_fmt = load_image(data_url)
    assert result_bytes == raw
    assert result_fmt == "gif"


# ---------------------------------------------------------------------------
# load_image — HTTP URL
# ---------------------------------------------------------------------------


def test_load_image_http_url() -> None:
    raw = b"\x89PNGfake_png"
    mock_response = MagicMock()
    mock_response.read.return_value = raw
    mock_response.__enter__ = lambda s: s
    mock_response.__exit__ = MagicMock(return_value=False)

    with patch("urllib.request.urlopen", return_value=mock_response):
        result_bytes, result_fmt = load_image("https://example.com/photo.png")

    assert result_bytes == raw
    assert result_fmt == "png"


def test_load_image_http_url_unsupported_extension() -> None:
    with pytest.raises(ValueError, match="Unsupported image extension"):
        load_image("https://example.com/document.pdf")


# ---------------------------------------------------------------------------
# build_multimodal_content
# ---------------------------------------------------------------------------


def test_build_multimodal_content_no_images() -> None:
    """Without images the prompt is returned as-is (fast path)."""
    result = build_multimodal_content("Hello world", [])
    assert result == "Hello world"


def test_build_multimodal_content_with_image(tmp_path: Path) -> None:
    img_file = tmp_path / "outfit.jpg"
    raw = b"\xff\xd8\xff\xe0fake_jpeg"
    img_file.write_bytes(raw)

    result = build_multimodal_content("Analyze this outfit", [str(img_file)])

    assert isinstance(result, list)
    assert len(result) == 2

    text_block, image_block = result
    assert text_block == {"text": "Analyze this outfit"}
    assert "image" in image_block
    assert image_block["image"]["format"] == "jpeg"
    assert image_block["image"]["source"]["bytes"] == raw


def test_build_multimodal_content_multiple_images(tmp_path: Path) -> None:
    files = []
    for name in ("a.png", "b.webp"):
        f = tmp_path / name
        f.write_bytes(b"fake")
        files.append(str(f))

    result = build_multimodal_content("Compare these", files)

    assert isinstance(result, list)
    assert len(result) == 3  # 1 text + 2 images
    assert result[0] == {"text": "Compare these"}
    assert result[1]["image"]["format"] == "png"
    assert result[2]["image"]["format"] == "webp"


def test_build_multimodal_content_with_data_url() -> None:
    raw = b"fake_gif"
    encoded = base64.b64encode(raw).decode()
    data_url = f"data:image/gif;base64,{encoded}"

    result = build_multimodal_content("What is this?", [data_url])

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[1]["image"]["format"] == "gif"
    assert result[1]["image"]["source"]["bytes"] == raw
