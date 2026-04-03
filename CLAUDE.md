## Build

Build the C extension locally:
```bash
uv run setup.py build_ext --inplace
```

Run tests:
```bash
uv run pytest
```

## C extension conventions
C code are in folder `native_code/{OS_NAME}`, each of them is a cmake project.
But this cmake project is only used for IDE indexing and code hints, DO NOT `make` this project!
You should always try to build via `setup.py`
