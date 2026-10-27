"""Run after `uv build --no-build-isolation --offline`; install only local artifacts."""
import pathlib
import subprocess
import sys
import tarfile
import tempfile
import zipfile


def main():
    root = pathlib.Path(__file__).resolve().parents[1]
    wheels = list((root / "dist").glob("*.whl"))
    sdists = list((root / "dist").glob("*.tar.gz"))
    assert len(wheels) == len(sdists) == 1, "Expected exactly one local wheel and sdist"
    with zipfile.ZipFile(wheels[0]) as wheel:
        names = wheel.namelist()
        assert "native_ocr/_ocr_native.pyi" in names
        assert "native_ocr/py.typed" in names
        assert any(name.startswith("native_ocr/_ocr_native.") and name.endswith(".so") for name in names)
    with tarfile.open(sdists[0]) as sdist:
        names = sdist.getnames()
        for source in ("native_code/osx/src/apple_ocr.m", "native_code/osx/src/ext.c",
                       "native_code/osx/include/apple_ocr.h"):
            assert any(name.endswith("/" + source) for name in names), source
    with tempfile.TemporaryDirectory(prefix="ocr-wheel-") as directory:
        venv = pathlib.Path(directory) / "venv"
        subprocess.run(["uv", "venv", "--python", sys.executable, str(venv)], check=True)
        interpreter = venv / "bin" / "python"
        subprocess.run(["uv", "pip", "install", "--python", str(interpreter), "--no-deps",
                        "--offline", str(wheels[0])], check=True)
        script = """
import asyncio, pathlib, sys
import native_ocr
from native_ocr import _ocr_native
path = pathlib.Path(_ocr_native.__file__).resolve()
assert path.is_relative_to(pathlib.Path(sys.argv[1]).resolve()), path
assert path.suffix == '.so'
assert 'en-US' in native_ocr.get_supported_languages()
async def check():
    try:
        await native_ocr.perform_ocr_on_image(b'not an image', True)
    except ValueError:
        pass
    else:
        raise AssertionError('invalid encoding must raise ValueError')
asyncio.run(check())
print('Installed wheel import:', path)
print('OK wheel import, language query, invalid encoding and packaged type/native sources')
"""
        subprocess.run([str(interpreter), "-I", "-c", script, str(venv)], cwd=directory, check=True)


if __name__ == "__main__":
    main()
