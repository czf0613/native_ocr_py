import pathlib
import pytest

native_ocr = pytest.importorskip(
    "native_ocr",
    reason="native_ocr C extension is not built — run: uv run setup.py build_ext --inplace",
)

from native_ocr import (  # noqa: E402
    BoundingBox,
    get_supported_languages,
    perform_ocr_on_bgra,
    perform_ocr_on_image,
)


# --- get_supported_languages ---


def test_supported_languages_returns_list() -> None:
    langs = get_supported_languages()
    assert isinstance(langs, list)
    assert len(langs) > 0
    for lang in langs:
        assert isinstance(lang, str)
        assert len(lang) > 0
    print(f"Supported languages ({len(langs)}): {langs}")


def test_supported_languages_cached() -> None:
    assert get_supported_languages() is get_supported_languages()


def test_supported_languages_contains_english() -> None:
    langs = get_supported_languages()
    assert any("en" in lang for lang in langs)


def test_supported_languages_contains_chinese() -> None:
    langs = get_supported_languages()
    assert any("zh" in lang for lang in langs)


# --- perform_ocr_on_image ---


@pytest.mark.asyncio
async def test_ocr_image_returns_list(sample_image_bytes: bytes) -> None:
    results = await perform_ocr_on_image(sample_image_bytes, normalized=True)
    assert isinstance(results, list)
    assert len(results) > 0
    print(f"OCR returned {len(results)} results")
    for r in results:
        print(f"  [{r['content']}] @ ({r['position']['x']:.3f}, {r['position']['y']:.3f}, "
              f"{r['position']['width']:.3f}, {r['position']['height']:.3f})")


@pytest.mark.asyncio
async def test_ocr_image_result_types(sample_image_bytes: bytes) -> None:
    results = await perform_ocr_on_image(sample_image_bytes, normalized=True)
    for r in results:
        assert isinstance(r, dict)
        assert isinstance(r["content"], str)
        assert len(r["content"]) > 0
        assert isinstance(r["position"], dict)


@pytest.mark.asyncio
async def test_ocr_image_normalised_bounding_boxes(sample_image_bytes: bytes) -> None:
    results = await perform_ocr_on_image(sample_image_bytes, normalized=True)
    for r in results:
        pos = r["position"]
        assert 0.0 <= pos["x"] <= 1.0
        assert 0.0 <= pos["y"] <= 1.0
        assert 0.0 < pos["width"] <= 1.0
        assert 0.0 < pos["height"] <= 1.0


@pytest.mark.asyncio
async def test_ocr_image_pixel_bounding_boxes(sample_image_bytes: bytes) -> None:
    results = await perform_ocr_on_image(sample_image_bytes, normalized=False)
    assert len(results) > 0
    max_coord = max(
        max(r["position"]["x"], r["position"]["y"],
            r["position"]["width"], r["position"]["height"])
        for r in results
    )
    assert max_coord > 1.0
    print(f"Max pixel coordinate: {max_coord:.1f}")


@pytest.mark.asyncio
async def test_ocr_image_contains_chinese_text(sample_image_bytes: bytes) -> None:
    results = await perform_ocr_on_image(
        sample_image_bytes, normalized=True, languages=["zh-Hans"]
    )
    combined = "".join(r["content"] for r in results)
    assert any("一" <= ch <= "鿿" for ch in combined)
    print(f"Combined text: {combined}")


@pytest.mark.asyncio
async def test_ocr_image_known_text(sample_image_bytes: bytes) -> None:
    results = await perform_ocr_on_image(
        sample_image_bytes, normalized=True, languages=["zh-Hans"]
    )
    combined = "".join(r["content"] for r in results)
    assert "恭喜获得" in combined


@pytest.mark.asyncio
async def test_ocr_image_with_roi(sample_image_bytes: bytes) -> None:
    roi = BoundingBox(x=0.15, y=0.1, width=0.7, height=0.6)
    results = await perform_ocr_on_image(sample_image_bytes, normalized=True, roi=roi)
    assert isinstance(results, list)
    assert len(results) > 0
    print(f"ROI results ({len(results)}): {[r['content'] for r in results]}")


@pytest.mark.asyncio
async def test_ocr_image_low_accuracy(sample_image_bytes: bytes) -> None:
    results = await perform_ocr_on_image(
        sample_image_bytes, normalized=True, high_accuracy=False
    )
    assert isinstance(results, list)
    print(f"Low accuracy: {len(results)} results")


@pytest.mark.asyncio
async def test_ocr_image_custom_words(sample_image_bytes: bytes) -> None:
    results = await perform_ocr_on_image(
        sample_image_bytes,
        normalized=True,
        languages=["zh-Hans"],
        custom_words=["宝石计划", "灵台道人"],
    )
    assert isinstance(results, list)
    assert len(results) > 0


# --- perform_ocr_on_bgra (requires Pillow) ---

PIL = pytest.importorskip("PIL", reason="Pillow is required for BGRA tests")


def _png_to_bgra(path: pathlib.Path) -> tuple[bytes, int, int]:
    from PIL import Image

    img = Image.open(path).convert("RGBA")
    width, height = img.size
    r, g, b, a = img.split()
    bgra_img = Image.merge("RGBA", (b, g, r, a))
    return bgra_img.tobytes(), width, height


@pytest.mark.asyncio
async def test_ocr_bgra_returns_list(sample_image_path: pathlib.Path) -> None:
    bgra, width, height = _png_to_bgra(sample_image_path)
    results = await perform_ocr_on_bgra(bgra, width, height, normalized=True)
    assert isinstance(results, list)
    assert len(results) > 0
    print(f"BGRA OCR: {len(results)} results from {width}x{height} image")


@pytest.mark.asyncio
async def test_ocr_bgra_matches_image_results(sample_image_path: pathlib.Path) -> None:
    bgra, width, height = _png_to_bgra(sample_image_path)
    bgra_results = await perform_ocr_on_bgra(
        bgra, width, height, normalized=True, languages=["zh-Hans"]
    )
    img_results = await perform_ocr_on_image(
        sample_image_path.read_bytes(), normalized=True, languages=["zh-Hans"]
    )
    bgra_text = "".join(r["content"] for r in bgra_results)
    img_text = "".join(r["content"] for r in img_results)
    assert "恭喜获得" in bgra_text
    assert "恭喜获得" in img_text
    print(f"BGRA text: {bgra_text}")
    print(f"Image text: {img_text}")


@pytest.mark.asyncio
async def test_ocr_bgra_normalised_bounding_boxes(sample_image_path: pathlib.Path) -> None:
    bgra, width, height = _png_to_bgra(sample_image_path)
    results = await perform_ocr_on_bgra(bgra, width, height, normalized=True)
    for r in results:
        pos = r["position"]
        assert 0.0 <= pos["x"] <= 1.0
        assert 0.0 <= pos["y"] <= 1.0
        assert 0.0 < pos["width"] <= 1.0
        assert 0.0 < pos["height"] <= 1.0
