cmake_minimum_required(VERSION 3.20)
project(ocr_native LANGUAGES C OBJC)

# ---------------------------------------------------------------------------
# NOTE: This CMake project is for IDE indexing and code hints ONLY.
# Do NOT build or install via CMake. Use `uv run setup.py build_ext --inplace`
# to produce the actual Python extension.
# ---------------------------------------------------------------------------

set(CMAKE_C_STANDARD 11)
set(CMAKE_OBJC_ARC ON)

# Python headers — hardcoded for IDE indexing only (Homebrew Python 3.14)
set(Python3_INCLUDE_DIRS
    /opt/homebrew/opt/python@3.14/Frameworks/Python.framework/Versions/3.14/include/python3.14
)
set(Python3_LIBRARIES "")

# macOS SDK frameworks
find_library(VISION_FRAMEWORK    Vision    REQUIRED)
find_library(FOUNDATION_FRAMEWORK Foundation REQUIRED)
find_library(COREGRAPHICS_FRAMEWORK CoreGraphics REQUIRED)
find_library(IMAGEIO_FRAMEWORK     ImageIO      REQUIRED)

add_library(${PROJECT_NAME} SHARED
    src/apple_ocr.m
    src/ocr_native.c
)

target_include_directories(${PROJECT_NAME} PRIVATE
    include
    ${Python3_INCLUDE_DIRS}
)

target_compile_options(${PROJECT_NAME} PRIVATE
    -fobjc-arc
)

target_link_libraries(${PROJECT_NAME} PRIVATE
    ${VISION_FRAMEWORK}
    ${FOUNDATION_FRAMEWORK}
    ${COREGRAPHICS_FRAMEWORK}
    ${IMAGEIO_FRAMEWORK}
)
# Python3_LIBRARIES is intentionally empty — IDE indexing only, not a real build
