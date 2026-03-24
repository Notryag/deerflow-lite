# 03 Agent And Tool Contracts

## Document Role

- Purpose: 定义状态对象、agent 输出和 tool I/O 的可执行合同
- Audience: 工程实现、测试实现、AI CLI
- Source of truth for: `RunState`、agent contracts、tool contracts

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
    status: str = "pending"

    plan: list[str] = Field(default_factory=list)
    task_type: str | None = None

    needs_retrieval: bool = False
    needs_web_search: bool = False
    needs_python: bool = False

    retrieved_docs: list[dict] = Field(default_factory=list)
    search_results: list[dict] = Field(default_factory=list)

    notes_files: list[str] = Field(default_factory=list)
    output_files: list[str] = Field(default_factory=list)

    final_answer: str | None = None
    errors: list[str] = Field(default_factory=list)
```

### 2.1 State Rules

- 所有 list 字段 MUST 使用 `default_factory`
- `status` MUST 至少支持 `pending`, `running`, `completed`, `failed`
- 节点运行后必须显式写回相关字段
- 错误必须写入 `errors`

## 3. Orchestrator Contract

### 3.1 Responsibility

`orchestrator` MUST：

- 理解任务意图
- 生成简短 plan
- 判断是否需要 retrieval、web search、python
- 决定执行顺序
- 为下游节点整理上下文摘要

### 3.2 Output Shape

orchestrator 的结构化输出必须能映射成：

```python
{
  "task_type": "research_report",
  "plan": [
    "inspect available local documents",
    "retrieve relevant chunks",
    "write research notes",
    "produce final markdown report"
  ],
  "needs_retrieval": True,
  "needs_web_search": False,
  "needs_python": False
}
```

### 3.3 Output Rules

- orchestrator MUST NOT 直接写最终长文
- orchestrator MUST NOT 隐式触发工具执行
- orchestrator 的输出必须可单测解析

## 4. Research Agent Contract

### 4.1 Responsibility

`research_agent` MUST：

- 消化 retrieval 或 web search 结果
- 产出结构化 notes
- 将 notes 写入 workspace

### 4.2 Notes Format

默认 notes 文件格式如下：

```md
# Research Notes

## User task
...

## Key findings
- ...

## Evidence
1. ...

## Open questions
- ...
```

### 4.3 Output Rules

- 研究结论必须能追溯到输入材料
- notes 产物路径必须写入 `state.notes_files`
- 缺失信息必须放入 `Open questions`

## 5. Writer Agent Contract

### 5.1 Responsibility

`writer_agent` MUST：

- 基于 notes、retrieved docs、search results 生成最终结果
- 输出 `final.md`
- 给出对用户可读的最终答复摘要

### 5.2 Output Rules

- 内容默认简洁
- 内容必须分层
- 必须区分“来自检索/搜索的事实”和“模型整合结论”
- 最终产物路径必须写入 `state.output_files`
- 最终摘要必须写入 `state.final_answer`

## 6. Retrieval Tool Contract

### 6.1 Signature

`retrieve_knowledge(query, top_k=3, collection_name=None) -> list[dict]`

### 6.2 Output Shape

每条记录必须包含：

```python
{
  "content": "...",
  "source": "...",
  "score": 0.87,
  "metadata": {}
}
```

### 6.3 Rules

- retrieval 必须作为 tool 存在
- 不得硬编码到主 prompt 前缀里
- `top_k` 默认值为 `3`

## 7. Web Search Tool Contract

第一版允许 stub，但接口必须稳定。

### 7.1 Signature

`search_web(query, top_k=5) -> list[dict]`

### 7.2 Output Shape

```python
{
  "title": "...",
  "url": "...",
  "snippet": "...",
  "source": "web"
}
```

### 7.3 Rules

- 没有真实 provider 时，返回 mock 结构
- stub 数据必须可测试，不得随机漂移

## 8. File Tool Contracts

### 8.1 Required Tools

- `read_file(path)`
- `write_file(path, content)`
- `list_workspace_files()`

### 8.2 Security Rules

- 所有路径 MUST 限制在当前 thread workspace 内
- 必须做路径归一化和越界校验
- 越界访问必须返回清晰错误

## 9. Python Execution Contract

`run_python_code` 不是 MVP 必需项，但预留接口路径。

如果实现，必须满足：

- 只在受限目录执行
- 必须有超时
- 必须捕获 `stdout` 和 `stderr`
- 必须返回执行结果和产物路径

## 10. Failure Handling

每个节点都必须遵守以下失败处理策略：

- 工具失败时写入 `state.errors`
- 非关键失败可以降级继续，但必须记录
- 无法继续时将 `state.status` 置为 `failed`
- 最终失败也应尽量保留 workspace 以便排查
