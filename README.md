# native_ocr_py

通过 Python C/Objective-C 扩展调用 **macOS Vision**，在本机识别图片文字；不调用外部 OCR 服务，也不捆绑模型。

## 环境与安装

- 当前构建仅实现 macOS，不支持 Windows/Linux。
- 项目声明 macOS 13+、Python 3.11+；开发环境由 `.python-version` 固定为 3.14。最低系统、最低 Python 版本及各 CPU 架构未在本轮验证。
- 分发名为 `native_ocr_py`，导入名为 `native_ocr`，编译扩展为 `native_ocr._ocr_native`。
- 源码构建需已安装 Xcode Command Line Tools/SDK 和 `uv`，使用 setuptools。CMake 仅用于 IDE 索引。

在当前独立 checkout 的根目录执行：

```bash
uv sync --locked
uv run --no-sync python setup.py build_ext --inplace
uv run --no-sync python -c 'import native_ocr; import native_ocr._ocr_native as ext; print(native_ocr.__file__); print(ext.__file__)'
uv run --no-sync python examples/ocr_image.py tests/sample.png
```

本轮未核验 PyPI 或预编译 wheel 的可用性；以上为源码构建步骤，尚未作为本轮原生验收执行。更多命令见[开发指南](docs/development.md)。

## 文件输入示例

示例只读取指定图片，打印实际 OCR 返回值，不采集屏幕。可用仓库的 `tests/sample.png`，或用户明确提供的图片路径：

```bash
uv run --no-sync python examples/ocr_image.py tests/sample.png --language zh-Hans
uv run --no-sync python examples/ocr_image.py tests/sample.png --pixels
```

在已有 Python 程序中：

```python
import asyncio
from pathlib import Path

import native_ocr


async def main():
    data = Path("tests/sample.png").read_bytes()
    results = await native_ocr.perform_ocr_on_image(data, normalized=True)
    for result in results:
        box = result["position"]
        print(result["content"], box["x"], box["y"])


asyncio.run(main())
```

## 公共 API

以下签名与当前 Python 包装层一致；`normalized` 必填，可选参数也允许位置传参，没有 keyword-only 的 `*`。

```python
def get_supported_languages() -> list[str]: ...

async def perform_ocr_on_image(
    data: bytes,
    normalized: bool,
    roi: BoundingBox | None = None,
    high_accuracy: bool = True,
    languages: list[str] | None = None,
    custom_words: list[str] | None = None,
) -> list[OcrResult]: ...

async def perform_ocr_on_bgra(
    bgra: bytes,
    width: int,
    height: int,
    normalized: bool,
    roi: BoundingBox | None = None,
    high_accuracy: bool = True,
    languages: list[str] | None = None,
    custom_words: list[str] | None = None,
) -> list[OcrResult]: ...
```

| 参数/接口 | 约定 |
| --- | --- |
| `data` | 编码图片文件的完整字节。通过系统 ImageIO 解码第 0 帧；格式能力取决于系统，不承诺逐一验证所有格式或多帧识别。 |
| `bgra`, `width`, `height` | 已解码的 BGRA8 字节和正整数像素尺寸。每像素 B、G、R、A 四字节，无行填充；必须严格满足 `len(bgra) == width * height * 4`。原生使用预乘 alpha；透明像素的颜色通道需预乘，完全不透明图可用 A=255。 |
| `normalized` | `True` 返回归一化坐标；`False` 按原始整图宽高换算为像素坐标，数值仍为 `float`，不取整。 |
| `roi` | 始终使用左上原点、归一化矩形，和 `normalized` 的取值无关；`None` 表示全图。合法输入需四项齐全且有限，`x,y >= 0`、`width,height > 0`、`x+width,y+height <= 1`。当前校验不完整，不能依赖它处理非法输入。 |
| `high_accuracy` | `True` 选择 Vision accurate，`False` 选择 fast；不是本库显式执行多轮纠错。 |
| `languages` | BCP-47 语言提示列表。`None` 或 `[]` 不设置 `recognitionLanguages`，使用系统默认语言配置；本库未启用自动语言检测。 |
| `custom_words` | 补充词表，仅在 accurate 模式设置；不保证改善每次识别。 |
| `get_supported_languages()` | 同步查询 accurate 模式的语言列表并缓存，不能据此保证 fast 模式同样支持。返回同一个可变列表，调用方应避免修改。当前失败也可能返回并缓存 `[]`。 |

### 返回值与坐标

`BoundingBox` 和 `OcrResult` 是 `TypedDict`，运行时都是字典，不能用属性访问：

```python
from typing import TypedDict


class BoundingBox(TypedDict):
    x: float
    y: float
    width: float
    height: float


class OcrResult(TypedDict):
    content: str
    position: BoundingBox
```

文本会去除两端空白并过滤空串。矩形以左上角为原点，x 向右、y 向下。原生层翻转 Vision 的 y 轴；Python 层用整幅解码图的宽高缩放，不按 ROI 重新缩放或偏移。局部 ROI 的实际坐标行为仍待 fixture 验证。

例如，以下片段接在异步函数中，`data` 为图片文件字节：

```python
roi = native_ocr.BoundingBox(x=0.5, y=0.0, width=0.5, height=0.5)
results = await native_ocr.perform_ocr_on_image(data, False, roi)
for result in results:
    box = result["position"]
    print(result["content"], box["x"], box["y"], box["width"], box["height"])
```

## 当前限制与接管状态

本初稿依据固定输入 `819f41413f22812eb25c64c0efd04cad0d5b3107` 的源码，尚未集成实现 Agent 的修复。详见[接管计划](docs/codex-takeover-plan-20261027.md)和[架构说明](docs/architecture.md)。

- 正常无文字可返回 `[]`；当前部分解码、图像创建、语言查询及 Vision 失败也返回空结果，因此 `[]` 不能证明识别成功。
- 参数解析、尺寸/缓冲区、ROI、字符串和分配错误处理尚有安全缺口；类型注解/stub 不做运行时校验。不要将非法输入直接用于当前原生入口。
- 两个 OCR API 通过 `asyncio.to_thread` 调同步扩展；当前原生 Vision 调用没有显式释放 GIL，不能保证事件循环响应性或并行加速。取消等待不会可靠终止已经开始的原生请求。
- 更明确的 Python 异常、资源清理和 GIL 处理属于待集成、待验证变更；本轮只检查文档与示例语法，不宣称原生功能通过。
- 未固定 Vision request revision；未显式传入 EXIF orientation，也未验证透明 BGRA、方向元数据和各系统格式边界。

## 维护入口

统一规则见 [AGENTS.md](AGENTS.md)，开发步骤见[开发指南](docs/development.md)。本次接管仅向指定测试分支交付，不更新默认分支，不执行发布流程。

## License

[MIT](LICENSE)
