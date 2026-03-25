# 03 Agent And Tool Contracts

## Document Role

- Purpose: 定义状态对象、agent 行为和 tool / subagent I/O 的可执行合同
- Audience: 工程实现、测试实现、AI CLI
- Source of truth for: `RunState`、agent contracts、subagent contracts、tool contracts

## 1. Contract Rules

所有 contract 必须满足以下规则：

- 字段名稳定
- 类型清晰
- 输出可测试
- 输出能直接写入 `RunState`
- 不依赖自然语言猜测隐含字段

## 2. RunState

`RunState` MUST 使用 `pydantic.BaseModel`。

建议的最小结构如下：

```python
from pydantic import BaseModel, Field


class RunState(BaseModel):
    thread_id: str
    user_task: str
    workspace_dir: str | None = None
    trace_id: str | None = None
    status: str = "pending"

    plan: list[str] = Field(default_factory=list)
    task_type: str | None = None

    subagent_tasks: list[dict] = Field(default_factory=list)
    subagent_results: list[dict] = Field(default_factory=list)

    retrieved_docs: list[dict] = Field(default_factory=list)
    search_results: list[dict] = Field(default_factory=list)

    artifact_files: list[str] = Field(default_factory=list)
    output_files: list[str] = Field(default_factory=list)

    final_answer: str | None = None
    errors: list[str] = Field(default_factory=list)
```

### 2.1 State Rules

- 所有 list 字段 MUST 使用 `default_factory`
- `status` MUST 至少支持 `pending`, `running`, `completed`, `failed`
- `subagent_tasks` 至少要记录 `task_id`、`description`、`subagent_type`、`status`
- `subagent_results` 至少要记录 `task_id`、`summary`、`artifacts`、`status`
- 节点运行后必须显式写回相关字段
- 错误必须写入 `errors`

## 3. Lead Agent Contract

### 3.1 Responsibility

`lead_agent` MUST：

- 理解任务意图
- 生成简短 plan
- 判断是否需要委派
- 在需要时构造自包含的 subagent task prompt
- 汇总 subagent 结果和 workspace 产物
- 产出最终对用户可读的回答

### 3.2 Behavior Rules

- `lead_agent` MAY 直接完成简单任务
- `lead_agent` MUST NOT 依赖固定写死的下游 `research_agent` / `writer_agent`
- `lead_agent` MUST 通过 `task` 工具发起 subagent
- `lead_agent` MUST 记录 plan、subagent 调用和最终输出
- `lead_agent` 必须区分“来自工具或 artifact 的事实”和“模型综合结论”

## 4. Task Tool Contract

### 4.1 Signature

`task(description, prompt, subagent_type="general-purpose", max_turns=8) -> dict`

### 4.2 Request Shape

```python
{
  "description": "Inspect local docs and summarize key API changes.",
  "prompt": "Read the relevant files from the shared workspace and return a concise summary with artifact paths.",
  "subagent_type": "general-purpose",
  "max_turns": 8,
}
```

### 4.3 Output Shape

`task` 的返回值必须能映射成：

```python
{
  "task_id": "task_001",
  "description": "Inspect local docs and summarize key API changes.",
  "subagent_type": "general-purpose",
  "status": "completed",
  "summary": "The docs changed in three places...",
  "artifacts": ["workspace/notes/api_changes.md"],
  "citations": ["docs/api.md#section-2"],
  "error": None,
}
```

### 4.4 Rules

- `task` MUST 是唯一的 subagent 创建入口
- `prompt` MUST 自包含
- `subagent_type` MUST 由 registry 校验
- `task` MUST 记录 `task_id`
- `task` MUST NOT 允许 subagent 再创建 subagent
- 失败时也 MUST 返回结构化结果或将错误写入 `state.errors`

## 5. Subagent Contract

### 5.1 Responsibility

subagent MUST：

- 只处理被分配的单个子任务
- 在共享 workspace 中读写必要产物
- 返回结构化摘要与 artifact 路径
- 在超时或失败时给出可追踪状态

### 5.2 Execution Rules

- subagent MUST 以独立上下文启动
- subagent 初始输入 SHOULD 是一条自包含的用户 prompt
- subagent 与父 agent 共享 workspace / thread 级数据
- subagent MUST NOT 继承父 agent 的完整消息历史
- subagent MUST NOT 再调用 `task`

### 5.3 Built-In Types

最少必须支持的类型：

- `general-purpose`: 默认分析型 subagent，可使用除 `task` 外的常规工具
- `bash`: 偏 shell / coding 的 subagent，工具集必须比通用 subagent 更严格

## 6. Subagent Registry Contract

registry MUST 提供稳定的类型到配置映射。

最小配置形状如下：

```python
{
  "name": "general-purpose",
  "description": "General research and synthesis worker.",
  "max_turns": 8,
  "timeout_seconds": 900,
  "allowed_tools": ["retrieve_knowledge", "search_web", "read_file", "write_file", "list_workspace_files"],
  "disallowed_tools": ["task"],
}
```

规则：

- registry MUST 校验请求的 `subagent_type`
- 每种类型 MUST 有显式 `max_turns`
- 每种类型 MUST 有显式 `timeout_seconds`
- `task` MUST 默认在所有 subagent 类型中禁用

## 7. Subagent Executor Contract

executor MUST 负责 subagent 生命周期管理。

### 7.1 Required Behavior

- 创建 subagent 初始状态
- 执行单个或多个 subagent
- 控制并发上限
- 控制超时
- 汇总结构化结果
- 传播 `trace_id`

### 7.2 Rules

- 默认最大并发 SHOULD 为 `3`
- 超时后 MUST 返回 `status="failed"` 或 `status="timeout"`
- executor MUST 将结果写回 `RunState.subagent_results`
- executor SHOULD 将每个 subagent 的日志或 manifest 写入 workspace

## 8. Retrieval Tool Contract

### 8.1 Signature

`retrieve_knowledge(query, top_k=3, collection_name=None) -> list[dict]`

### 8.2 Output Shape

每条记录必须包含：

```python
{
  "content": "...",
  "source": "...",
  "score": 0.87,
  "metadata": {}
}
```

### 8.3 Rules

- retrieval 必须作为 tool 存在
- 不得硬编码到主 prompt 前缀里
- `top_k` 默认值为 `3`

## 9. Web Search Tool Contract

第一版允许 stub，但接口必须稳定。

### 9.1 Signature

`search_web(query, top_k=5) -> list[dict]`

### 9.2 Output Shape

```python
{
  "title": "...",
  "url": "...",
  "snippet": "...",
  "source": "web"
}
```

### 9.3 Rules

- 没有真实 provider 时，返回 mock 结构
- stub 数据必须可测试，不得随机漂移

## 10. File Tool Contracts

### 10.1 Required Tools

- `read_file(path)`
- `write_file(path, content)`
- `list_workspace_files()`

### 10.2 Security Rules

- 所有路径 MUST 限制在当前 thread workspace 内
- 必须做路径归一化和越界校验
- 越界访问必须返回清晰错误

## 11. Python Execution Contract

`run_python_code` 不是 MVP 必需项，但预留接口路径。

如果实现，必须满足：

- 只在受限目录执行
- 必须有超时
- 必须捕获 `stdout` 和 `stderr`
- 必须返回执行结果和产物路径

## 12. Failure Handling

每个节点都必须遵守以下失败处理策略：

- 工具失败时写入 `state.errors`
- subagent 失败可以降级继续，但必须记录 `task_id` 和失败原因
- 非关键失败可以降级继续，但必须记录
- 无法继续时将 `state.status` 置为 `failed`
- 最终失败也应尽量保留 workspace 以便排查
