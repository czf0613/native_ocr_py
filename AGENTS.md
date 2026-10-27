# Agent 维护入口

先读 [README.md](README.md)、[架构说明](docs/architecture.md)和[开发指南](docs/development.md)。带日期的方案与验证文档保留各轮范围和证据，不能替代当前用户授权。

## 代码地图

| 路径 | 职责 |
| --- | --- |
| `src/native_ocr/__init__.py` | 公共 async API、ROI 字典解析、结果清理/缩放、语言缓存。 |
| `src/native_ocr/types.py` / `_ocr_native.pyi` | TypedDict 及同步扩展入口的静态接口。 |
| `native_code/osx/src/ext.c` / `apple_ocr.m` | C 模块注册、输入校验、图像与 Vision、原生资源管理。 |
| `setup.py` / `pyproject.toml` | setuptools 扩展构建及项目元数据。 |
| `tests/` / `examples/ocr_image.py` | 分层回归与文件输入示例。 |

## 构建与验证

项目操作使用 uv，保持锁定依赖；未经授权不升级版本、依赖或 Python pin。构建使用 setuptools / `setup.py`；CMake **仅供 IDE 索引**，不用于构建或安装。

```bash
uv sync --locked
uv run --no-sync python setup.py build_ext --inplace
uv run --no-sync python -c 'import native_ocr; import native_ocr._ocr_native as ext; print(native_ocr.__file__); print(ext.__file__)'
uv run --no-sync pytest -v -ra
git diff --check
```

先核对导入路径属于当前 checkout，不能将扩展缺失或 skip 当作验收通过。按改动选择相关检查，涉及原生实现时执行完整回归；只有文档变动时可做语法、一致性和示例检查，不必重复已确认代码的完整矩阵。危险原生输入用子进程隔离并设超时；信号终止、超时、SystemError 都不是合法异常结果。

## API 与原生安全

- 保持公共名称、参数顺序/默认值、位置传参兼容和 TypedDict/嵌套 dict 结构；API 行为变化需明确说明并覆盖回归。
- `.pyi` 不提供运行时校验。原生入口必须检查参数解析、容器类型/长度、数值转换、溢出、Python 分配/列表操作和系统调用失败，保留有效异常并清理资源。
- ARC 不代管 CF/Python 引用。每个 buffer/CF/Python 引用在成功和失败出口各释放一次；每调用的 autoreleasepool 覆盖工作线程上的原生对象。
- 释放 GIL 前先持有稳定的输入快照和原生对象；无 GIL 区不调用 Python C API，异常路径也必须恢复 GIL。取消 await 不等于终止原生工作。
- Python 合并同模块导入，C/ObjC 控制流加花括号；同步入口说明和注解维护于 `.pyi`，C 方法表 `ml_doc` 使用 `NULL`。

## 工作与证据

- 保留无关改动，不覆盖他人工作；遵守当前任务的目录、文件、分支、协作和权限限制。指定了精确依赖 SHA 时不要用移动分支最新值替代。
- 使用获准样例或临时生成的可追溯 fixture，避免自行读取用户私有图片、采集屏幕或更改系统权限；不读取、打印或提交凭据。代理仅对确需联网的单条命令生效，不改全局配置。
- 提交、push、默认分支更新、tag/release 和包发布均须符合当前用户授权；完成实现不自动授予额外发布权限。发布分支后用单独的 `git ls-remote origin refs/heads/<branch>` 核验精确远端 SHA。
- 记录实际命令、退出码、连续输出及通过/失败/xfail/skip 数量。未执行项目标为 `not_run`；注明外部报告来源，不把其它会话或静态审阅冒充本轮亲测。
