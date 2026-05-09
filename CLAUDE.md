## Network Access

This repository is hosted on GitHub, which is not accessible in some countries. If there's a network issue, set the HTTP proxy and HTTPS proxy to `localhost:7890`:

```bash
export http_proxy=http://localhost:7890
export https_proxy=http://localhost:7890
```

## Package Manager

We use `uv` to manage this project. Always use `uv` commands for project operations:

- `uv run` to execute scripts and commands
- `uv add` to add dependencies
- `uv sync` to sync the environment

## Build

Build the C extension locally:
```bash
uv run setup.py build_ext --inplace
```

Run tests:
```bash
uv run pytest
```

## Testing

Tests are in the `tests/` directory. Async tests use `pytest-asyncio`.

Only run the specific test file(s) relevant to your changes, not the full suite. For example:

```bash
uv run pytest tests/test_ocr.py -v -s
```

Only run the full suite (`uv run pytest -v -s`) when explicitly asked or before a commit/push.

## Project Structure

```
native_code/
  osx/          # macOS C/ObjC extension source
    include/
      apple_ocr.h    # C interface header
    src/
      ext.c          # Module entry point (Python ↔ C bridge)
      apple_ocr.m    # Vision framework wrapper (ObjC)
    CMakeLists.txt   # IDE hints only, NOT for building
src/
  native_ocr/
    __init__.py      # Public async API
    _ocr_native.pyi  # Type stubs for the C extension
    types.py         # TypedDict definitions (BoundingBox, OcrResult)
```

The `CMakeLists.txt` file is **only** for IDE code navigation and hints (e.g. CLion, VS Code IntelliSense). Do **not** use CMake to build this project. Always build via `setup.py` (which is invoked automatically by `uv` / `pip`).

## C extension conventions
C code are in folder `native_code/{OS_NAME}`, each of them is a cmake project.
But this cmake project is only used for IDE indexing and code hints, DO NOT `make` this project!
You should always try to build via `setup.py`

## Documentation

Write docstrings and type annotations in the `.pyi` stub files, not in C code. Every public function exposed by the C extension must have a corresponding annotated entry in the `.pyi` file so that users and IDEs can understand the API.

## C Code Style

- **No docstrings in C method tables.** Pass `NULL` for the `ml_doc` field in `PyMethodDef`. All documentation belongs in the `.pyi` stub files.
- **Declare variables near first use.** Do not group declarations at the top of a function.
- **Simplify allocation checks.** Functions like `PyList_New`, `Py_BuildValue`, and `PyDict_New` have negligible failure probability on modern machines. Do not write elaborate NULL-check-and-cleanup chains for them. Only check return values from system/OS calls that can realistically fail (e.g. `CGImageCreate`).
- **Do not check `PyArg_ParseTuple` return values.** The `.pyi` stub enforces correct types at the Python level, so callers will not pass wrong arguments. Just call it and use the parsed variables directly.
- **Always use braces for control flow.** Every `if`, `else`, `for`, and `while` body must be wrapped in `{}`, even if it is a single statement.
