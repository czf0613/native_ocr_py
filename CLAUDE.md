# Claude 维护入口

本仓库所有 Agent 统一遵循 [AGENTS.md](AGENTS.md)。构建、验证命令见[开发指南](docs/development.md)，实现边界见[架构说明](docs/architecture.md)。

- 使用 uv 管理环境、通过 setuptools / `setup.py` 构建；CMake 仅用于索引。
- `.pyi` 和类型注解不能校验运行时输入。必须检查参数解析、数值转换、内存分配和系统调用失败，并正确清理资源。
- 当前代码风险与拟修复策略以[接管计划](docs/codex-takeover-plan-20261027.md)为准；不要把计划当作已完成的实现或验证。
- 本轮只在 Provider 会话 worktree 和获准的测试分支工作，不操作原始 checkout，不更新默认分支，不发布。
