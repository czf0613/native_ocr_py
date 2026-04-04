import sys
from setuptools import setup, Extension

ext_modules = []

if sys.platform == "darwin":
    ext_modules.append(
        Extension(
            name="native_ocr.ext._ocr_native",
            include_dirs=["native_code/osx/include"],
            sources=[
                "native_code/osx/src/apple_ocr.m",
                "native_code/osx/src/ocr_native.c",
            ],
            extra_compile_args=["-fobjc-arc"],
            extra_link_args=[
                "-framework",
                "Vision",
                "-framework",
                "Foundation",
                "-framework",
                "CoreGraphics",
                "-framework",
                "ImageIO",
            ],
        )
    )
elif sys.platform == "win32":
    raise NotImplementedError("Windows support is not yet implemented")
else:
    raise RuntimeError("native_ocr_py only supports macOS and Windows")

setup(ext_modules=ext_modules)
