# native_ocr_py 接管与最小修复计划

## 1. 基线、范围与证据等级

- 固定代码输入：`refs/heads/master@8846278eb4a173f01ddaf24c4c8dbf5c4ccc4ed1`。本方案只新增此文档，不修改实现、测试、构建或 Agent 指南。
- 已逐项阅读 README、CLAUDE、全部 Python API/types/stub、C/ObjC 桥接、setup.py、build.sh、pyproject、MANIFEST 和现有测试；下文行号均指该固定输入。
- **已确认的是源代码事实和文档冲突，不是运行时崩溃或 OCR 正确性。** 本轮未构建、未导入扩展、未执行 Python/原生测试，也未触发危险输入；所有运行时候选留给实现 Agent 验证。
- 只使用 Provider 独立 worktree；只允许仓库样例或临时生成图片，不截图、不操作桌面、不修改系统权限。不调用其他 Agent；本文件供上层调度使用。
- 保持 macOS 定位、公共函数名称/参数顺序/默认值、异步调用和 TypedDict 返回值；不做 Windows、无关重构、版本/依赖升级、发布工作流或默认分支更新。

## 2. 实际架构与支持边界

| 层 | 当前实现与边界 |
| --- | --- |
| Python 公共层 | `src/native_ocr/__init__.py:19` 缓存语言列表；`:28` 将 ROI 字典转四元组；`:34` 去除文本两端空白、过滤空串、按原图尺寸缩放坐标；`:59`、`:97` 用 `asyncio.to_thread` 调同步扩展。可选参数目前也允许位置传参，没有 keyword-only 的 `*`。 |
| 类型与原生入口 | `types.py:6`、`:25` 是 TypedDict，运行时结果是嵌套 dict；`_ocr_native.pyi` 仅供静态检查，不做运行时校验。`ext.c:5` 注册三个同步入口，实际参数处理都在 `apple_ocr.m`。 |
| 图像与 Vision | BGRA 路径用无拷贝 provider 构造 CGImage；编码图片用 ImageIO 解码第 0 帧。每次创建 Vision handler/request，accurate/fast 由 `high_accuracy` 选择，custom words 只在 accurate 下设置。原生返回文本与归一化矩形，编码路径额外返回解码尺寸。无外部 OCR 服务或自带模型。 |
| 坐标 | `apple_ocr.m:64` 把左上原点 ROI 转为 Vision 左下原点；`:38` 把结果转换回左上原点；像素输出在 Python 层乘整幅解码图像的宽高。公式本身未见静态反转错误，不应直接改写。ROI 后输出是否保持整图坐标需真实 fixture 验证。 |
| 构建与支持 | `setup.py:6` 只实现 Darwin，链接 Vision/Foundation/CoreGraphics/ImageIO，ObjC 使用 ARC；其它系统明确报错。构建后端是 setuptools，`build.sh` 执行 `uv sync`、`uv build`。CMake 仅作 IDE 索引，禁止用来构建。 |

README 声明 macOS 13+ / Python 3.11+；`.python-version:1` 为开发环境选择 3.14，并非提高公共最低版本。代码没有固定 `request.revision`，setup.py 也没有显式设置 macOS 13 deployment target；因此“固定 revision 3”“全部架构已验证”都不能宣称。本轮环境仅确认 macOS 26.6.2/arm64、uv 和 Xcode SDK 可用，**不构成最低系统、x86_64、Python 3.11 或原生功能验收**。

## 3. 关键候选与最小修复顺序

优先级表示后续处理顺序。P0 先堵住进程安全边界，再进入真实 Vision；P1 修复失败可观测性和异步资源边界；P2 仅核实并记录，避免扩张。

| 编号 / 优先级 | 固定输入中的具体依据与风险（均未动态复现） | 最小策略与回归入口 |
| --- | --- | --- |
| B1 / P0 参数解析 | `apple_ocr.m:120`、`:173` 忽略 `PyArg_ParseTuple` 返回值，失败后仍使用未完成初始化的变量；`:125`、`:178` 直接 `PyTuple_GET_ITEM`，未检查 ROI 类型/长度；`:11` 使用 `PyList_GET_SIZE`，`:15` 未检查 UTF-8 转换。错误参数数量、超出 C int 的尺寸、非 tuple ROI、非 list hints 或非 str 元素可能进入未定义行为/ObjC 异常，而不只是 Python 异常。 | 每个解析/转换失败立即返回 NULL；访问宏前校验容器和长度，逐项检查转换异常。原生入口必须自卫，不能仅靠 Python 包装或 `.pyi`。公共层不得用 `languages or []` / `custom_words or []` 将非法 falsy 值悄悄当作 None。两入口直接调用和公共异步调用都覆盖。 |
| B2 / P0 BGRA 范围 | `apple_ocr.m:134`–`:143` 从未比较 `bgra8_buf.len`；`width * height * 4`、`width * 4` 在转 size_t **之前**已按 int 运算。负值、短 buffer 和乘法溢出可能向 CoreGraphics 声明超出真实内存的长度；长 buffer 也不符合现有严格等长约定。 | 先验证正尺寸和可表示范围，使用经除法上界校验的 size_t/Py_ssize_t 乘法，再严格比较实际长度；检查 colorSpace/provider/image 创建结果，不把无效资源传给后续 API。解码路径 `:208`–`:209` 的 size_t → int 也应检查再缩窄，或用能容纳尺寸的 Python 整数构造。不要通过分配巨型图片测试上界。 |
| B3 / P1 ROI 与字符串 | `_parse_roi` 只按 key 取值；原生 `PyFloat_AsDouble` 后不检查异常、有限性或边界。`unpack_str_list:12` 无 malloc 检查，长度转 int 未限界；UTF-8 C 字符串路径还需检查孤立 surrogate 和内嵌 NUL 的处理。 | ROI 四项须为可接受数值且有限，满足 `x,y >= 0`、`width,height > 0`、`x+width,y+height <= 1`；不静默裁剪或调换坐标。保留合理整数坐标的使用，不无关收紧为只能传 float。检查分配/计数上界；非法字符串给 Python 异常，不截断或把 nil 放进 NSArray。异常类型见下节。 |
| B4 / P1 错误吞没 | `run_request:87`–`:89` 丢弃 NSError；语言查询 `:102`–`:104`、解码 `:194`–`:204` 和 BGRA 图像创建失败 `:148`–`:150` 都返回空列表。语言查询的失败空列表还可能被 `@cache` 长期保存。当前无法区分“成功但无文字”和“根本没识别成功”。 | 正常空白图仍返回 `[]`；参数、解码、OS/Vision 失败明确抛异常，缓存只保存成功结果。保留正常返回形状；这是**错误路径语义收紧**，需文档明确列出，不冒称完全无行为变化。真实 Vision 失败难稳定制造时，单测可模拟包装层异常传播，但不能称为原生错误路径实测。 |
| B5 / P1 资源、线程、GIL | 桥接没有 `@autoreleasepool` 或释放 GIL 的区段；Python `to_thread` 不等于 C 扩展自动让出 GIL。`:24`、`:39`、`:45`、`:107`–`:110` 等分配/追加返回值未检查。ARC 不负责 CF 对象或 Python 引用，现有正常路径有释放，但新增错误分支容易泄漏/重复释放。 | 建立每调用 autoreleasepool 和统一、可审计的成功/失败清理路径；检查 Python 分配、列表追加和 malloc，保留原始异常。先在持 GIL 状态完成参数校验、NSString/NSArray 构造与资源持有，仅在纯 Vision 阻塞调用区间释放 GIL，恢复后再访问 Python。ObjC 异常不得越过 Python 边界；释放 GIL 时需保证异常路径同样恢复线程状态。是否实际卡住事件循环、发生泄漏或崩溃尚待验证。 |
| B6 / P1 测试可信度 | `tests/test_ocr.py:4` 的模块级 importorskip 会将扩展缺失变成跳过；`:143` 的模块级 Pillow importorskip 还会影响本文件前面的非 BGRA 测试。部分坐标/类型测试在空列表上循环，可空通过。当前没有非法输入、异常或事件循环响应性测试。 | macOS 验收首先显式导入并确认加载的是当前 worktree 的 `.so`，扩展缺失必须失败；Pillow 仅对依赖它的 fixture/测试局部跳过。非空文字 fixture 先断言有结果，再检查内容/坐标。记录收集、通过、失败、跳过数量；只看 pytest 退出码不够。 |
| B7 / P2 待核实边界 | 编码路径 `:200`、`:210` 用 CGImage，不显式传 EXIF orientation；BGRA 设为 premultiplied-first，而测试 `:149`–`:153` 只交换 RGBA 通道；语言列表查询使用 accurate，不能推定 fast 支持同样的语言。 | 用方向标记 fixture、透明/不透明图和模式匹配的语言测试核实；本轮不预设已错，不自动增加方向参数、扩大格式承诺或更改默认识别算法。若未形成证据，文档说明现有限制并保留后续项。 |

### 兼容性与资源约束

1. 保持现有五个导出名称及嵌套 dict 结构，不为配合 README 改成 dataclass；不增加 keyword-only 限制，不改变空白过滤、坐标单位和结果顺序，不新增公开异常类。
2. 建议异常契约：参数类型/缺失字段等结构错误为 `TypeError`，非法尺寸/ROI/损坏编码内容为 `ValueError`，不可表示尺寸为 `OverflowError`，系统/Vision 失败为 `RuntimeError`，分配失败为 `MemoryError`；具体消息需携带操作和安全的错误原因，不包含原始图像内容。实现和文档用同一回归表对齐，不能依赖 SystemError 或进程信号作为合法结果。
3. 释放 GIL 前必须确保图像数据整个请求期间有效。`y*` 导出的 buffer 防止调整尺寸/销毁，**不防止其它线程修改内容**；若继续接受 bytearray/memoryview 等扩展层已可接收的输入，优先对可能变化的数据作快照，不能简单把现有可用输入全部拒绝。UTF-8 借用指针也不得在另一个线程修改 list 后悬空；先构造自持有的 Foundation 对象。
4. handler/request、无拷贝 NSData/CG provider 的生命周期必须在 buffer 释放前结束；pool 要覆盖实际工作线程的原生调用。每个 Py_buffer、malloc、CF 引用和 Python 引用在成功/失败出口各释放一次。不对 ARC 对象手动 release，不在无 GIL 区调用 Python C API。
5. 不为本轮引入全局锁、线程池重写或新配置开关。`get_supported_languages()` 的可变缓存列表当前按对象身份复用（测试 `:30`），本轮不要顺手改成复制或 tuple。

## 4. 文档修正清单

| 文档位置 | 必须修正或补充 |
| --- | --- |
| `README.md:44`、`:94`–`:116`、`:135` | dataclass/属性访问与 TypedDict 冲突：展示 TypedDict 定义和 `result["content"]`、`result["position"]["x"]`。`BoundingBox(...)` 构造写法可以保留，因为返回 dict；用仓库样例替代依赖用户截图的 quickstart。 |
| `README.md:60`、`:75` 与参数表 | 删除不符合实际签名的 `*`；说明 normalized 必填、ROI 永远归一化且左上原点、像素结果为 float/整图坐标、BGRA 无行填充且严格等长，并说明 alpha 约定。补充合法空结果、输入异常、Vision 失败和取消限制。 |
| `README.md:70`、`:89`、`_ocr_native.pyi:34` | `None = auto-detect` 无代码依据：实现只在 hints 非空时设置 recognitionLanguages，没有开启 automaticallyDetectsLanguage；SDK 默认该属性为 NO。本轮优先把说明改为“使用系统默认语言配置”，不偷偷改变识别默认值。`high_accuracy` 是 recognitionLevel，不等于代码显式执行多轮纠错。 |
| README 安装/平台、项目元数据 | 不再承诺 Windows 即将支持；pyproject description/keywords 去掉已实现 Windows 的暗示，不改版本号、依赖范围、Python pin 或无关 lock。README 的 PyPI/wheel 可用性本轮未核验，不能承诺双架构 wheel；区分源码构建要求、声明支持与实际已测平台。额外图像格式取决于系统 ImageIO；不要宣称逐一验证。 |
| `CLAUDE.md:79`–`:80` / 新 `AGENTS.md` | 删除“不检查解析返回值”“分配失败可忽略”等不安全建议；stub 绝不提供运行时安全。AGENTS 作为通用入口，CLAUDE 引用同一份规则，保留 uv/setup.py 与 CMake 仅索引的约束；代理仅对确需联网的单命令生效，不改全局配置。 |
| 新架构/开发指南 | 描述上节调用链、资源归属、GIL、支持边界、文件分工；给出构建→显式导入→分层测试→本地打包/安装验证命令。区分分发名 `native_ocr_py`、导入名 `native_ocr` 和扩展 `_ocr_native`；Pillow/pytest 仅为开发依赖。解释 build.sh 会清理构建目录，不引导发布或使用 CMake。 |

## 5. 后续验证矩阵（本轮全部 not_run）

按 T0→T4 执行，危险用例先隔离；测试产物留在当前 Agent worktree 或临时目录。不用用户原始 checkout，不操作屏幕。任何环境/系统限制单独记为 blocked 或未验证，不替换成通过。

| 阶段 | 执行方式与判据 |
| --- | --- |
| T0 构建与导入门禁 | 在固定代码基线上先 `uv sync --locked`，再 `uv run --no-sync setup.py build_ext --inplace`；执行 `uv run --no-sync python -c 'import native_ocr; import native_ocr._ocr_native as extension; print(native_ocr.__file__); print(extension.__file__)'`，核对真实扩展路径和当前 worktree。保存构建退出码、编译器/SDK、macOS、架构、Python 版本。失败即停，不能以 importorskip 代替。 |
| T1 纯包装层 | 新 `tests/test_api.py` 在扩展已可导入的前提下 monkeypatch 已绑定的 `_detect_image`/`_detect_bgra8`；验证 None/完整 ROI、空白过滤、TypedDict 键、精确归一化→像素缩放、位置参数兼容、异常透传及缓存。明确此层不是 Vision 验收。 |
| T2 原生安全回归 | 新 `tests/test_native_validation.py` 用 `sys.executable` 启子进程，设置 timeout、捕获返回码/异常名；覆盖两原生入口参数缺失/多余、错误 buffer、非 tuple/长度 0/3/5 ROI、非数值/NaN/Inf/越界 ROI、非 list hints、非 str/surrogate/NUL 元素。BGRA 覆盖零/负尺寸、短/长 buffer、`2**31` 解析边界、`(2**30, 1)` 和 `(65536, 65536)` 乘法边界，传 tiny buffer 而不是分配巨量内存。必须正常报告预期 Python 异常；信号终止、超时、SystemError 都算失败。先修 P0，再放行进主测试进程。 |
| T3 真实 Vision fixture | 先运行现有 `tests/test_ocr.py`（默认 `tests/sample.png`，已查文件元信息为 1280×720 RGBA PNG）；其中“恭喜获得”只是既有测试期望，本轮未认证正确。另用 Pillow 在 tmp_path 生成高对比不透明 PNG，文字如 `NATIVE OCR 4826`、`LOWER PANEL 7319` 分放不重叠上下区；保存文字源、字体/尺寸、布局、图片 SHA256。字体不存在则明确 blocked，不猜字。编码/BGRA 两路径真实调用，核对已知 token、空白图 `[]`、全图/局部 ROI 的包含与排除、上下位置、整图坐标及像素尺度。框只需落入预先设计的宽松文字区域，浮点换算用明确容差，不锁死系统 OCR 的逐像素框或完整排序。 |
| T3 模式/边界补充 | accurate/fast 与支持语言按真实能力分别测试，fast 不强行复用中文断言；custom words 的测试验证可用与无异常，不宣称一定改善识别。透明 BGRA 和 EXIF 方向图用于 B7 定性，缺证据则保留限制。不能只断言返回 list/非空，也不能凭图片观感或模型补全真实 OCR 输出。 |
| T4 线程/资源/构建边界 | 先静态核对所有引用和清理路径，再让多次真实 OCR 与事件循环 heartbeat 并行，记录调度进展/耗时，避免脆弱的固定加速倍数；覆盖取消 await 后线程仍可能继续及并发参数生命周期，不宣称强制取消 Vision。重复成功/异常调用观察内存趋势仅作线索，不凭单次 RSS 证明无泄漏。构建变更若必要，才用 `uv build` 并在临时 venv 安装本地 wheel/sdist 检查导入及 `.pyi`/`py.typed`/原生源文件打包；不上传、不运行发布流程。 |

实现 Agent 新增上述安全/包装测试后，先分别运行 `uv run --no-sync pytest tests/test_native_validation.py -v -ra`、`uv run --no-sync pytest tests/test_api.py -v -ra`，再执行 `uv run --no-sync pytest tests/test_ocr.py -v -ra`；提交前运行 `uv run --no-sync pytest -v -ra` 和 `git diff --check`。每项报告实际命令、退出码、连续输出、测试数和跳过原因。当前机器验证不替代 macOS 13/x86_64/Python 3.11 验证；没有对应环境就列为未验证，不能自行提升最低支持版本解决问题。

## 6. 无冲突文件级职责与交付顺序

以下是上层后续分工建议，**不是授权本规划 Agent 修改其它文件或调度 Agent**。每阶段选择明确的已发布 SHA，不用移动分支名替代固定依赖版本。

| 角色 | 独占文件 | 范围与交接 |
| --- | --- | --- |
| 规划 Agent（本轮） | `docs/codex-takeover-plan-20261027.md` | 固定证据与优先级；只向 `refs/heads/codex/provider-ocr-plan-20261027` 普通 push，不修改 master/main/tag/release。 |
| 文档 Agent（首轮） | `README.md`、新 `AGENTS.md`、`CLAUDE.md`、新 `docs/architecture.md`、新 `docs/development.md`、新 `examples/ocr_image.py`；`pyproject.toml` **仅** description/keywords | 修 TypedDict/签名/支持说明、移除不安全建议，提供只读仓库图片的示例，标记当前行为与拟修复行为，不提前声称 bug 已修。指南只链接此方案，不改本方案或实现/stub。 |
| 实现 Agent | `src/native_ocr/**`（包括 docstring/types/stub）、`native_code/osx/src/**`、`native_code/osx/include/**`、`tests/**`；必要时 `setup.py`、`build.sh`、`MANIFEST.in` | 按 B1/B2→B3/B4/B5/B6 顺序小步修复回归；B7 先核实。先不碰 pyproject/lock/CMake/README/AGENTS/CLAUDE/docs/examples，避免与文档 Agent 冲突。若实测确需 pyproject 的构建配置变更，由上层另行指定单一所有者，不能双方同时改文件。无证据不动构建。 |
| 文档 Agent（集成收尾） | 仍限其首轮文件 | 在上层指定集成分支整合实现 Agent **已发布且指定的 SHA** 后，再对齐异常、语言默认、BGRA、线程限制和已测环境；用当前代码实际跑示例/指南命令。不得在未集成代码的旧基线上编写“已通过”结论。 |
| 独立 review Agent | 默认只读；问题交还原所有者 | 用隔离 inspection worktree 检出上层指定的最终代码 SHA，独立复核 P0/P1、类型/API 兼容和文档示例，执行相应构建/回归并给精确命令与退出码；不能重置原会话 worktree 或把实现 Agent 日志当作独立验收。 |

收尾门槛：仅预定文件变更；原生导入不是 skip；危险用例子进程存活并抛正确异常；真实 fixture 的内容/坐标有可追溯预期；文档与集成代码一致；未复现/未测环境清楚保留。各 Agent 只推送上层另行授权的自身交付分支，不自行决定最终合并或发布。

## 7. 参考与本轮验证记录

- 仓库文件与上文固定行号是主要证据；本机只读取 SDK，不构成运行时验证。`Vision.framework/Headers/VNRequest.h` 定义左下原点 ROI；`VNObservation.h` 定义 boundingBox；`VNRecognizeTextRequest.h` 说明语言能力依 request 配置，自动语言检测默认 NO 且自 revision 3 才有效。当前代码没有启用它，因此应纠正文档而非推断默认会自动检测。
- [CPython 3.14 参数解析与 buffer 契约](https://docs.python.org/3.14/c-api/arg.html)：解析返回值和异常必须检查，`y*` 获取的 buffer 必须在处理结束及提前退出时释放；这也不意味着可以无 GIL 访问其它 Python 对象。其约束直接反驳 CLAUDE 中依赖 stub 保证安全的说法。
- [CPython 线程状态/GIL 官方入口](https://docs.python.org/3.14/c-api/init.html)：后续实现需按实际测试 Python 版本复核释放/恢复线程状态要求。Apple 在线页面本轮仅返回 JS 页面，正文读取未成功；上述 Vision 契约使用本机 Xcode SDK 头文件，不把网页不可读记为验证通过。
- 本轮完成静态审阅、支持环境元信息检查；构建、pytest、非法原生输入、真实 Vision/fixture、并发与内存测试均 **not_run**。方案交付另以实际 `git diff --check`、commit、push 和独立 `git ls-remote origin refs/heads/codex/provider-ocr-plan-20261027` 输出为凭；远端核验成功不代表 OCR 验收成功。
