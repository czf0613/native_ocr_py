# Agent 接管入口

先读 [README.md](README.md)、[架构说明](docs/architecture.md)、[开发指南](docs/development.md)及[本轮接管计划](docs/codex-takeover-plan-20261027.md)。用户指令优先于旧指南；修复有证据的安全问题，不沿用忽略解析/分配错误的旧建议。

## 工作边界

- 只操作本会话的 Provider worktree，保留已有结果及无关改动；不 reset/clean，不访问或修改原始 `/Users/czf/Desktop/utils/native_ocr_py` checkout。
- 集成调度方指定的精确提交，不以移动分支最新值代替，不修改 Provider 私有 ref。未经明确授权不启动其他 Agent。
- 本轮只向各角色获准的测试分支普通 push；文档角色唯一输出为 `codex/provider-ocr-takeover-20261027`。不修改/推送 master、main 或默认分支，不 force push、打 tag、建 release 或运行发布工作流，不自行追加最终合并。
- 文档首轮仅改 README、AGENTS、CLAUDE、architecture/development 文档、文件输入示例，以及 pyproject 的 description/keywords；不改方案、实现、stub、tests、构建或 lock。实现集成必须等待调度方给出精确已发布 SHA。
- 只用仓库样例、临时生成图片或用户明确提供的图片；不截图、不操作桌面、不修改系统权限。不读取、打印或提交凭据。
- 不升级依赖、版本或 Python pin，不改全局配置。若确需联网代理，只给单条命令设置环境变量。

## 构建与验证

- 项目操作使用 `uv`；保持锁定环境，使用 setuptools / `setup.py` 构建扩展，CMake **仅用于 IDE 索引**，不用于构建或安装。
- 原生验收先显式导入并核对扩展来自当前 worktree，不能把 `importorskip` 当成功。危险非法输入回归应在子进程隔离并设超时。
- 按改动运行相关检查；涉及实现的收尾执行完整测试，记录通过/失败/跳过数量及原因。文档首轮仅做语法和一致性检查，无需重复原生构建。
- 提交前执行 `git diff --check`，核对文件范围。提交后普通 push 至唯一获准分支，再单独执行 `git ls-remote origin refs/heads/<branch>` 核验。
- 报告实际命令、退出码和连续输出证据；未执行项目标记 `not_run`，静态审阅、计划和其它 Agent 的记录不等于运行时验收。

## 实现约束

- 保持公开函数名称、参数顺序/默认值、位置传参兼容及 TypedDict/嵌套 dict 结果；不以文档修正为由改变 API。
- C 入口独立检查 `PyArg_ParseTuple`、容器类型/长度、数值转换和溢出。检查每个可失败的 Python 分配、列表操作、malloc 和系统调用，保留异常并完整清理；stub 不提供运行时安全。
- ARC 不代管 CF 引用或 Python 引用；每个 buffer/CF/Python 引用在成功与失败路径各释放一次。释放 GIL 的区间不得调用 Python C API，且需先保证输入和原生对象生命周期稳定。
- 无 GIL 工作不代表可强制取消原生请求；不预先宣称错误语义、线程响应性或资源问题已修复。
- Python 合并同模块导入；C/ObjC 控制流始终加花括号。原生入口注解和说明维护于 `.pyi`，方法表 `ml_doc` 使用 `NULL`。
