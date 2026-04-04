#!/bin/bash
set -e
cd "$(dirname "$0")"

rm -rf build || true
rm -rf dist || true
rm -rf src/native_ocr_py.egg-info || true

uv sync
uv build