"""Process-local fault/barrier injection verifies native cleanup and GIL safety.

These injected failures are not claims of reproducing an OS/Vision failure.
The barrier then calls real Vision on the generated known-text image.
"""
import pathlib
import subprocess
import sys
import textwrap

import pytest


@pytest.fixture(scope="module")
def fault_library(tmp_path_factory):
    destination = tmp_path_factory.mktemp("native-faults") / "faults.dylib"
    source = pathlib.Path(__file__).with_name("native_faults.m")
    command = ["xcrun", "clang", "-dynamiclib", "-fobjc-arc", "-fobjc-arc-exceptions",
               "-framework", "Foundation", "-framework", "Vision", str(source), "-o", str(destination)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stderr
    return destination


def _run(library, body, *arguments):
    prefix = """
import ctypes, resource, sys, time
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
from native_ocr import _ocr_native as native
lib = ctypes.CDLL(sys.argv[1])
lib.ocr_test_install.argtypes = [ctypes.c_int]
"""
    result = subprocess.run([sys.executable, "-X", "faulthandler", "-c",
                             textwrap.dedent(prefix) + textwrap.dedent(body), str(library), *map(str, arguments)],
                            capture_output=True, text=True, timeout=40)
    assert result.returncode == 0, (result.returncode, result.stdout, result.stderr)
    assert "OK" in result.stdout, result.stdout


@pytest.mark.parametrize("mode", [1, 2], ids=["NSError", "NSException"])
@pytest.mark.parametrize("kind", ["image", "bgra8", "languages"])
def test_native_failures_are_python_exceptions_and_cleanup(fault_library, mode, kind, text_fixture):
    _run(fault_library, f"""
from pathlib import Path
from PIL import Image
owner = bytearray(Path(sys.argv[2]).read_bytes())
if {kind!r} == 'bgra8':
    with Image.open(sys.argv[2]) as image:
        owner = bytearray(image.convert('RGBA').tobytes('raw', 'BGRA'))
def invoke():
    if {kind!r} == 'languages':
        return native.get_supported_langs()
    args = [owner, 1200, 800] if {kind!r} == 'bgra8' else [owner]
    return getattr(native, 'detect_' + {kind!r})(*args, (0, 0, 1, 1), True, ['en-US'], [])
for _ in range(3):
    lib.ocr_test_install({mode})
    try:
        invoke()
    except RuntimeError as exc:
        assert ('ocr.test.injected' if {mode} == 1 else 'OCRTest') in str(exc), str(exc)
    else:
        raise AssertionError('native failure was swallowed')
    owner.extend(b'x')
    del owner[-1:]
lib.ocr_test_install(0)
result = invoke()
assert result
if {kind!r} != 'languages':
    observations = result[0] if {kind!r} == 'image' else result
    assert '4826' in ' '.join(row[0] for row in observations)
print('OK errors, buffer release and subsequent native call')
""", text_fixture)


@pytest.mark.parametrize("kind", ["image", "bgra8"])
@pytest.mark.parametrize("readonly_view", [False, True])
def test_gil_release_and_mutable_input_snapshots(fault_library, kind, readonly_view, text_fixture):
    _run(fault_library, f"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from PIL import Image
owner = bytearray(Path(sys.argv[2]).read_bytes())
if {kind!r} == 'bgra8':
    with Image.open(sys.argv[2]) as image:
        owner = bytearray(image.convert('RGBA').tobytes('raw', 'BGRA'))
view = memoryview(owner).toreadonly() if {readonly_view} else owner
languages, words = ['en-US'], ['NATIVE']
args = [view, 1200, 800] if {kind!r} == 'bgra8' else [view]
lib.ocr_test_install(3)
with ThreadPoolExecutor(max_workers=1) as pool:
    future = pool.submit(getattr(native, 'detect_' + {kind!r}), *args, (0, 0, 1, 1), True, languages, words)
    try:
        deadline = time.monotonic() + 10
        while not lib.ocr_test_entered():
            assert time.monotonic() < deadline, 'Vision barrier was never reached'
            time.sleep(.001)
        # Running Python here proves the native worker has released the GIL.
        # Replace both data and strings while real Vision has not read them yet.
        owner[:] = b'\\x00' * len(owner)
        languages[:] = [object()]
        words[:] = [object()]
    finally:
        lib.ocr_test_unblock()
    result = future.result(timeout=20)
observations = result[0] if {kind!r} == 'image' else result
text = ' '.join(row[0] for row in observations)
assert 'NATIVE OCR 4826' in text and 'LOWER PANEL 7319' in text, text
if {readonly_view}:
    view.release()
owner.extend(b'x')
print('OK GIL, buffer and string snapshots, export released')
""", text_fixture)


def test_await_cancellation_keeps_native_inputs_alive(fault_library, text_fixture):
    _run(fault_library, """
import asyncio
from pathlib import Path
from native_ocr import perform_ocr_on_image
owner = bytearray(Path(sys.argv[2]).read_bytes())
lib.ocr_test_install(3)
async def main():
    task = asyncio.create_task(perform_ocr_on_image(owner, True, languages=['en-US']))
    try:
        deadline = time.monotonic() + 10
        while not lib.ocr_test_entered():
            assert time.monotonic() < deadline
            await asyncio.sleep(.001)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        else:
            raise AssertionError('await did not cancel')
        assert not lib.ocr_test_completed(), 'cancellation unexpectedly ended Vision'
        owner[:] = b'\\x00' * len(owner)
    finally:
        lib.ocr_test_unblock()
asyncio.run(main())  # joins the default executor before returning
assert lib.ocr_test_completed()
owner.extend(b'x')
print('OK cancellation, continued worker and buffer release')
""", text_fixture)
