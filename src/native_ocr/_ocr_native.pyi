def get_supported_langs() -> list[str]:
    """Return BCP-47 language codes supported by the Vision OCR engine.

    Queries VNRecognizeTextRequest.supportedRecognitionLanguages at the
    ``accurate`` recognition level. The returned list typically includes
    codes like ``"en-US"``, ``"zh-Hans"``, ``"ja-JP"``, etc.

    Returns:
        A list of BCP-47 / ISO 639-1 language code strings.

    Raises RuntimeError on Vision failure rather than returning an empty list.
    """
    ...

def detect_bgra8(
    bgra8: bytes,
    width: int,
    height: int,
    roi: tuple[float, float, float, float],
    high_accuracy: bool,
    langs: list[str],
    custom_words: list[str],
) -> list[tuple[str, float, float, float, float]]:
    """Run OCR on a raw BGRA8 pixel buffer.

    The buffer must be tightly packed (no row padding):
    ``len(bgra8) == width * height * 4``.

    Args:
        bgra8: Raw BGRA8 pixel data.
        width: Image width in pixels.
        height: Image height in pixels.
        roi: Region of interest as ``(x, y, width, height)`` in normalised
            ``[0.0, 1.0]`` coordinates, top-left origin.
        high_accuracy: True for accurate mode, False for fast mode.
        langs: BCP-47 language hints (empty list uses system defaults).
        custom_words: Extra vocabulary (only effective in accurate mode).

    Returns:
        A list of ``(text, x, y, width, height)`` tuples. Coordinates are
        normalised ``[0.0, 1.0]``, top-left origin.

    Inputs are validated before native access. Invalid types raise TypeError;
    invalid dimensions/ROI/length or NUL hints raise ValueError; unrepresentable
    sizes raise OverflowError. UTF-8 conversion can raise UnicodeEncodeError.
    Native failures raise RuntimeError; allocation failures raise MemoryError.
    Input buffers and hints are copied before Vision runs without the GIL.
    """
    ...

def detect_image(
    data: bytes,
    roi: tuple[float, float, float, float],
    high_accuracy: bool,
    langs: list[str],
    custom_words: list[str],
) -> tuple[list[tuple[str, float, float, float, float]], int, int]:
    """Run OCR on an encoded image using the system ImageIO decoders.

    Args:
        data: Raw bytes of an encoded image file.
        roi: Region of interest as ``(x, y, width, height)`` in normalised
            ``[0.0, 1.0]`` coordinates, top-left origin.
        high_accuracy: True for accurate mode, False for fast mode.
        langs: BCP-47 language hints (empty list uses system defaults).
        custom_words: Extra vocabulary (only effective in accurate mode).

    Returns:
        A tuple of ``(results, image_width_px, image_height_px)`` where
        results is a list of ``(text, x, y, width, height)`` tuples with
        normalised coordinates.

    Invalid/undecodable image data raises ValueError. Other validation, native
    failure and input snapshot semantics match detect_bgra8. A successfully
    recognised blank image returns ([], width, height).
    """
    ...
