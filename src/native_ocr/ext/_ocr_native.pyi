def get_supported_langs() -> list[str]:
    pass

def detect_bgra8(
    bgra8: bytes,
    width: int,
    height: int,
    roi: tuple[float, float, float, float],
    high_accuracy: bool,
    langs: list[str],
    custom_words: list[str],
) -> list[tuple[str, float, float, float, float]]:
    pass

def detect_image(
    data: bytes,
    roi: tuple[float, float, float, float],
    high_accuracy: bool,
    langs: list[str],
    custom_words: list[str],
) -> list[tuple[str, float, float, float, float]]:
    pass
