import asyncio
from functools import cache

from .ext import detect_bgra8 as _detect_bgra8
from .ext import detect_image as _detect_image
from .ext import get_supported_langs
from .types import BoundingBox, OcrResult

__all__ = [
    "OcrResult",
    "BoundingBox",
    "get_supported_languages",
    "perform_ocr_on_bgra",
    "perform_ocr_on_image",
]


@cache
def get_supported_languages() -> list[str]:
    """
    Return the list of language codes supported by the underlying OCR engine.

    Each code follows BCP-47 / ISO 639-1 conventions (e.g. ``"en-US"``, ``"zh-Hans"``).
    Pass these codes to the ``languages`` parameter of the OCR functions to restrict
    or prioritise recognition to specific languages.

    The result is cached after the first call.
    """
    return get_supported_langs()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_roi(roi: BoundingBox | None) -> tuple[float, float, float, float]:
    if roi is None:
        return (0.0, 0.0, 1.0, 1.0)
    return (roi.x, roi.y, roi.width, roi.height)


def _build_results(
    raw: list[tuple[str, float, float, float, float]],
    normalized: bool,
    img_width: int,
    img_height: int,
) -> list[OcrResult]:
    results: list[OcrResult] = []
    for text, x, y, w, h in raw:
        text = text.strip()
        if not text:
            continue
        if not normalized:
            x *= img_width
            y *= img_height
            w *= img_width
            h *= img_height
        results.append(
            OcrResult(
                content=text,
                position=BoundingBox(x=x, y=y, width=w, height=h),
            )
        )
    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def perform_ocr_on_bgra(
    bgra: bytes,
    width: int,
    height: int,
    normalized: bool,
    roi: BoundingBox | None = None,
    high_accuracy: bool = True,
    languages: list[str] | None = None,
    custom_words: list[str] | None = None,
) -> list[OcrResult]:
    """
    Run OCR on a raw BGRA8 pixel buffer.

    The buffer must be tightly packed with no row padding, i.e.
    ``len(bgra) == width * height * 4``.

    Args:
        bgra: Raw pixel data in BGRA8 format (4 bytes per pixel, no padding).
        width: Image width in pixels.
        height: Image height in pixels.
        normalized: Controls the coordinate space of the **returned** bounding
            boxes only. When ``True``, result coordinates are normalised to
            ``[0.0, 1.0]``. When ``False``, result coordinates are in pixels.
            Does not affect ``roi``, which is always normalised.
        roi: Optional region of interest in **normalised** ``[0.0, 1.0]``
            coordinates (top-left origin). Only pixels within this rectangle
            are scanned. ``None`` means the full image is scanned.
        high_accuracy: When ``True``, the OCR engine applies additional
            correction passes for higher accuracy at the cost of speed.
            When ``False``, a faster but less accurate scan is performed.
        languages: BCP-47 language codes (from ``get_supported_languages``) that
            hint the engine about which languages to expect. ``None`` or an empty
            list enables automatic language detection.
        custom_words: A supplementary vocabulary for the engine. Providing
            domain-specific or rare words improves recognition of those terms.
            Only effective when ``high_accuracy`` is ``True``.

    Returns:
        A list of ``OcrResult`` objects, each containing the recognised text and
        its bounding box. The list is empty if no text is detected.
    """
    roi_tuple = _parse_roi(roi)
    langs = languages or []
    words = custom_words or []

    raw: list[tuple[str, float, float, float, float]] = await asyncio.to_thread(
        _detect_bgra8, bgra, width, height, roi_tuple, high_accuracy, langs, words
    )

    return _build_results(raw, normalized, width, height)


async def perform_ocr_on_image(
    data: bytes,
    normalized: bool,
    roi: BoundingBox | None = None,
    high_accuracy: bool = True,
    languages: list[str] | None = None,
    custom_words: list[str] | None = None,
) -> list[OcrResult]:
    """
    Run OCR on an encoded image file loaded into memory.

    Accepts any image format supported by the OS's built-in decoders.
    JPEG and PNG are guaranteed to be supported; HEIC, TIFF, BMP, and WebP
    are available on most systems.

    Args:
        data: Raw bytes of an encoded image file (e.g. the contents of a
            ``.jpg`` or ``.png`` file).
        normalized: Controls the coordinate space of the **returned** bounding
            boxes only. When ``True``, result coordinates are normalised to
            ``[0.0, 1.0]``. When ``False``, result coordinates are in pixels.
            Does not affect ``roi``, which is always normalised.
        roi: Optional region of interest in **normalised** ``[0.0, 1.0]``
            coordinates (top-left origin). Only pixels within this rectangle
            are scanned. ``None`` means the full image is scanned.
        high_accuracy: When ``True``, the OCR engine applies additional
            correction passes for higher accuracy at the cost of speed.
        languages: BCP-47 language codes (from ``get_supported_languages``) that
            hint the engine about which languages to expect. ``None`` or an empty
            list enables automatic language detection.
        custom_words: A supplementary vocabulary for the engine. Only effective
            when ``high_accuracy`` is ``True``.

    Returns:
        A list of ``OcrResult`` objects, each containing the recognised text and
        its bounding box. The list is empty if no text is detected.
    """
    roi_tuple = _parse_roi(roi)
    langs = languages or []
    words = custom_words or []

    raw, img_width, img_height = await asyncio.to_thread(
        _detect_image, data, roi_tuple, high_accuracy, langs, words
    )

    return _build_results(raw, normalized, img_width, img_height)
