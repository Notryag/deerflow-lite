# Runtime Boundaries

## 当前代码的正确定位

当前代码已经有了正确骨架：

- `packages/harness/north/config.py`
- `packages/harness/north/state.py`
- `packages/harness/north/agent.py`
- `packages/harness/north/runtime/`
- `packages/harness/north/client.py`
- `packages/harness/north/checkpointer.py`
- `app/cli.py`

问题不在于“缺更多模块”，而在于哪些宿主问题属于通用 Runtime，哪些应留在产品层，
以及新增契约是否形成了可验证的任务闭环。

## 不变的模块边界

### `packages/harness/north/config.py`

- 从宿主明确指定的 `.env` 路径加载环境变量
- runtime 配置
- 参数校验

路径约定：

- harness 不发现或缓存所谓“项目根目录”
- `skills_dir` 和 `thread_base_dir` 由宿主写入 `AppConfig`
- `AppClient` 将路径传入 runtime context，文件工具不读取当前工作目录
- 示例 CLI 可以选择 `.deerflow` 作为兼容目录，但该名称不属于 harness 契约

### `packages/harness/north/state.py`

- 共享状态 schema
- 未来 reducer 扩展入口

### `packages/harness/north/runtime/`

- 组装工具
- 组装 skill
- 组装 middleware
- 组装 checkpointer
- 组装 state schema
- 管理最小 run 生命周期
- 通过 stream bridge 解耦 agent 执行和事件消费

### `packages/harness/north/skills/*`

- 从本地 skill 目录发现 skill 定义
- 读取 frontmatter，生成 skill catalog
- 提供 `SKILL.md` 正文的按需加载入口

说明：

- skill 是 agent 装配层能力，不是 thread state
- skill 的可见范围属于 runtime scope，默认不写入 `ThreadState`
- agent 默认看到的是 skill catalog，而不是全部 skill 正文
- 具体 `SKILL.md` 内容通过 `read_file` 等工具按资源 URI 按需读取
- 第一版不承担 marketplace / sandbox / 远程安装职责

### `packages/harness/north/agent.py`

- 创建 model
- 安装宿主提供的 Plugin
- 调用 `create_agent(...)`
- 将 Plugin 注册的 `AgentDefinition` 转换为委派工具，并在委派时创建无 Checkpointer 的专业 Agent

### `packages/harness/north/subagents.py`

- 定义产品无关的 Agent Definition 和委派工具
- 传播父调用 callback、context、取消和 thread 资源作用域
- 隔离 Checkpointer、工具集合、Skill 可见性和 graph state
- 将结构化结果或最终文本序列化为主 Agent 可消费的工具结果

说明：

- North 不定义 Case Analyst、Researcher 等产品角色
- Skill frontmatter 的工具列表不自动成为权限来源；Subagent 工具必须由宿主显式传入
- Subagent 不写产品消息、业务记忆或 Run

### `packages/harness/north/client.py`

- `chat()` / `stream()` 对外入口
- 标准化事件流
- `thread_id` 与 runnable config
- 把执行委托给 runtime service

说明：

- `thread_id` / `run_id` 在当前阶段是 runtime scope，不是产品层对象
- 它们的职责只是隔离一次持续任务的状态、checkpoint、事件流和 artifact 路径
- 当前阶段不要围绕它继续发明更重的 thread 业务模型

### `packages/harness/north/tools/*`

- 工具定义
- 工具注册

### `packages/harness/north/agents/middlewares/*`

- 运行时行为控制

### `app/cli.py`

- 宿主层 CLI 入口
- 参数解析
- 默认配置装配
- 不承载可复用 harness 核心实现

## 当前最小状态模型方向

```python
class ThreadState(AgentState):
    title: str | None
    artifacts: list[str]
    thread_data: dict | None
    uploaded_files: list[dict] | None
    clarification_request: dict | None
```

其中：

- `artifacts` 对当前阶段尤其重要
- `thread_data` 是未来文件 / 工作区能力的基础

### 当前最小状态更新约定

- `artifacts`
  当前唯一默认允许普通工具写入的共享字段。
  写入内容应是 thread 级 artifact 路径，而不是任意业务对象。

- `thread_data`
  当前由 runtime 预留。
  在没有专门工具契约之前，不应由普通工具随意写入。

- `uploaded_files`
  当前由 runtime / 输入接入层维护。
  工具可以读取，但不应直接改写。

- `title`
  当前不是主线能力，不作为普通工具输出目标。

- `clarification_request`
  由 North clarification middleware 写入的一次性结构化请求。`RunExecutor` 在完成时将其
  验证并投影为 `RuntimeExecutionResult.clarification`；宿主负责映射到自己的持久化
  Interaction。它不是产品层状态权威，用户回复进入下一次执行时会被清除。

### 关于 `outputs/`

- `outputs/` 只是 artifact 的物理落盘目录
- 它不是独立产品概念，也不是要扩展成通用文件系统抽象
- 当前保留它，只是为了让报告和后续 artifact 有稳定线程级落点

## 当前阶段不该做的事

- 提前引入完整 sandbox
- 提前引入 memory
- 提前引入 todo 等尚无宿主需求的外围能力
- 提前引入过多工具
- 提前引入多子代理协作

### 代码执行

North 当前不实现代码执行。未来如有真实文件分析需求，Harness 只定义执行请求、结果、
Runtime Event 和工具装配协议，隔离执行器及其安全策略由宿主提供。

输入必须来自明确的 resource URI，中间结果写入 `workspace://`，最终用户文件写入
`output://` 并通过 `present_files` 返回。不得把普通本机子进程包装成面向不可信代码的
Sandbox。完整边界见 [code-execution-boundary.md](./code-execution-boundary.md)。

这些能力属于长期候选，不是当前阶段的主推进项。

## 当前阶段的架构策略

> 保持 `app -> north` 单向依赖；Harness 负责产品无关契约，宿主负责业务与基础设施装配。
## Thread Title Middleware

`TitleMiddleware` is an opt-in runtime capability for thread-level metadata. It runs in the lead
Agent's `after_model`/`aafter_model` hook after the first complete user/assistant exchange and
returns `{"title": "..."}` into the shared `ThreadState`. The checkpoint therefore persists the
title without creating a second Run, message, or subagent.

The middleware knows nothing about a host product's domain. A host may configure a lightweight title
model, or rely on the bounded first-message fallback, and then project `ThreadState.title` into its
own conversation/case metadata. Child subagents do not inherit auto-title middleware. User-edited
product titles must be treated as authoritative by the host and must never be overwritten by this
runtime projection.
