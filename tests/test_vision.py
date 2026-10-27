"""Real Vision content/coordinate checks against text generated in conftest."""
import asyncio
import io
import time

import pytest

from native_ocr import perform_ocr_on_bgra, perform_ocr_on_image


async def _recognise(path, kind, normalized=True, roi=None, high_accuracy=True, custom_words=None,
                     languages=None):
    languages = ["en-US"] if languages is None else languages
    if kind == "image":
        return await perform_ocr_on_image(path.read_bytes(), normalized, roi, high_accuracy,
                                          languages, custom_words)
    from PIL import Image

    with Image.open(path) as image:
        image = image.convert("RGBA")
        data = image.tobytes("raw", "BGRA")
        return await perform_ocr_on_bgra(data, *image.size, normalized, roi, high_accuracy,
                                        languages, custom_words)


def _text(results):
    assert results, "known text fixture must produce observations"
    return " ".join(result["content"] for result in results)


def _check_text_and_boxes(results, normalized=True):
    text = _text(results)
    assert "NATIVE OCR 4826" in text
    assert "LOWER PANEL 7319" in text
    for token, low, high in (("4826", 0.10, 0.30), ("7319", 0.60, 0.85)):
        matching = [result for result in results if token in result["content"]]
        assert matching
        box = matching[0]["position"]
        x, y, width, height = (box[name] for name in ("x", "y", "width", "height"))
        if not normalized:
            x, width, y, height = x / 1200, width / 1200, y / 800, height / 800
        assert 0.05 < x < 0.20
        assert low < y < y + height < high
        assert 0.3 < width < 0.85


@pytest.mark.parametrize("kind", ["image", "bgra"])
@pytest.mark.parametrize("high_accuracy", [True, False])
@pytest.mark.asyncio
async def test_generated_content_and_full_image_coordinates(text_fixture, kind, high_accuracy):
    results = await _recognise(text_fixture, kind, high_accuracy=high_accuracy,
                               custom_words=["NATIVE", "PANEL"])
    _check_text_and_boxes(results)


@pytest.mark.parametrize("kind", ["image", "bgra"])
@pytest.mark.parametrize("upper", [True, False])
@pytest.mark.asyncio
async def test_roi_inclusion_exclusion_and_source_coordinates(text_fixture, kind, upper):
    roi = dict(x=0.05, y=0.0 if upper else 0.55, width=0.90, height=0.45)
    results = await _recognise(text_fixture, kind, roi=roi)
    text = _text(results)
    assert ("4826" if upper else "7319") in text
    assert ("7319" if upper else "4826") not in text
    # ROI results are relative to the entire source, not the cropped ROI.
    for result in results:
        box = result["position"]
        assert 0.05 < box["x"] < 0.20
        assert (0.10 if upper else 0.60) < box["y"] < (0.30 if upper else 0.85)
    pixels = await _recognise(text_fixture, kind, normalized=False, roi=roi)
    assert [r["content"] for r in pixels] == [r["content"] for r in results]
    for norm, pixel in zip(results, pixels, strict=True):
        for name, scale in (("x", 1200), ("y", 800), ("width", 1200), ("height", 800)):
            assert pixel["position"][name] == pytest.approx(norm["position"][name] * scale, abs=2)


@pytest.mark.parametrize("kind", ["image", "bgra"])
@pytest.mark.asyncio
async def test_blank_image_remains_empty(kind):
    from PIL import Image

    image = Image.new("RGBA", (600, 400), "white")
    if kind == "image":
        stream = io.BytesIO()
        image.save(stream, format="PNG")
        results = await perform_ocr_on_image(stream.getvalue(), True)
    else:
        results = await perform_ocr_on_bgra(image.tobytes("raw", "BGRA"), 600, 400, True)
    assert results == []


@pytest.mark.parametrize("kind", ["image", "bgra"])
@pytest.mark.parametrize("languages", [["zh-Hans"], ["zh-Hans", "en-US"]])
@pytest.mark.asyncio
async def test_generated_chinese_exact_text_and_roi(chinese_text_fixture, kind, languages):
    # Expected characters come from the draw.text source, never from OCR output.
    results = await _recognise(chinese_text_fixture, kind, languages=languages)
    text = _text(results)
    assert "恭喜获得" in text
    assert "下方区域7319" in text.replace(" ", "")
    top = await _recognise(chinese_text_fixture, kind, languages=languages,
                           roi=dict(x=0.05, y=0, width=0.90, height=0.45))
    assert "恭喜获得" in _text(top)
    assert "7319" not in _text(top)
    assert all(0.10 < result["position"]["y"] < 0.30 for result in top)


@pytest.mark.asyncio
async def test_real_concurrent_vision_and_event_loop_progress(text_fixture):
    ticks = 0
    done = False

    async def heartbeat():
        nonlocal ticks
        while not done:
            await asyncio.sleep(0.002)
            ticks += 1

    heartbeat_task = asyncio.create_task(heartbeat())
    start = time.monotonic()
    try:
        results = await asyncio.wait_for(asyncio.gather(
            _recognise(text_fixture, "image"), _recognise(text_fixture, "bgra"),
            _recognise(text_fixture, "image")), timeout=30)
        observed_ticks = ticks
    finally:
        done = True
        await heartbeat_task
    for result in results:
        _check_text_and_boxes(result)
    print(f"Concurrent real OCR: elapsed={time.monotonic() - start:.3f}s, heartbeat_ticks={observed_ticks}")
    assert observed_ticks > 0
