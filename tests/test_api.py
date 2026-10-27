"""Wrapper contracts tested with bound native functions replaced, not Vision."""
import threading

import pytest

import native_ocr as api


@pytest.mark.parametrize("kind", ["image", "bgra"])
@pytest.mark.parametrize("normalized", [True, False])
@pytest.mark.asyncio
async def test_positional_arguments_results_and_scaling(monkeypatch, kind, normalized):
    calls = []
    caller_thread = threading.get_ident()
    raw = [("  Native text \n", 0.1, 0.2, 0.3, 0.4), (" \n\t", 0, 0, 1, 1)]

    def native(*args):
        assert threading.get_ident() != caller_thread
        calls.append(args)
        return (raw, 100, 200) if kind == "image" else raw

    roi = dict(x=0, y=0.1, width=1, height=0.8)
    languages, words = ["en-US"], ["Native"]
    monkeypatch.setattr(api, f"_detect_{'image' if kind == 'image' else 'bgra8'}", native)
    if kind == "image":
        results = await api.perform_ocr_on_image(b"data", normalized, roi, False, languages, words)
        expected_call = (b"data", (0, 0.1, 1, 0.8), False, languages, words)
    else:
        results = await api.perform_ocr_on_bgra(b"data", 100, 200, normalized, roi, False, languages, words)
        expected_call = (b"data", 100, 200, (0, 0.1, 1, 0.8), False, languages, words)
    assert calls == [expected_call]
    box = dict(x=0.1, y=0.2, width=0.3, height=0.4) if normalized else dict(x=10., y=40., width=30., height=80.)
    assert results == [dict(content="Native text", position=box)]
    assert isinstance(results[0], dict) and isinstance(results[0]["position"], dict)


@pytest.mark.parametrize("kind", ["image", "bgra"])
@pytest.mark.asyncio
async def test_none_defaults_and_empty_results(monkeypatch, kind):
    def native(*args):
        assert args[-4:] == ((0., 0., 1., 1.), True, [], [])
        return ([], 100, 200) if kind == "image" else []

    monkeypatch.setattr(api, f"_detect_{'image' if kind == 'image' else 'bgra8'}", native)
    results = await api.perform_ocr_on_image(b"data", True) if kind == "image" else await api.perform_ocr_on_bgra(b"data", 1, 1, True)
    assert results == []


@pytest.mark.parametrize("kind", ["image", "bgra"])
@pytest.mark.parametrize("error", [ValueError("decode"), RuntimeError("Vision"), MemoryError("allocation")])
@pytest.mark.asyncio
async def test_native_exception_propagates(monkeypatch, kind, error):
    def native(*args):
        raise error

    monkeypatch.setattr(api, f"_detect_{'image' if kind == 'image' else 'bgra8'}", native)
    with pytest.raises(type(error)) as caught:
        if kind == "image":
            await api.perform_ocr_on_image(b"data", True)
        else:
            await api.perform_ocr_on_bgra(b"data", 1, 1, True)
    assert caught.value is error


@pytest.mark.parametrize("kind", ["image", "bgra"])
@pytest.mark.parametrize("field", ["languages", "custom_words"])
@pytest.mark.parametrize("value", [False, 0, "", (), {}])
@pytest.mark.asyncio
async def test_invalid_falsy_hints_are_not_discarded(kind, field, value):
    # Actual native validation, reached before any attempt to decode this data.
    with pytest.raises(TypeError):
        if kind == "image":
            await api.perform_ocr_on_image(b"data", True, **{field: value})
        else:
            await api.perform_ocr_on_bgra(b"1234", 1, 1, True, **{field: value})


@pytest.mark.parametrize("roi", [False, (), [], {}, dict(x=0, y=0, width=1)])
@pytest.mark.asyncio
async def test_public_roi_structure(roi):
    with pytest.raises(TypeError):
        await api.perform_ocr_on_image(b"data", True, roi)


def test_language_cache_only_stores_success(monkeypatch):
    api.get_supported_languages.cache_clear()
    calls = 0
    languages = ["en-US"]

    def native():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("query failed")
        return languages

    monkeypatch.setattr(api, "get_supported_langs", native)
    try:
        with pytest.raises(RuntimeError, match="query failed"):
            api.get_supported_languages()
        assert api.get_supported_languages() is languages
        assert api.get_supported_languages() is languages
        assert calls == 2
    finally:
        api.get_supported_languages.cache_clear()
