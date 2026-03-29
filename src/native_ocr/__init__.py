from .types import OcrResult, BoundingBox
from .ext import get_supported_langs
from functools import cache

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
    """
    return get_supported_langs()


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
    return []


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
    return []
