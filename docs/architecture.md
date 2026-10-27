# 架构与当前边界

本说明对应固定输入 `819f41413f22812eb25c64c0efd04cad0d5b3107`；实现修复尚未集成，本轮未执行原生功能验收。

## 调用链

```text
应用（读取图片文件或提供已解码 BGRA）
  → native_ocr 的 async Python 包装
  → asyncio.to_thread
  → _ocr_native 同步 C 入口（ext.c 注册）
  → apple_ocr.m：CoreGraphics / ImageIO → Vision request
  → 原生 tuple 列表 → Python 文本清理和坐标缩放 → 嵌套 dict
```

| 文件 | 职责 |
| --- | --- |
| `src/native_ocr/__init__.py` | 五个公共导出；语言查询缓存、ROI 转 tuple、线程调度、去空白/空串及坐标换算。 |
| `src/native_ocr/types.py` | `BoundingBox` / `OcrResult` TypedDict；运行时是 dict。 |
| `src/native_ocr/_ocr_native.pyi` | 三个同步扩展入口的静态接口，不检查运行时输入。部分旧说明与源码不符，以本说明及 README 的源码核对结果为准，待实现角色对齐。 |
| `native_code/osx/src/ext.c` | 注册 `get_supported_langs`、`detect_image`、`detect_bgra8`。 |
| `native_code/osx/src/apple_ocr.m` | 参数处理、图像构造/解码、Vision 请求、结果提取和资源释放。 |
| `setup.py` / `pyproject.toml` | setuptools 扩展构建及项目元数据；链接 Vision、Foundation、CoreGraphics、ImageIO。 |
| `native_code/osx/CMakeLists.txt` | IDE 索引，不能用于构建。 |

## 图像、坐标与语言

编码路径以无拷贝 NSData 包装文件字节，经 ImageIO 解码第 0 帧并取得整图宽高；没有显式传入 EXIF orientation。BGRA 路径使用无拷贝 CGDataProvider 构造 CGImage：紧密排列、无行填充、每像素四字节、预乘 alpha。输入必须严格等长，当前原生代码尚未完整校验长度和尺寸溢出。

ROI 输入采用左上原点的归一化 `(x, y, width, height)`，传给 Vision 时 y 转为 `1 - y - height`。提取结果时做同样的 y 轴翻转。Python 对 `normalized=False` 的结果用整图宽高相乘，保留浮点数，不以 ROI 为新的坐标原点。局部 ROI、透明 BGRA 和 EXIF 方向仍需真实 fixture 验证。

每次识别创建新的 handler/request；`high_accuracy` 选择 accurate/fast。只有语言列表非空才设置 `recognitionLanguages`，只有 accurate 模式且词表非空才设置 `customWords`。未启用自动语言检测，未固定 request revision。语言查询采用 accurate 模式，不能据此推定 fast 的能力；Python 缓存返回同一个列表对象。

## 资源与线程

- Python 导出的 `Py_buffer` 借用输入内存，当前调用结束后释放；无拷贝 NSData/provider 不接管这块内存。调用期间必须保证数据存活且内容稳定。
- ARC 管理 Objective-C 对象；CF 的 create/copy 引用及 Python 引用仍需显式释放。当前正常路径有释放，错误路径和分配检查需按计划补齐；没有每调用的显式 autoreleasepool。
- `asyncio.to_thread` 仅将同步调用交给工作线程；当前原生调用没有显式释放 GIL，不能保证其它 Python 工作或事件循环持续运行。
- 取消 await 不等于终止已经启动的 Vision 请求；不能依赖超时/取消释放底层工作占用的资源。

## 当前行为与待集成修复

正常无文字会得到空列表，Python 还会过滤纯空白候选；但当前解码/图像创建/Vision/语言查询失败也可能得到空列表。语言查询失败的空列表还会被缓存。目前不能给用户承诺统一的异常类型或消息。

[接管计划](codex-takeover-plan-20261027.md)提出补齐参数、尺寸、ROI、字符串和分配检查，区分失败与合法空结果，完善清理并在合适区间释放 GIL。这些是待实现、待验证事项，不是本初稿已完成的行为。待调度方提供精确实现 SHA 后，再集成并对齐异常契约、线程说明和实测记录。

构建仅实现 Darwin；项目声明 macOS 13+/Python 3.11+，未显式固定 macOS deployment target。最低系统、x86_64、各 Python 版本及 wheel 覆盖不能由当前源码或单机结果推导。库不包含独立 OCR 模型或外部 OCR 服务，识别能力由系统 Vision 提供。
