from dataclasses import dataclass
from typing import final


@final
@dataclass
class BoundingBox:
    """
    A rectangle in top-left-origin coordinate space.

    Coordinates are either normalised (``[0.0, 1.0]``) or in pixels,
    depending on the ``normalized`` flag passed to the OCR function.
    All fields are ``float`` in both cases.

    Attributes:
        x: Horizontal distance from the left edge to the left side of the box.
        y: Vertical distance from the top edge to the top side of the box.
        width: Width of the box.
        height: Height of the box.
    """

    x: float
    y: float
    width: float
    height: float


@final
@dataclass
class OcrResult:
    """
    A single OCR recognition result.

    ``content`` is automatically trimmed of leading/trailing whitespace and
    will never be an empty string — results with no recognisable text are
    dropped before being returned.

    Attributes:
        content: The recognised text string.
        position: Bounding box of the recognised text within the source image.
    """

    content: str
    position: BoundingBox
