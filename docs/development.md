# 开发与验证

统一约束见 [AGENTS.md](../AGENTS.md)，当前实测状态见[验证记录](validation-20261027.md)。使用 uv、setuptools 和已安装的 macOS SDK；不通过 CMake 构建，不擅自更改依赖、Python pin 或全局配置。

## 从 checkout 到示例

新 checkout 可按以下步骤建立工作分支；先将 `selected_sha` 替换为当前任务选定的完整提交。已有 checkout 应保留当前工作并按任务要求集成，不重新初始化。

```bash
git clone --no-checkout https://github.com/czf0613/native_ocr_py.git
cd native_ocr_py
selected_sha="替换为已选定的完整提交SHA"
git switch --create my-ocr-work "$selected_sha"
```

从仓库根目录执行：

```bash
uv sync --locked
uv run --no-sync python setup.py build_ext --inplace
uv run --no-sync python -c 'import native_ocr; import native_ocr._ocr_native as ext; print(native_ocr.__file__); print(ext.__file__)'
uv run --no-sync python examples/ocr_image.py --help
uv run --no-sync python examples/ocr_image.py tests/sample.png --language zh-Hans
uv run --no-sync python examples/ocr_image.py tests/sample.png --language zh-Hans --pixels
```

确认 Python 模块和 `.so` 均来自当前 checkout；导入失败先停止验收。分发名是 `native_ocr_py`、导入名是 `native_ocr`。运行时无第三方 Python 依赖，pytest、pytest-asyncio、Pillow 属于锁定开发环境。

示例只读取指定文件并打印真实结果；也可使用用户明确提供的图片。`--language` 可重复；不传时使用系统默认配置，不是自动检测。原样例正确标题“恭喜获得”在当前系统误读为“恭喜荻得。”，示例正常退出不代表识别准确。

`build.sh` 会清理 `build/`、`dist/`、`src/native_ocr_py.egg-info/`，再执行 `uv sync` 和 `uv build`。需要保留已有构建产物或锁定环境时，使用上面的独立步骤。编译警告和最低平台验证必须单独记录，不自行抬高/降低支持声明。

## 分层测试

先完成显式导入门禁，然后按改动选择相关测试；原生实现收尾执行完整回归：

```bash
uv run --no-sync pytest tests/test_api.py -v -ra
uv run --no-sync pytest tests/test_native_validation.py tests/test_native_lifecycle.py -v -ra
uv run --no-sync pytest tests/test_vision.py tests/test_ocr.py -v -ra
uv run --no-sync pytest -v -ra
```

| 层 | 验证范围 |
| --- | --- |
| `test_api.py` | 包装层位置参数、结果清理/缩放、异常传播和缓存；mock 不构成 Vision 验收。 |
| `test_native_validation.py` | 子进程隔离非法参数、尺寸、ROI、字符串等；崩溃/超时/SystemError 是失败。 |
| `test_native_lifecycle.py` | 临时测试 dylib 注入 NSError/NSException、GIL 屏障、可变输入快照及取消生命周期；不应链接进生产扩展。 |
| `test_vision.py` | 临时绘制已知英文/中文、不透明图，验证编码/BGRA、语言、ROI、坐标与事件循环进展。 |
| `test_ocr.py` | 仓库 sample 回归，四项精确标题测试仅对已知“恭喜荻得”误读 xfail，保留正确预期。 |

`conftest.py` 强制扩展来自当前 checkout。Pillow 跳过仅限依赖它的测试/fixture，但验收仍需报告实际 skip；本次实现报告为 193 passed、4 xfailed、0 skipped，xfail 不能算 passed。本轮文档整合不重复完整矩阵。

## 本地 wheel/sdist 验证

使用已同步环境，离线构建并检查本地产物，不上传：

```bash
uv build --no-build-isolation --offline
mkdir -p build/documentation-tmp
TMPDIR="$PWD/build/documentation-tmp" uv run --no-sync python tests/check_distribution.py
```

脚本要求 `dist/` 恰有一个 wheel 和一个 sdist，若有多份先人工确认，不盲目删除；可通过 `uv build --out-dir <目录>` 保留旧产物，但脚本固定读取 `dist/`。脚本检查 wheel 的 `.pyi`/`py.typed`/`.so` 及 sdist 的原生源文件，在临时 venv 中只安装本地 wheel，隔离导入并验证语言查询和损坏图片异常。**它没有另行从 sdist 安装测试**，不能报告为两种产物安装均通过。

若离线构建依赖不可用，记录缺失项；不要升级锁定依赖或将降级方案写成通过。生成的 wheel 标签反映本机工具链配置，不能证明最低系统/其它架构可用，也不等于 PyPI 已发布。

## 交付证据

```bash
git diff --check
git status --short
```

核对当前任务的文件范围和获准分支，再执行获准的 commit/push；远端核验单独执行 `git ls-remote origin refs/heads/<获准分支>`。记录实际命令、退出码、连续输出及通过/失败/xfail/skip 数量；区分亲测、外部报告和未验证项。一次性接管约束与本轮结果放在[带日期的记录](validation-20261027.md)。
