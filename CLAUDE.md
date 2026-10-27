# Claude 维护入口

本仓库所有 Agent 统一遵循 [AGENTS.md](AGENTS.md)。构建、验证命令见[开发指南](docs/development.md)，实现边界见[架构说明](docs/architecture.md)。

- 使用 uv 管理环境、通过 setuptools / `setup.py` 构建；CMake 仅用于索引。
- `.pyi` 和类型注解不能校验运行时输入。必须检查参数解析、数值转换、内存分配和系统调用失败，并正确清理资源。
- 当前行为见 README 和架构说明，历史方案见[接管计划](docs/codex-takeover-plan-20261027.md)，证据及未验证边界见[验证记录](docs/validation-20261027.md)。不要把计划或其它会话报告冒充本轮亲测。
- 遵守当前用户指定的工作目录、文件范围、协作和分支/发布授权；一次性限制记录在带日期的文档中。
