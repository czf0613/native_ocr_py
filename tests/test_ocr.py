"""
Tests for native_ocr public API.

The tests cover three functions:
  - get_supported_languages()
  - perform_ocr_on_image()
  - perform_ocr_on_bgra()

The BGRA tests require Pillow to decode the sample PNG into raw pixel data.
They are automatically skipped when Pillow is not installed.

All tests are skipped when the C extension has not been built yet.
"""
import asyncio
import pathlib
import pytest

native_ocr = pytest.importorskip(
    "native_ocr",
    reason="native_ocr C extension is not built — run: uv run setup.py build_ext --inplace",
)

from native_ocr import (  # noqa: E402
    BoundingBox,
    OcrResult,
    get_supported_languages,
    perform_ocr_on_bgra,
    perform_ocr_on_image,
)


# ---------------------------------------------------------------------------
# get_supported_languages
# ---------------------------------------------------------------------------

def test_supported_languages_returns_list() -> None:
    langs = get_supported_languages()
    assert isinstance(langs, list)
    assert len(langs) > 0, "Expected at least one supported language"
    for lang in langs:
        assert isinstance(lang, str)
        assert len(lang) > 0


def test_supported_languages_cached() -> None:
    """Result must be the same object on repeated calls (cache is active)."""
    assert get_supported_languages() is get_supported_languages()


def test_supported_languages_contains_english() -> None:
    langs = get_supported_languages()
    assert any("en" in lang for lang in langs), f"Expected an English entry, got: {langs}"


def test_supported_languages_contains_chinese() -> None:
    langs = get_supported_languages()
    assert any("zh" in lang for lang in langs), f"Expected a Chinese entry, got: {langs}"


# ---------------------------------------------------------------------------
# perform_ocr_on_image
# ---------------------------------------------------------------------------

def test_ocr_image_returns_list(sample_image_bytes: bytes) -> None:
    results = asyncio.run(perform_ocr_on_image(sample_image_bytes, normalized=True))
    assert isinstance(results, list)
    assert len(results) > 0, "Expected at least one OCR result from the sample image"


def test_ocr_image_result_types(sample_image_bytes: bytes) -> None:
    results = asyncio.run(perform_ocr_on_image(sample_image_bytes, normalized=True))
    for r in results:
        assert isinstance(r, OcrResult)
        assert isinstance(r.content, str)
        assert len(r.content) > 0, "OcrResult.content must never be empty"
        assert isinstance(r.position, BoundingBox)


def test_ocr_image_normalised_bounding_boxes(sample_image_bytes: bytes) -> None:
    results = asyncio.run(perform_ocr_on_image(sample_image_bytes, normalized=True))
    for r in results:
        pos = r.position
        assert 0.0 <= pos.x <= 1.0,     f"x out of range: {pos.x}"
        assert 0.0 <= pos.y <= 1.0,     f"y out of range: {pos.y}"
        assert 0.0 < pos.width  <= 1.0, f"width out of range: {pos.width}"
        assert 0.0 < pos.height <= 1.0, f"height out of range: {pos.height}"


def test_ocr_image_pixel_bounding_boxes(sample_image_bytes: bytes) -> None:
    """With normalized=False, at least one coordinate must exceed 1.0."""
    results = asyncio.run(perform_ocr_on_image(sample_image_bytes, normalized=False))
    assert len(results) > 0
    max_coord = max(
        max(r.position.x, r.position.y, r.position.width, r.position.height)
        for r in results
    )
    assert max_coord > 1.0, "Expected pixel coordinates to exceed 1.0"


def test_ocr_image_contains_chinese_text(sample_image_bytes: bytes) -> None:
    """Sample image is a Chinese game screenshot — expect Chinese characters."""
    results = asyncio.run(
        perform_ocr_on_image(sample_image_bytes, normalized=True, languages=["zh-Hans"])
    )
    combined = "".join(r.content for r in results)
    has_chinese = any("\u4e00" <= ch <= "\u9fff" for ch in combined)
    assert has_chinese, f"Expected Chinese characters, got: {combined!r}"


def test_ocr_image_known_text(sample_image_bytes: bytes) -> None:
    """The sample image contains '恭喜获得' — verify it is recognised."""
    results = asyncio.run(
        perform_ocr_on_image(sample_image_bytes, normalized=True, languages=["zh-Hans"])
    )
    combined = "".join(r.content for r in results)
    assert "恭喜获得" in combined, f"Expected '恭喜获得' in OCR output, got: {combined!r}"


def test_ocr_image_with_roi(sample_image_bytes: bytes) -> None:
    """ROI covering roughly the centre dialog must still return results."""
    roi = BoundingBox(x=0.15, y=0.1, width=0.7, height=0.6)
    results = asyncio.run(
        perform_ocr_on_image(sample_image_bytes, normalized=True, roi=roi)
    )
    assert isinstance(results, list)
    assert len(results) > 0


def test_ocr_image_low_accuracy(sample_image_bytes: bytes) -> None:
    results = asyncio.run(
        perform_ocr_on_image(sample_image_bytes, normalized=True, high_accuracy=False)
    )
    assert isinstance(results, list)


def test_ocr_image_custom_words(sample_image_bytes: bytes) -> None:
    """Passing custom_words must not raise and must still return results."""
    results = asyncio.run(
        perform_ocr_on_image(
            sample_image_bytes,
            normalized=True,
            languages=["zh-Hans"],
            custom_words=["宝石计划", "灵台道人"],
        )
    )
    assert isinstance(results, list)
    assert len(results) > 0


# ---------------------------------------------------------------------------
# perform_ocr_on_bgra  (requires Pillow)
# ---------------------------------------------------------------------------

PIL = pytest.importorskip("PIL", reason="Pillow is required for BGRA tests")


def _png_to_bgra(path: pathlib.Path) -> tuple[bytes, int, int]:
    """Return (bgra_bytes, width, height) for a PNG file."""
    from PIL import Image

    img = Image.open(path).convert("RGBA")
    width, height = img.size
    r, g, b, a = img.split()
    bgra_img = Image.merge("RGBA", (b, g, r, a))
    return bgra_img.tobytes(), width, height


def test_ocr_bgra_returns_list(sample_image_path: pathlib.Path) -> None:
    bgra, width, height = _png_to_bgra(sample_image_path)
    results = asyncio.run(perform_ocr_on_bgra(bgra, width, height, normalized=True))
    assert isinstance(results, list)
    assert len(results) > 0


def test_ocr_bgra_matches_image_results(sample_image_path: pathlib.Path) -> None:
    """BGRA and encoded-image paths should recognise the same text."""
    bgra, width, height = _png_to_bgra(sample_image_path)
    bgra_results = asyncio.run(
        perform_ocr_on_bgra(bgra, width, height, normalized=True, languages=["zh-Hans"])
    )
    img_results = asyncio.run(
        perform_ocr_on_image(
            sample_image_path.read_bytes(), normalized=True, languages=["zh-Hans"]
        )
    )
    bgra_text = "".join(r.content for r in bgra_results)
    img_text  = "".join(r.content for r in img_results)
    # Both should contain Chinese characters; exact match not required
    assert "恭喜获得" in bgra_text, f"BGRA path missing expected text, got: {bgra_text!r}"
    assert "恭喜获得" in img_text,  f"Image path missing expected text, got: {img_text!r}"


def test_ocr_bgra_normalised_bounding_boxes(sample_image_path: pathlib.Path) -> None:
    bgra, width, height = _png_to_bgra(sample_image_path)
    results = asyncio.run(perform_ocr_on_bgra(bgra, width, height, normalized=True))
    for r in results:
        pos = r.position
        assert 0.0 <= pos.x <= 1.0
        assert 0.0 <= pos.y <= 1.0
        assert 0.0 < pos.width  <= 1.0
        assert 0.0 < pos.height <= 1.0
