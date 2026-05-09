import platform
from setuptools import setup, Extension

ext_modules = []

match platform.system():
    case "Darwin":
        ext_modules.append(
            Extension(
                name="native_ocr._ocr_native",
                include_dirs=["native_code/osx/include"],
                sources=[
                    "native_code/osx/src/ext.c",
                    "native_code/osx/src/apple_ocr.m",
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
    case "Windows":
        raise RuntimeError("Windows support coming soon")
    case unsupported:
        raise RuntimeError(f"Unsupported platform: {unsupported}")

setup(ext_modules=ext_modules)
