# 02 Architecture And Runtime

## Document Role

- Purpose: 定义系统结构、目录布局、workspace 模型和运行时策略
- Audience: 架构设计、工程实现、AI CLI
- Source of truth for: 架构、目录结构、流程、workspace、上下文策略

## 1. Top-Level Architecture

主流程 MUST 是显式编排，而不是黑盒 agent 自动串联。

```text
User Task
  -> CLI Entry
  -> Run Manager
  -> Orchestrator
      -> Retrieval when needed
      -> Web search when needed
      -> Python execution when needed
  -> Research Agent
  -> Writer Agent
  -> Persist Outputs
  -> Final Answer
```

系统的核心分工必须是：

- agent 负责推理和决策
- tool 负责外部能力调用
- workflow 负责流程控制
- state 负责跨节点共享信息
- workspace 负责中间产物落盘

## 2. Required Directory Layout

实现 MUST 以以下结构为目标：

```text
app/
  agents/
    orchestrator.py
    research_agent.py
    writer_agent.py
  tools/
    retrieval.py
    web_search.py
    file_ops.py
    python_exec.py
  workflows/
    run_task.py
  runtime/
    state.py
    workspace.py
    logger.py
  rag/
    loaders.py
    splitter.py
    embeddings.py
    vectorstore.py
    retriever.py
  config/
    settings.py
  cli/
    main.py
tests/
```

说明：

- `python_exec.py` 可以是 stub，但模块路径应预留
- `api/` 不在当前强制目录内
- `schemas/` 只有在实现中有明确独立价值时再引入

## 3. Runtime Flow

第一版 MUST 用显式流程函数驱动：

```python
def run_task(user_task: str) -> RunState:
    state = init_state(user_task)
    state = run_orchestrator(state)

    if state.needs_retrieval:
        state = run_retrieval(state)

    if state.needs_web_search:
        state = run_web_search(state)

    if state.needs_python:
        state = run_python_code_step(state)

    state = run_research_agent(state)
    state = run_writer_agent(state)
    state = persist_outputs(state)
    return state
```

以下约束必须满足：

- 节点调用顺序清晰
- 条件分支由 `RunState` 驱动
- 节点之间不依赖隐式 prompt 历史传递关键数据
- graph-like 可以有，但第一版不得先造复杂 graph engine

## 4. Workspace Model

每次 run MUST 创建独立目录：

```text
runtime/threads/{thread_id}/
  input/
  notes/
  outputs/
  logs/
```

### 4.1 File Convention

以下文件约定必须默认存在或由流程生成：

- `input/task.md`
- `notes/research.md`
- `outputs/final.md`
- `logs/run.log`

### 4.2 Workspace Principles

- 所有最终结果 MUST 落盘
- 关键中间结果 SHOULD 落盘
- agent 协作 SHOULD 通过结构化 state 和文件完成
- workspace 必须可以支持调试和失败恢复

## 5. Context Injection Strategy

writer 和 orchestrator SHOULD 使用 middleware 注入动态上下文，但必须控制输入量。

允许注入的内容：

- task summary
- available tools summary
- workspace file summary
- retrieval summary
- research notes summary

不得直接注入的内容：

- 整个 workspace 原文
- 大量无筛选日志
- 全量检索结果原文

### 5.1 Context Budget Rules

- 默认只传摘要
- 长文只传前若干段或压缩摘要
- retrieval 默认 `top_k = 3`
- writer 优先读取 notes 摘要，而不是直接消费所有原始材料

## 6. Configuration

实现 SHOULD 使用 `.env` 加 `settings` 模块统一读取配置。

最小配置项必须覆盖：

```env
OPENAI_API_KEY=
OPENAI_BASE_URL=
MODEL_NAME=
EMBEDDING_MODEL=
VECTOR_DB_DIR=.cache/vectorstore
RUNTIME_DIR=./runtime
WEB_SEARCH_PROVIDER=stub
```

## 7. Evolution Path

以下演进顺序必须遵守：

1. 先跑通显式 workflow
2. 再稳定 state 和 tool contracts
3. 最后再考虑节点抽象、condition、edge 等图模型

当前阶段不得为了未来扩展而提前引入复杂调度框架。
