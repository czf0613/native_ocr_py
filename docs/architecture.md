# 架构与边界

本说明已对齐实现提交 `dff3766418c20abf6b302c1656c6e55148af9b87`。各会话实测来源、已知误读及未验证项见[验证记录](validation-20261027.md)；[最初计划](codex-takeover-plan-20261027.md)保留为历史快照。

## 调用链与文件

```text
应用读取编码图片 / 提供 BGRA
  → native_ocr async API → asyncio.to_thread
  → _ocr_native 同步 C 入口（ext.c）
  → apple_ocr.m：校验、输入快照、ImageIO/CoreGraphics、Vision
  → tuple 列表 → Python 去空白/过滤空串/坐标缩放 → 嵌套 dict
```

`src/native_ocr/__init__.py` 导出 `BoundingBox`、`OcrResult`、`get_supported_languages` 和两个 async OCR 函数。`types.py` 定义 TypedDict，运行时为字典；`_ocr_native.pyi` 描述三个同步入口，不承担运行时校验。`setup.py` 通过 setuptools 构建 C/ObjC 扩展，启用 ARC/ARC 异常清理，链接 Vision、Foundation、CoreGraphics、ImageIO。CMake 只供索引。

## 图像与坐标

两种输入均先复制到自持有的 NSData。编码路径经 ImageIO 解码第 0 帧，读取整图尺寸，不显式传 EXIF orientation；可用格式由系统决定。BGRA 路径由快照建立 provider/CGImage，要求正尺寸、无行填充、严格等长、预乘 alpha 的 BGRA8；在乘法及长度比较前检查范围。

ROI 是左上原点的归一化矩形，默认全图。四项须可转数值且有限、尺寸为正且位于整图内，不自动裁剪。传给 Vision 的 y 为 `1 - (y + height)`，先求和避免底边浮点误差。Vision 结果按 ROI 换算为整图归一化坐标：

```text
x = roi.x + bbox.x * roi.width
y = roi.y + (1 - (bbox.y + bbox.height)) * roi.height
width  = bbox.width  * roi.width
height = bbox.height * roi.height
```

`normalized=False` 再由 Python 层用整图宽高相乘，返回值仍是 float。ROI 不建立新的输出原点。当前生成英文/中文图片测试覆盖整图坐标、ROI 包含/排除及像素换算；这是指定环境的测试证据，不是所有图像/系统的保证。

## 请求、错误与语言

每次识别创建 handler/request；`high_accuracy` 选择 accurate/fast，custom words 仅在 accurate 下设置。`languages=None` 被包装为 `[]`，原生仅在列表非空时设置语言；空列表使用系统默认配置，未启用自动语言检测，也未固定 request revision。accurate 的语言能力查询不能保证 fast 能力相同。

成功无文字仍返回空列表。错误处理区分类型/结构（TypeError）、非法值或解码失败（ValueError）、尺寸溢出（OverflowError）、系统/Vision/ObjC 失败（RuntimeError）及已检查的分配失败（MemoryError）；UTF-8 编码错误保留 UnicodeEncodeError。具体典型原因见 README，不承诺稳定的异常消息。

同步语言查询只缓存成功结果，异常不会被 `functools.cache` 缓存；缓存返回同一个可变列表，调用方不要修改。

## 所有权、GIL 与取消

- 解析失败立即返回，成功获取的 `Py_buffer` 在出口释放；数据始终复制，包括只读 memoryview 对可变底层内存的视图。提示词转换为拥有自身数据的 NSString/NSArray。
- 快照发生在原生工作线程处理输入时，不是 async 调用提交瞬间；调用方不要在工作线程尚未制作快照前修改共享输入。
- 每调用有 autoreleasepool。ARC 管 ObjC；CF create/copy 引用由 finally 清理，Python 分配/追加失败保持异常并释放已持引用。ObjC 异常在桥接边界转为 Python 异常。
- 仅 Vision `performRequests` 阶段释放 GIL，finally 恢复后才访问 Python。解析、快照、解码、语言查询等阶段仍持有 GIL；不承诺整个调用无阻塞或固定并发加速倍数。
- 取消 await 只取消等待，已经启动的 Vision 工作可继续；输入快照继续存活到原生请求清理。`asyncio.run` 关闭默认 executor 时可能等待该工作结束。

## 平台边界

仅实现 Darwin；声明 macOS 13+/Python 3.11+，实测 macOS 26.6.2 arm64/Python 3.14.7。setup.py 未显式固定 deployment target；本环境构建使用 11.0，语言 API availability 警告及 wheel 标签见验证记录，不能据此宣称支持 macOS 11。

未验证 macOS 13、x86_64、Python 3.11、free-threaded Python、EXIF 方向、透明 BGRA、内存耗尽及泄漏；无 Windows/Linux 实现或全格式承诺。OCR 不依赖外部服务或捆绑模型，识别结果随系统 Vision 能力而变。
