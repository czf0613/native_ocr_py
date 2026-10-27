"""Unsafe native inputs run only in timeout-protected, core-disabled children."""
import subprocess
import sys

import pytest

ROI = (0.0, 0.0, 1.0, 1.0)


def _arguments(kind):
    if kind == "image":
        return [b"invalid encoded image", ROI, True, [], []]
    return [b"\xff" * 4, 1, 1, ROI, True, [], []]


def _cases():
    for kind in ("image", "bgra8"):
        base = _arguments(kind)
        yield kind, [], "TypeError", "missing"
        yield kind, base[:-1], "TypeError", "too-few"
        yield kind, base + [None], "TypeError", "too-many"
        for buffer in (None, "text", 0, [], memoryview(b"1234")[::2]):
            yield kind, [buffer, *base[1:]], "TypeError" if not isinstance(buffer, memoryview) else "BufferError", "buffer"
        roi_index = 1 if kind == "image" else 3
        for roi in (None, [], {}, (), (0, 0, 1), (0, 0, 1, 1, 1), [0, 0, 1, 1]):
            args = base.copy()
            args[roi_index] = roi
            yield kind, args, "TypeError", "roi-structure"
        for roi in (("0", 0, 1, 1), (None, 0, 1, 1)):
            args = base.copy()
            args[roi_index] = roi
            yield kind, args, "TypeError", "roi-type"
        for roi in ((float("nan"), 0, 1, 1), (0, float("inf"), 1, 1),
                    (0, 0, float("-inf"), 1), (-0.1, 0, 1, 1),
                    (0, -0.1, 1, 1), (0, 0, 0, 1), (0, 0, 1, -1),
                    (0.5, 0, 0.6, 1), (0, 0.5, 1, 0.6)):
            args = base.copy()
            args[roi_index] = roi
            yield kind, args, "ValueError", "roi-range"
        for index in (roi_index + 2, roi_index + 3):
            for value in (None, False, 0, "", (), {}, [1], [None], [b"en-US"], ["\ud800"], ["en\0US"]):
                args = base.copy()
                args[index] = value
                error = "UnicodeEncodeError" if value == ["\ud800"] else "ValueError" if value == ["en\0US"] else "TypeError"
                yield kind, args, error, "hints"
    for width, height, data, error in (
        (0, 1, b"", "ValueError"), (-1, 1, b"", "ValueError"),
        (1, 0, b"", "ValueError"), (1, -1, b"", "ValueError"),
        (1, 1, b"123", "ValueError"), (1, 1, b"12345", "ValueError"),
        (2**31, 1, b"", "OverflowError"), (1, 2**31, b"", "OverflowError"),
        (2**30, 1, b"", "ValueError"), (65536, 65536, b"", "ValueError"),
        (2**31 - 1, 2**31 - 1, b"", "OverflowError"),
        (1.0, 1, b"1234", "TypeError"), (1, "1", b"1234", "TypeError"),
    ):
        yield "bgra8", [data, width, height, ROI, True, [], []], error, "dimensions"
    for data in (b"", b"not an image", b"\x89PNG\r\n\x1a\n"):
        yield "image", [data, ROI, True, [], []], "ValueError", "decode"


CASES = list(_cases())


# repr(memoryview) is not executable, and float repr uses nan/inf names.
def _expression(value):
    if isinstance(value, memoryview):
        return "memoryview(b'1234')[::2]"
    if isinstance(value, list):
        return "[" + ", ".join(_expression(item) for item in value) + "]"
    return repr(value)


@pytest.mark.parametrize("kind,args,error,label", CASES,
                         ids=[f"{kind}-{label}-{i}" for i, (kind, _, _, label) in enumerate(CASES)])
def test_native_rejects_invalid_input(kind, args, error, label):
    script = f"""
import resource
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
from native_ocr import _ocr_native as native
nan = float('nan')
inf = float('inf')
try:
    native.detect_{kind}(*{_expression(args)})
except {error} as exc:
    assert type(exc).__name__ == {error!r}, type(exc).__name__
    print('OK ' + type(exc).__name__)
else:
    raise AssertionError('native call accepted invalid input')
"""
    result = subprocess.run([sys.executable, "-X", "faulthandler", "-c", script],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert result.stdout.strip() == f"OK {error}", result.stdout


@pytest.mark.parametrize("kind", ["image", "bgra8"])
def test_buffer_export_released_after_parse_and_validation_errors(kind):
    # A leaked Py_buffer prevents bytearray resizing even after a failed call.
    script = f"""
from native_ocr import _ocr_native as native
for mode in ('parse', 'validate'):
    data = bytearray(b'1234')
    args = [data, 2**31, 1, (0, 0, 1, 1), True, [], []] if {kind!r} == 'bgra8' else [data, (), True, [], []]
    if mode == 'parse':
        args = [data]
    try:
        native.detect_{kind}(*args)
    except (TypeError, ValueError, OverflowError):
        pass
    else:
        raise AssertionError('expected error')
    data.extend(b'5')
print('OK released')
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert result.stdout.strip() == "OK released"
