# native_ocr_py

通过 Python C/Objective-C 扩展调用 **macOS Vision**，在本机识别图片文字；不调用外部 OCR 服务，也不捆绑模型。

## 环境与安装

- 当前构建仅实现 macOS，不支持 Windows/Linux。
- 项目声明 macOS 13+、Python 3.11+；开发环境由 `.python-version` 固定为 3.14。目前记录的实测环境为 macOS 26.6.2 / arm64 / Python 3.14.7，不代表最低系统、其它 Python 或 CPU 架构已验证。
- 分发名为 `native_ocr_py`，导入名为 `native_ocr`，编译扩展为 `native_ocr._ocr_native`。
- 源码构建需已安装 Xcode Command Line Tools/SDK 和 `uv`，使用 setuptools。CMake 仅用于 IDE 索引。

在 checkout 的根目录执行（获取源码见[开发指南](docs/development.md)）：

```bash
uv sync --locked
uv run --no-sync python setup.py build_ext --inplace
uv run --no-sync python -c 'import native_ocr; import native_ocr._ocr_native as ext; print(native_ocr.__file__); print(ext.__file__)'
uv run --no-sync python examples/ocr_image.py tests/sample.png
```

以上构建和文件输入示例已在当前 worktree 执行；这不代表样例文字均识别正确。PyPI/wheel 发布覆盖未核验；本地生成的 wheel 标签也不构成最低系统支持证明。详见[验证记录](docs/validation-20261027.md)。

## 文件输入示例

示例只读取指定图片，打印实际 OCR 返回值，不采集屏幕。可用仓库的 `tests/sample.png`，或用户明确提供的图片路径：

```bash
uv run --no-sync python examples/ocr_image.py tests/sample.png --language zh-Hans
uv run --no-sync python examples/ocr_image.py tests/sample.png --language zh-Hans --pixels
```

原样例标题正确文字为“恭喜获得”；当前系统显式中文提示仍输出“恭喜荻得。”。这是已知识别误差，不是正确输出示范；默认语言也未正确识别该标题。

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
| `roi` | 始终使用左上原点、归一化矩形，和 `normalized` 的取值无关；`None` 表示全图。四项必须齐全、可转为数值且有限，`x,y >= 0`、`width,height > 0`、`x+width,y+height <= 1`；不自动裁剪。结果仍相对整图。 |
| `high_accuracy` | `True` 选择 Vision accurate，`False` 选择 fast；不是本库显式执行多轮纠错。 |
| `languages` | BCP-47 语言提示列表。`None` 或 `[]` 不设置 `recognitionLanguages`，使用系统默认语言配置；本库未启用自动语言检测。 |
| `custom_words` | 补充词表，仅在 accurate 模式设置；不保证改善每次识别。 |
| `get_supported_languages()` | 同步查询 accurate 模式的语言列表，仅缓存成功结果；失败抛异常。不能据此保证 fast 模式同样支持。返回同一个可变列表，调用方应避免修改。 |

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

文本会去除两端空白并过滤空串。矩形以左上角为原点，x 向右、y 向下。原生层将 Vision 的 ROI 局部坐标换算回整图并翻转 y 轴；Python 层再按需要乘整图宽高。局部 ROI 不改变输出的整图坐标基准；生成图片的内容/ROI 回归已验证此约定，来源见验证记录。

例如，以下片段接在异步函数中，`data` 为图片文件字节：

```python
roi = native_ocr.BoundingBox(x=0.5, y=0.0, width=0.5, height=0.5)
results = await native_ocr.perform_ocr_on_image(data, False, roi)
for result in results:
    box = result["position"]
    print(result["content"], box["x"], box["y"], box["width"], box["height"])
```

## 异常与异步限制

已集成实现提交 `dff3766418c20abf6b302c1656c6e55148af9b87`。正常识别但无文字（或候选仅为空白）返回 `[]`；错误路径会抛出 Python 异常，与旧版静默空结果有行为差异。

| 异常 | 典型原因 |
| --- | --- |
| `TypeError` | 参数类型错误、ROI 字段缺失、语言/词表不是字符串列表。 |
| `ValueError` | 非正尺寸、BGRA 长度不符、ROI 非有限/越界、提示含 NUL、图片无法解码。孤立 surrogate 的 UTF-8 转换会抛其子类 `UnicodeEncodeError`。 |
| `OverflowError` | 尺寸或长度超出底层可表示范围。 |
| `RuntimeError` | CoreGraphics 图像创建、Vision 识别/语言查询失败，或捕获到 Objective-C 异常。 |
| `MemoryError` | 已检查的分配操作失败；未做真实内存耗尽验证。 |

两个 OCR API 通过 `asyncio.to_thread` 调同步扩展。原生工作线程先复制输入字节和提示词，再在 Vision `performRequests` 期间释放 GIL；参数处理、图像解码和同步语言查询不因此变成无阻塞操作，也不保证并发加速。取消 await 或超时不会终止已经开始的原生请求；`asyncio.run` 退出时还可能等待工作线程结束。

未固定 Vision request revision，未显式传入 EXIF orientation。透明 BGRA、EXIF 方向、其它平台/版本及内存泄漏仍未验证。完整边界见[架构说明](docs/architecture.md)和[验证记录](docs/validation-20261027.md)。

## 维护入口

统一规则见 [AGENTS.md](AGENTS.md)，开发步骤见[开发指南](docs/development.md)，历史决策见[接管计划](docs/codex-takeover-plan-20261027.md)。分支更新和发布须遵守当前用户授权。

## License

[MIT](LICENSE)
