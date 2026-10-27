"""读取明确指定的图片文件并打印实际 OCR 结果，不采集屏幕。"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from native_ocr import OcrResult


async def recognize(
    data: bytes, normalized: bool, languages: list[str] | None
) -> list[OcrResult]:
    from native_ocr import perform_ocr_on_image

    return await perform_ocr_on_image(
        data, normalized=normalized, languages=languages
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path, help="仓库样例或用户明确提供的图片路径")
    parser.add_argument("--pixels", action="store_true", help="输出浮点像素坐标")
    parser.add_argument(
        "--language", action="append", help="BCP-47 语言提示，可重复；默认使用系统语言配置"
    )
    args = parser.parse_args()
    try:
        data = args.image.read_bytes()
    except OSError as error:
        parser.error(str(error))
    results = asyncio.run(recognize(data, not args.pixels, args.language))
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
