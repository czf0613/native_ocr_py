import sys
from setuptools import setup, Extension

ext_modules = []

if sys.platform == "darwin":
    ext_modules.append(
        Extension(
            name="native_ocr.ext._ocr_native",
            include_dirs=[],
            sources=[],
            extra_compile_args=["-fobjc-arc"],
            extra_link_args=[
                "-framework",
                "Vision",
                "-framework",
                "Foundation",
            ],
        )
    )
elif sys.platform == "win32":
    raise NotImplementedError("Windows support is not yet implemented")
else:
    raise RuntimeError("native_ocr_py only supports macOS and Windows")

setup(ext_modules=ext_modules)
