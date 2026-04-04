# native_ocr_py

A Python library that exposes the **macOS Vision OCR engine** via a Python C extension — no third-party OCR service, no bundled models, no network calls. Uses the OS-native framework directly for fast, on-device text recognition.

> **Platform support:** macOS only for now. Windows support is planned.

---

## Requirements

- macOS 13 or later (for Vision framework revision 3)
- Python 3.11 or later

---

## Installation

Install from PyPI:

```bash
pip install native_ocr_py
```

Because the package includes a compiled C extension, a pre-built wheel for your macOS architecture (arm64 / x86_64) must be available on PyPI. If no matching wheel is found, pip will attempt to build from source, which requires Xcode Command Line Tools:

```bash
xcode-select --install
```

---

## Quick start

```python
import asyncio
import native_ocr

async def main():
    with open("screenshot.png", "rb") as f:
        data = f.read()

    results = await native_ocr.perform_ocr_on_image(data, normalized=True)

    for r in results:
        print(r.content, r.position)

asyncio.run(main())
```

---

## API

### `get_supported_languages() -> list[str]`

Returns BCP-47 language codes supported by the Vision OCR engine (e.g. `"en-US"`, `"zh-Hans"`). The result is cached after the first call.

---

### `await perform_ocr_on_image(data, normalized, *, roi, high_accuracy, languages, custom_words) -> list[OcrResult]`

Run OCR on an encoded image loaded into memory. Accepts any format supported by the OS decoder — JPEG and PNG are guaranteed; HEIC, TIFF, BMP, and WebP are available on most systems.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `data` | `bytes` | — | Raw bytes of an encoded image file |
| `normalized` | `bool` | — | `True` → result coordinates in `[0.0, 1.0]`; `False` → pixels |
| `roi` | `BoundingBox \| None` | `None` | Region of interest in **normalised** coordinates. `None` = full image |
| `high_accuracy` | `bool` | `True` | Use the accurate (slower) recognition level |
| `languages` | `list[str] \| None` | `None` | BCP-47 hints from `get_supported_languages()`. `None` = auto-detect |
| `custom_words` | `list[str] \| None` | `None` | Domain-specific vocabulary hints. Only applied when `high_accuracy=True` |

---

### `await perform_ocr_on_bgra(bgra, width, height, normalized, *, roi, high_accuracy, languages, custom_words) -> list[OcrResult]`

Run OCR on a raw BGRA8 pixel buffer. Useful when you already have decoded pixel data (e.g. from a screen capture or camera frame) and want to avoid re-encoding.

The buffer must be tightly packed: `len(bgra) == width * height * 4`.

| Parameter | Type | Default | Description |
|---|---|---|---|
| `bgra` | `bytes` | — | Raw BGRA8 pixel data, no row padding |
| `width` | `int` | — | Image width in pixels |
| `height` | `int` | — | Image height in pixels |
| `normalized` | `bool` | — | `True` → result coordinates in `[0.0, 1.0]`; `False` → pixels |
| `roi` | `BoundingBox \| None` | `None` | Region of interest in **normalised** coordinates. `None` = full image |
| `high_accuracy` | `bool` | `True` | Use the accurate (slower) recognition level |
| `languages` | `list[str] \| None` | `None` | BCP-47 hints. `None` = auto-detect |
| `custom_words` | `list[str] \| None` | `None` | Domain-specific vocabulary hints. Only applied when `high_accuracy=True` |

---

### `BoundingBox`

```python
@dataclass
class BoundingBox:
    x: float      # distance from left edge
    y: float      # distance from top edge
    width: float
    height: float
```

Top-left-origin coordinate rectangle. When used as `roi` input, always normalised. When returned in `OcrResult`, normalised or pixel depending on the `normalized` flag.

---

### `OcrResult`

```python
@dataclass
class OcrResult:
    content: str        # recognised text, stripped, never empty
    position: BoundingBox
```

---

## Examples

### Restrict to a region of interest

```python
# Scan only the top-right quarter of the image
roi = native_ocr.BoundingBox(x=0.5, y=0.0, width=0.5, height=0.5)
results = await native_ocr.perform_ocr_on_image(data, normalized=True, roi=roi)
```

### Pixel coordinates

```python
results = await native_ocr.perform_ocr_on_image(data, normalized=False)
for r in results:
    print(f"{r.content!r} at ({r.position.x:.0f}, {r.position.y:.0f})")
```

### OCR from a raw screen capture buffer

```python
async def ocr_frame(bgra_bytes: bytes, width: int, height: int):
    return await native_ocr.perform_ocr_on_bgra(
        bgra_bytes, width, height,
        normalized=True,
        high_accuracy=False,   # faster for real-time use
    )
```

### Language hints

```python
langs = native_ocr.get_supported_languages()
print(langs)  # ['en-US', 'zh-Hans', 'zh-Hant', 'ja-JP', ...]

results = await native_ocr.perform_ocr_on_image(
    data, normalized=True, languages=["zh-Hans", "en-US"]
)
```

---

## License

MIT
