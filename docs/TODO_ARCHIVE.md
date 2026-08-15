# North Agent TODO Archive

## 2026-07-22: Run-aware dual-threshold compaction

- [x] Replace repeated threshold-only summaries with checkpointed per-Run normal and emergency
  budgets, token-targeted retention, minimum-growth protection, atomic tool-call batches, and
  separate history/context token telemetry.

## 2026-07-22: Preserve ToolMessage presentation artifacts

- [x] Verify the canonical `RunExecutor` message stream preserves
  JSON-compatible `ToolMessage.artifact` independently from compact model-visible
  content, and document that hosts own validation and durable projection.

这份文件记录已经完成的 TODO。当前可执行任务请看 [TODO](./TODO.md)。

## Completed

### P0 主线闭环

- [x] T4. 改造 `present_files`，真正联动 `artifacts`
  目标：
  让 artifact 成为线程状态的一等数据，而不是只是给模型看的字符串。
  关联文件：
  `app/tools/builtin/present_files.py`
  `app/state.py`
  `app/client.py`
  `app/runtime.py`
  `tests/test_tools.py`
  `tests/test_app.py`
  完成标准：
  `ThreadState.artifacts` 被更新；`chat()` / `stream()` 都能拿到 artifact 结果；工具输出不再只是一段展示文本。

- [x] T5. 扩展 `AppClient.stream()` 事件协议
  目标：
  让流式输出不仅有 AI 文本，还能看到工具与状态变化。
  关联文件：
  `app/client.py`
  `app/state.py`
  `tests/test_app.py`
  完成标准：
  至少覆盖 `ai`、`tool`、`values`、`end`、`error`；artifact 相关状态变化对调用方可见。

### P1 支撑闭环

- [x] T6. 把线程路径模型真正接入输出链路
  目标：
  让 `ThreadPaths` 不只是静态路径定义，而是实际参与报告写出与 artifact 存放。
  关联文件：
  `app/threads/paths.py`
  `app/tools/builtin/present_files.py`
  `app/tools/builtin/write_report.py`
  `app/state.py`
  `tests/test_threads.py`
  完成标准：
  报告文件和 artifact 有稳定 thread 级位置；路径约定被测试覆盖。

- [x] T7. 明确 `ThreadState` 的最小更新约定
  目标：
  让后续 AI 清楚哪些字段是 runtime 主写、哪些字段是工具写入。
  关联文件：
  `app/state.py`
  `app/client.py`
  `app/runtime.py`
  `docs/LITE_ARCHITECTURE.md`
  完成标准：
  `artifacts`、`thread_data`、`uploaded_files` 的职责和更新来源有明确文档或代码约束。

- [x] T8. 以 DeerFlow 语义重建第一批 middleware
  目标：
  在不回退到 demo 语义的前提下，重建最小 runtime 保护层。
  关联文件：
  `app/agents/__init__.py`
  `app/agents/middlewares/__init__.py`
  `app/agents/middlewares/tool_error.py`
  `app/agents/middlewares/loop_detection.py`
  `app/agents/middlewares/clarification.py`
  `app/runtime.py`
  `tests/test_middlewares.py`
  完成标准：
  行为围绕真实工具失败、tool loop、clarification 恢复设计；确认语义成立后再默认启用。

### P2 下一阶段基础设施

- [x] T9. 引入最小 skill 系统
  目标：
  让 runtime 能向 agent 暴露可发现的 skill catalog，并通过懒加载读取具体 skill 内容，为后续文件分析、代码执行、报告生成等能力提供可复用装配层。
  关联文件：
  `app/config.py`
  `app/runtime.py`
  `app/agent.py`
  `app/client.py`
  `app/skills/__init__.py`
  `app/skills/loader.py`
  `app/cli.py`
  `app/tools/builtin/read_file.py`
  `tests/test_skills.py`
  `tests/test_app.py`
  `tests/test_agent.py`
  `tests/test_config.py`
  `tests/test_tools.py`
  `docs/architecture/runtime-boundaries.md`
  `docs/architecture/target-structure.md`
  `readme.md`
  完成标准：
  支持本地 `skills/<name>/SKILL.md`；agent 默认只拿到 skill catalog；具体正文通过 `read_file` + 资源 URI 按需读取；可通过配置或 CLI 过滤本轮可见 skill；默认不把 skill 正文直接注入上下文。

### P3 文件分析闭环

- [x] T10. 引入线程文件发现入口
  目标：
  让 agent 能发现当前 thread 内可读取的上传、工作区、输出和记忆文件，为文件分析闭环提供入口。
  关联文件：
  `app/tools/builtin/list_files.py`
  `app/tools/builtin/__init__.py`
  `app/tools/registry.py`
  `skills/file-analysis/SKILL.md`
  `skills/README.md`
  `tests/test_tools.py`
  `tests/test_skills.py`
  完成标准：
  `list_files` 返回可传给 `read_file` 的 resource URI；默认 skill catalog 暴露 `file-analysis`；测试覆盖文件发现、domain 过滤和 prompt catalog 行为。

- [x] T11. 接入最小上传链路
  目标：
  让 CLI / client 能把本地文件复制到 thread uploads，并把 `uploaded_files` 作为 runtime-owned state 暴露给 agent。
  关联文件：
  `app/threads/uploads.py`
  `app/threads/__init__.py`
  `app/client.py`
  `app/cli.py`
  `tests/test_threads.py`
  `tests/test_app.py`
  `docs/TODO.md`
  完成标准：
  `AppClient.chat()` / `AppClient.stream()` 支持 `files=`；CLI 支持 `--file`；上传文件落到 `.deerflow/threads/<thread_id>/uploads/`；初始 state 含 `uploaded_files`，消息中包含可读的 `upload://` URI。

- [x] T12. 让 CLI 显示 artifact 输出
  目标：
  让命令行入口能直接看到 `chat()` / `stream()` 返回的 artifact 列表，避免报告已经生成但用户不可见。
  关联文件：
  `app/cli.py`
  `tests/test_cli.py`
  `docs/TODO.md`
  `readme.md`
  完成标准：
  非流式响应打印 AI 文本后打印 `Artifacts:`；流式模式结束后打印最终 artifact 列表；测试覆盖空 artifact、非流式 artifact 和流式最终 artifact。

- [x] T14. 让 CLI 可选显示流式事件
  目标：
  让调研和文件分析任务在命令行里能看到工具调用与状态更新摘要，同时保持默认输出安静。
  关联文件：
  `app/cli.py`
  `tests/test_cli.py`
  `docs/TODO.md`
  `readme.md`
  完成标准：
  `--stream --show-events` 打印 tool / values / error 事件摘要；默认 `--stream` 仍只打印 AI 文本和最终 artifacts；测试覆盖事件格式化与 CLI 输出。

## Completed Stage Exit Criteria

- [x] Web 调研闭环已经跑通
- [x] artifact 输出已经打通
- [x] runtime 保护能力达到最小可用
- [x] 下一阶段可以自然扩到文件分析、代码执行、报告生成

### P0 Harness/App 架构收敛

- [x] H1. 固化 `packages/harness/north` 的公开边界
  目标：
  明确 `north` 的稳定公开接口，只把真正可复用的 harness 能力放进包里。
  完成标准：
  顶层导出按宿主入口、持久化、上下文和可观测性收敛，并由契约测试锁定。

- [x] H3. 分链迁移并删除兼容层
  目标：
  完成 Harness/App 分层迁移，不保留长期双实现。
  完成标准：
  `app/` 只保留示例 CLI；所有可复用实现均位于 `packages/harness/north/`。

- [x] H2. 去掉 `north` 对当前仓库固定路径的隐式依赖
  目标：
  让 `north` 不再把仓库根、skills 目录、thread 目录当成内部常量假设。
  关联文件：
  `app/cli.py`
  `packages/harness/north/config.py`
  `packages/harness/north/client.py`
  `packages/harness/north/threads/*`
  `packages/harness/north/resources.py`
  `packages/harness/north/tools/builtin/*`
  完成标准：
  `north` 的路径相关能力由显式配置或 runtime context 注入；宿主项目负责给默认值。

### P3 文件分析闭环

- [x] T13. 加端到端 smoke test
  目标：
  用一条测试证明当前用户入口能跑通上传、文件发现、文件读取、报告写出、artifact 暴露。
  完成标准：
  脚本化 Agent 通过真实文件组件验证 `files=` 上传到 `ChatResponse.artifacts` 的完整链路，
  不依赖真实模型或网络。

- [x] T15. 收敛文件分析 skill 的端到端说明
  目标：
  让 `file-analysis` skill 明确指导模型发现文件、读取相关内容、按需写报告并呈现 artifact。
  完成标准：
  Skill 覆盖上传、workspace、output、memory 资源，区分直接回答与持久报告，并声明文件内容不可信。

### P4 代码执行准备

- [x] T16. 定义代码执行前置边界
  目标：
  在真正引入执行能力前，明确最小输入、输出、Artifact、风险边界，避免直接做泛化 Sandbox。
  完成标准：
  文档定义受限 Python 闭环、Harness/宿主职责、安全不变量、暂不做事项，以及
  `upload://`、`workspace://`、`output://` 和 Artifact 的关系。

### P5 宿主上下文效率

- [x] T17. 支持 token-aware 上下文压缩触发器
  目标：
  让工具结果大小差异显著的宿主按近似 token 预算触发摘要，同时保留消息数硬上限。
  关联文件：
  `packages/harness/north/config.py`
  `packages/harness/north/agent.py`
  `tests/test_config.py`
  `tests/test_agent.py`
  `docs/architecture/thread-persistence.md`
  完成标准：
  宿主可同时配置 token 阈值和消息数阈值，North 使用 OR 语义触发 LangChain 安全压缩，
  且未配置 token 阈值的既有宿主行为不变。

- [x] T18. 支持宿主追加 Agent middleware
  目标：
  允许宿主添加领域级模型请求策略，同时保留 North 默认的澄清和运行时 middleware。
  关联文件：
  `packages/harness/north/agent.py`
  `tests/test_agent.py`
  完成标准：
  `additional_middlewares` 追加在 runtime 默认 middleware 之后，不改变显式
  `middlewares` 覆盖入口，也不要求宿主复制 North 的默认装配。

### P6 宿主委派能力

- [x] S6. 最小 Subagent 委派契约
  目标：
  由 Lexora 的法律 Supervisor 需求验证产品无关的有界 Subagent 执行边界。
  关联文件：
  `packages/harness/north/subagents.py`
  `packages/harness/north/agent.py`
  `packages/harness/north/runtime/events.py`
  `packages/harness/north/__init__.py`
  `tests/test_subagents.py`
  `tests/test_agent.py`
  `docs/architecture/subagents.md`
  完成标准：
  `SubagentSpec` 声明独立 prompt、显式 Tools、Skills、结果 schema、超时和 recursion limit；
  `build_agent` 将无 Checkpointer 的专业 Agent 暴露为委派工具，并在父 Run callbacks、context
  和取消链中以 `subagent:<name>` 标记模型调用。第一版不支持嵌套或业务记忆。
