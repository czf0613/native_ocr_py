# 2026-10-27 接管整合与验证记录

## 版本、范围与证据来源

| 项目 | 固定版本/来源 |
| --- | --- |
| 初始代码基线 | `8846278eb4a173f01ddaf24c4c8dbf5c4ccc4ed1` |
| 历史计划输入 | `819f41413f22812eb25c64c0efd04cad0d5b3107`，见[接管计划](codex-takeover-plan-20261027.md)；计划内“未执行”仅指当时阶段。 |
| 已发布文档初稿 | `cadea392f51d2376aafc3f42802c870d4f048734` |
| 本轮实现输入 | `dff3766418c20abf6b302c1656c6e55148af9b87`，`refs/heads/codex/provider-ocr-fixes-20261027` |
| 本轮集成 | 在文档分支普通 merge 精确实现 SHA，保留初稿历史；最终提交 SHA 见交付回执。 |

本次一次性授权仅限当前会话 worktree，保持原始 checkout 不动；不 reset/clean、不采集屏幕、不操作桌面/系统权限，不读取或输出凭据，不启动其它 Agent。实现及测试文件归实现角色，本轮文档角色只调整 README/AGENTS/CLAUDE、docs、文件输入示例，以及 pyproject 的 description/keywords；不更改源码、测试、构建、依赖、版本或 Python pin。

唯一交付分支为 `refs/heads/codex/provider-ocr-takeover-20261027`，普通 push，不创建 PR，不更新 master/main/默认分支，不 force push、打 tag、建 release 或运行发布工作流。这些是本轮限制，长期维护规则见 [AGENTS.md](../AGENTS.md)。

下文明确分开：本轮文档会话亲测、实现 Agent 报告、协调器转述的独立审查。外部结果不填作本轮亲测通过。

## 实现结果（来源：实现 Agent，经协调器提供）

实测 macOS 26.6.2 / arm64 / Python 3.14.7，共 **197 项：193 passed、4 xfailed、0 skipped**。文档整合没有重复该完整矩阵。复现入口见[开发指南](development.md)：

```bash
uv sync --locked
uv run --no-sync python setup.py build_ext --inplace
uv run --no-sync pytest tests/test_api.py -v -ra
uv run --no-sync pytest tests/test_native_validation.py tests/test_native_lifecycle.py -v -ra
uv run --no-sync pytest tests/test_vision.py tests/test_ocr.py -v -ra
uv run --no-sync pytest -v -ra
```

| 证据 | 报告状态及边界 |
| --- | --- |
| 旧基线无参数 `detect_image()` | 隔离子进程崩溃，返回码 `-11`；不是合法 Python 异常。当前参数解析已修复并有子进程回归。本轮未重跑危险旧基线。 |
| 旧基线损坏编码图 | 静默返回 `([], 0, 0)`；当前改为 ValueError，正常无文字仍为空列表。 |
| 类型/尺寸/ROI/字符串 | 已补齐原生输入、等长/乘法范围、有限 ROI、NUL/UTF-8 和分配检查；公共位置参数、默认值和 dict 结构保留。 |
| ROI | 实测证明需将 Vision 局部结果换算回整图；当前代码已换算。英文/中文生成 fixture 的编码/BGRA、语言及 ROI 测试通过，不能沿用历史计划中“公式未见错误”作为最终结论。 |
| 线程/生命周期 | 原生制作输入/提示词快照，在 Vision 调用区间释放并恢复 GIL；NSError/NSException 注入、并发、可变输入和取消后继续执行的生命周期回归通过。取消 await 不会强制终止 Vision。 |
| 资源 | 已增加 pool、失败检查及清理；这不等于做过内存耗尽或证明无泄漏。 |

## 原样例准确性：四项仍为 xfail

`tests/sample.png` 为 1280×720 PNG，标题正确字是 **“恭喜获得”**（协调器依据仓库原图核对），不能将 OCR 误读改作正确预期。

- 系统默认语言未正确识别标题。
- 显式 `['zh-Hans']` 和 `['zh-Hans', 'en-US']` 均观测到“恭喜荻得”（本轮示例输出含末尾句号“恭喜荻得。”）。
- 四项是编码/BGRA 两路径 × 两组语言提示的精确标题断言；仅遇到已知“恭喜荻得”且无正确标题时调用 xfail。缺失结果、其它错误或绑定异常仍会失败；正确标题才通过。
- **4 xfailed 不是 4 passed，原样例精确标题未通过。** 生成中文 fixture 的成功是另一组证据，不能覆盖此问题。

复现文件示例（读取仓库图，不截图）：

```bash
uv run --no-sync python examples/ocr_image.py tests/sample.png
uv run --no-sync python examples/ocr_image.py tests/sample.png --language zh-Hans
uv run --no-sync python examples/ocr_image.py tests/sample.png --language zh-Hans --pixels
uv run --no-sync python examples/ocr_image.py tests/sample.png --language zh-Hans --language en-US
```

本轮亲测前三条，均退出 0；默认返回 7 条，显式中文两条路径各 15 条。中文标题归一化框约为 `(0.415625, 0.261111, 0.2078125, 0.0694444)`；像素框约为 `(532, 188, 266, 50)`，数值仍为 float。退出 0 只证明示例执行完成，不是文字准确性通过；双语言结果来源为实现 Agent 报告。

## 可追溯 fixture

生成代码在 `tests/conftest.py`，1200×800 RGB、白底黑字、不透明，坐标为绘制起点：

| 图 | 字体与字号 | 绘制内容及位置 | PNG SHA256 |
| --- | --- | --- | --- |
| 英文 | `/System/Library/Fonts/Helvetica.ttc`，64 | `NATIVE OCR 4826` 于 `(100,130)`；`LOWER PANEL 7319` 于 `(100,550)` | `2db818de5f0db674cbf0a69b8b156d7bb1880d5eeb450bf7930332f2473ebc43` |
| 中文 | `/System/Library/Fonts/STHeiti Medium.ttc`，74 | `恭喜获得` 于 `(100,130)`；`下方区域 7319` 于 `(100,550)` | `cc82c0106bc5def31b3d92d519264f15b861aaca2ba75282d48c77e1a77e0877` |
| 仓库 sample | 现有文件，未重绘 | 正确标题 `恭喜获得`，与生成图分开 | `6555c2200cea493b6b127de909cd82671bd372e21f8874253bd742b598ce4dd0` |

以上哈希由本文档会话使用已有生成函数在本 worktree 重建/计算；只重建图像，没有重复其 OCR 测试。字体或 Pillow/系统变化可能改变 PNG 哈希，应重新保存元数据，不能复用旧哈希冒充新图。

可复现重建命令（使用已锁定的 Pillow 12.2.0）：

```bash
uv run --no-sync python - <<'PY'
from pathlib import Path
import hashlib
import runpy

namespace = runpy.run_path('tests/conftest.py')
class LocalFixturePaths:
    def mktemp(self, name):
        path = Path('build/documentation-fixtures') / name
        path.mkdir(parents=True, exist_ok=True)
        return path

factory = LocalFixturePaths()
for name, font, size, lines in [
    ('vision-text', '/System/Library/Fonts/Helvetica.ttc', 64,
     [('NATIVE OCR 4826', (100, 130)), ('LOWER PANEL 7319', (100, 550))]),
    ('vision-chinese', '/System/Library/Fonts/STHeiti Medium.ttc', 74,
     [('恭喜获得', (100, 130)), ('下方区域 7319', (100, 550))]),
]:
    namespace['_make_text_fixture'](factory, name, font, size, lines)
print('sample.png SHA256:', hashlib.sha256(Path('tests/sample.png').read_bytes()).hexdigest())
print('Fixture recreation only; no OCR tests executed')
PY
```

## 本轮文档会话亲测

环境读取为 `26.6.2 arm64 3.14.7`，Python 包和原生 `.so` 都从当前 worktree 的 `src/native_ocr` 加载，解释器来自本 worktree 的 `.venv`。

| 命令/检查 | 本轮状态 |
| --- | --- |
| `git fetch origin dff3766418c20abf6b302c1656c6e55148af9b87` 后 `git rev-parse FETCH_HEAD` | 与 Provider 固定输入一致；初始会话无 FETCH_HEAD，按精确 SHA fetch 后核实，不取移动分支最新值。 |
| `git merge --no-edit dff3766418c20abf6b302c1656c6e55148af9b87` | 普通 merge 成功，保留文档初稿历史。 |
| `uv sync --locked` | 成功，未修改依赖声明或 lock。 |
| `uv run --no-sync python setup.py build_ext --inplace` | 成功，有下述 availability 警告。 |
| `uv run --no-sync python examples/ocr_image.py --help` | 成功，无需读取图片。 |
| 上述默认/中文/中文像素三条真实示例 | 正常完成；已知标题误读如上，不能算准确性通过。 |
| `uv build --no-build-isolation --offline` | 本地 wheel/sdist 构建成功，未上传。 |
| `TMPDIR="$PWD/build/documentation-tmp" uv run --no-sync python tests/check_distribution.py` | 本地 wheel 安装/隔离导入、语言查询、损坏编码异常及 wheel 类型文件/sdist 原生源检查通过；未另行安装 sdist。临时目录需先 `mkdir -p build/documentation-tmp`。 |
| 文档/示例语法、API 签名、TypedDict、链接/命令语法与 AGENTS 可移植性 | 检查通过；源码签名与字段逐项比较，不导入替代实现。 |
| 源码/测试/构建/lock/历史计划与精确实现输入比较 | 无差异；文档和元数据改动仅限获准范围。 |
| `git diff --check` | 通过。 |
| 完整 pytest 矩阵 | `not_run`；按调度要求不重复，不能填作本轮亲测通过。 |

本地构建产物为 `dist/native_ocr_py-0.0.2.tar.gz` 和 `dist/native_ocr_py-0.0.2-cp314-cp314-macosx_11_0_arm64.whl`。编译实见 `-mmacosx-version-min=11.0`，并报告：

```text
warning: 'supportedRecognitionLanguagesAndReturnError:' is only available on macOS 12.0 or newer [-Wunguarded-availability-new]
```

SDK note 明示该 API 自 macOS 12 引入，而 deployment target 为 11.0。setup.py 未显式固定 target；当前 Python/工具链默认值和 wheel 的 `macosx_11_0_arm64` 标签不是 macOS 11/12 支持证明。本轮不修改构建文件，也不扩张 macOS 13+ 的原声明；最低系统仍未验证。

## 独立代码复核（来源：协调器转述的独立审查会话）

独立代码审查 `run_46e2e94fde4b4e1592d680722f6e79cc` 已完成，状态 `completed/done/no_changes`，`error=null`；精确输入为 `dff3766418c20abf6b302c1656c6e55148af9b87`，报告相对基线无新增可行动问题。以下是该会话结果，**不是本文档会话执行的检查**：

- 隔离 worktree 构建并实际加载自己的扩展；`uv run --locked pytest -q -ra`：**193 passed、4 xfailed、0 skipped，16.29s**。
- 本地 wheel/sdist 及安装导入检查通过；真实 Vision ROI 与绘制字形位置独立对照通过，PNG SHA 与原记录一致。
- xfail 边界探针确认：空结果、其它标题错误均失败，仅“恭喜荻得”走 xfail，“恭喜获得”通过。
- `nm`/`otool` 核对生产扩展没有测试注入符号或测试 dylib 依赖。

该独立审查覆盖指定实现 SHA，**最终整合文档仍待后续复核**，不能宣称所有整合验收已通过。

## 未验证与后续边界

macOS 13、x86_64、Python 3.11、free-threaded Python、EXIF 方向、透明 BGRA、真实内存耗尽及内存泄漏均未验证。未逐一验证全部 ImageIO 格式、最低系统可用性、其它 wheel 架构或 PyPI 发布状态；不承诺 Windows/Linux。原样例标题误读仍存在，不能通过改预期或合并 xfail 数量掩盖。
