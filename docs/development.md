# 开发与验证

从当前 Provider 会话 worktree 根目录执行命令，先遵循 [AGENTS.md](../AGENTS.md)。使用 uv、setuptools 和已安装的 macOS SDK；不升级依赖、不改 Python pin/lock，也不改全局代理或系统权限。CMake 只作索引。

**本轮记录：**文档初稿仅做语法与源码一致性检查；以下构建、导入、pytest、真实 OCR、打包与安装命令均未在本轮执行，不代表验收通过。

## 构建与导入门禁

```bash
uv sync --locked
uv run --no-sync python setup.py build_ext --inplace
uv run --no-sync python -c 'import native_ocr; import native_ocr._ocr_native as ext; print(native_ocr.__file__); print(ext.__file__)'
```

确认两个路径都属于当前 worktree；导入失败就停止原生验收，不能用跳过测试代替。分发名 `native_ocr_py` 与导入名 `native_ocr` 不同。运行时没有第三方 Python 依赖；pytest、pytest-asyncio、Pillow 属于开发依赖。

`build.sh` 会清理 `build/`、`dist/`、`src/native_ocr_py.egg-info/`，再执行 `uv sync` 和 `uv build`。它不是保留所有构建产物的命令；本轮不运行该脚本，锁定环境使用上述步骤。

## 分层验证

当前已有原生测试：

```bash
uv run --no-sync pytest tests/test_ocr.py -v -ra
```

现有文件用模块级 `importorskip` 导入扩展和 Pillow，扩展缺失或 Pillow 缺失可能使整文件跳过；部分断言还可能在空结果上循环而空通过。先完成导入门禁，保存收集/通过/失败/跳过数和原因，真实文字测试必须先断言非空并核对已知内容。

实现修复合入后，核实计划中的测试文件实际存在，再分别执行：

```bash
uv run --no-sync pytest tests/test_native_validation.py -v -ra
uv run --no-sync pytest tests/test_api.py -v -ra
uv run --no-sync pytest tests/test_ocr.py -v -ra
uv run --no-sync pytest -v -ra
```

`test_native_validation.py` 和 `test_api.py` 是计划新增项，固定输入中尚不存在。非法原生输入须先修复 P0 再用子进程隔离、设置超时；信号终止、超时、SystemError 不能当作预期异常。包装层 mock 不证明真实 Vision 行为；内容/坐标和事件循环响应性需真实 fixture，详见[验证矩阵](codex-takeover-plan-20261027.md)。

只使用仓库样例、临时生成图片或用户明确提供图片，不截图、不操作桌面。可运行文件输入示例：

```bash
uv run --no-sync python examples/ocr_image.py tests/sample.png --language zh-Hans
uv run --no-sync python examples/ocr_image.py tests/sample.png --pixels
```

示例打印真实结果；不以预写文本代替 OCR，不将 `[]` 自动判为成功。取消等待不能可靠终止已经开始的原生识别。

## 本地打包和安装验证（需要时）

仅本地构建，不上传、不执行仓库发布工作流：

```bash
uv build --no-sources
```

分别在临时环境验证本地 wheel 和 sdist。以下每次只选择一个实际生成的文件，手动替换路径，不假定架构或文件名：

```bash
artifact_path="/absolute/path/to/one-local-artifact.whl"
verify_root=$(mktemp -d)
uv venv "$verify_root/venv"
uv pip install --python "$verify_root/venv/bin/python" "$artifact_path"
(cd "$verify_root" && uv run --no-project --no-sync --python "$verify_root/venv/bin/python" python -c 'import native_ocr; import native_ocr._ocr_native as ext; print(native_ocr.__file__); print(ext.__file__)')
```

验证 sdist 时用新的临时环境，将 `artifact_path` 换成实际 `.tar.gz`。确认导入来自临时环境而非源码目录，检查 wheel 含 `.pyi`/`py.typed`，sdist 含原生源文件；记录 SDK、系统、CPU、Python 和构建产物信息。构建隔离可能按现有范围获取构建依赖，不修改项目的依赖声明或锁文件。打包/安装成功也不替代真实 OCR 或其它平台验收。

## 提交与交付

文档首轮可用 Python `ast.parse` 检查示例/代码块、`tomllib` 核对元数据与源码签名，不需导入原生扩展。提交前执行：

```bash
git diff --check
git status --short
```

逐项核对角色文件范围，提交并普通 push 到获准测试分支；随后单独运行 `git ls-remote origin refs/heads/<获准分支>`，记录远端完整 SHA。文档角色本轮仅交付 `codex/provider-ocr-takeover-20261027`，不创建 PR，不更新默认分支、tag 或 release。
