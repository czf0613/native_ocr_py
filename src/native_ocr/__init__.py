import asyncio
from functools import cache
from ._ocr_native import (
    detect_bgra8 as _detect_bgra8,
    detect_image as _detect_image,
    get_supported_langs,
)
from .types import BoundingBox, OcrResult

__all__ = [
    "BoundingBox",
    "OcrResult",
    "get_supported_languages",
    "perform_ocr_on_bgra",
    "perform_ocr_on_image",
]


@cache
def get_supported_languages() -> list[str]:
    """Return BCP-47 language codes supported by the Vision OCR engine.

    The result is cached after the first call.
    """
    return get_supported_langs()


def _parse_roi(roi: BoundingBox | None) -> tuple[float, float, float, float]:
    if roi is None:
        return (0.0, 0.0, 1.0, 1.0)
    return (roi["x"], roi["y"], roi["width"], roi["height"])


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
    """Run OCR on a raw BGRA8 pixel buffer.

    The buffer must be tightly packed with no row padding, i.e.
    ``len(bgra) == width * height * 4``.

    Args:
        bgra: Raw pixel data in BGRA8 format (4 bytes per pixel, no padding).
        width: Image width in pixels.
        height: Image height in pixels.
        normalized: When True, result coordinates are normalised to [0.0, 1.0].
            When False, result coordinates are in pixels.
        roi: Region of interest in normalised [0.0, 1.0] coordinates (top-left
            origin). None means the full image.
        high_accuracy: When True, applies additional correction passes.
        languages: BCP-47 language codes to restrict/prioritise recognition.
        custom_words: Supplementary vocabulary. Only effective with high_accuracy.
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
    """Run OCR on an encoded image file loaded into memory.

    Accepts any format supported by the OS's built-in decoders. JPEG and PNG
    are guaranteed; HEIC, TIFF, BMP, and WebP are available on most systems.

    Args:
        data: Raw bytes of an encoded image file.
        normalized: When True, result coordinates are normalised to [0.0, 1.0].
            When False, result coordinates are in pixels.
        roi: Region of interest in normalised [0.0, 1.0] coordinates (top-left
            origin). None means the full image.
        high_accuracy: When True, applies additional correction passes.
        languages: BCP-47 language codes to restrict/prioritise recognition.
        custom_words: Supplementary vocabulary. Only effective with high_accuracy.
    """
    roi_tuple = _parse_roi(roi)
    langs = languages or []
    words = custom_words or []

    raw, img_width, img_height = await asyncio.to_thread(
        _detect_image, data, roi_tuple, high_accuracy, langs, words
    )

    return _build_results(raw, normalized, img_width, img_height)
