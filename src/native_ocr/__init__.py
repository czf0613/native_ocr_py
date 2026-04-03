import asyncio
import struct
from functools import cache, partial

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


def _image_size(data: bytes) -> tuple[int, int]:
    """
    Extract (width, height) from a PNG or JPEG byte stream without
    any third-party dependencies.

    Raises ValueError for unsupported formats or malformed headers.
    """
    # PNG: fixed 8-byte signature, then IHDR chunk at offset 8.
    # Width and height are at offsets 16–20 and 20–24 respectively (big-endian).
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        w, h = struct.unpack(">II", data[16:24])
        return w, h

    # JPEG: scan for an SOF (Start Of Frame) marker.
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 3 < len(data):
            if data[i] != 0xFF:
                break
            marker = data[i + 1]
            # SOF0–SOF15 (excluding DHT/DAC markers 0xC4/0xCC)
            if marker in (
                0xC0,
                0xC1,
                0xC2,
                0xC3,
                0xC5,
                0xC6,
                0xC7,
                0xC9,
                0xCA,
                0xCB,
                0xCD,
                0xCE,
                0xCF,
            ):
                # Segment layout: FF marker | 2B length | 1B precision | 2B height | 2B width
                h, w = struct.unpack(">HH", data[i + 5 : i + 9])
                return w, h
            segment_len = struct.unpack(">H", data[i + 2 : i + 4])[0]
            i += 2 + segment_len

    raise ValueError(
        "Cannot determine image dimensions for normalized=False. "
        "Only PNG and JPEG are supported for pixel-coordinate output. "
        "Pass normalized=True for other formats."
    )


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
        normalized: When ``True``, all coordinates in ``roi`` and in the returned
            ``BoundingBox`` values are normalised to the range ``[0.0, 1.0]``.
            When ``False``, coordinates are in pixels.
            All coordinate values must be ``float`` regardless of this flag.
        roi: Optional region of interest. Only pixels within this bounding box
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

    loop = asyncio.get_running_loop()
    raw: list[tuple[str, float, float, float, float]] = await loop.run_in_executor(
        None,
        partial(
            _detect_bgra8, bgra, width, height, roi_tuple, high_accuracy, langs, words
        ),
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
        normalized: When ``True``, all coordinates in ``roi`` and in the returned
            ``BoundingBox`` values are normalised to the range ``[0.0, 1.0]``.
            When ``False``, coordinates are in pixels.
            All coordinate values must be ``float`` regardless of this flag.
            Note: pixel-coordinate output is only supported for PNG and JPEG.
        roi: Optional region of interest. Only pixels within this bounding box
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

    loop = asyncio.get_running_loop()
    raw: list[tuple[str, float, float, float, float]] = await loop.run_in_executor(
        None,
        partial(_detect_image, data, roi_tuple, high_accuracy, langs, words),
    )

    img_width, img_height = _image_size(data) if not normalized else (1, 1)
    return _build_results(raw, normalized, img_width, img_height)
