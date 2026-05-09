from typing import TypedDict, final

__all__ = ["BoundingBox", "OcrResult"]


@final
class BoundingBox(TypedDict):
    """A rectangle in top-left-origin coordinate space.

    When used as input (``roi`` parameter), coordinates must be normalised to
    ``[0.0, 1.0]``. When used as output (``OcrResult["position"]``), coordinates
    are normalised or in pixels depending on the ``normalized`` flag.
    """

    x: float
    """Horizontal distance from the left edge to the left side of the box."""
    y: float
    """Vertical distance from the top edge to the top side of the box."""
    width: float
    """Width of the box."""
    height: float
    """Height of the box."""


@final
class OcrResult(TypedDict):
    """A single OCR recognition result.

    ``content`` is automatically trimmed of leading/trailing whitespace and
    will never be an empty string.
    """

    content: str
    """The recognised text string."""
    position: BoundingBox
    """Bounding box of the recognised text within the source image."""
