# 02 Architecture And Runtime

## Document Role

- Purpose: 定义系统结构、目录布局、workspace 模型和运行时策略
- Audience: 架构设计、工程实现、AI CLI
- Source of truth for: 架构、目录结构、流程、workspace、上下文策略

## 1. Top-Level Architecture

主流程 MUST 是显式编排的 `Lead Agent + task/subagent` harness，而不是固定写死的多段式 agent 流水线。

```text
User Task
  -> CLI Entry
  -> Run Manager
  -> Lead Agent
      -> direct answer when task is simple
      -> task tool when delegation is needed
          -> Subagent Executor
              -> Subagent A
              -> Subagent B
              -> Subagent C
      -> aggregate structured subagent results
  -> Persist Outputs
  -> Final Answer
```

系统的核心分工必须是：

- `lead_agent` 负责规划、委派、综合
- `task` 工具负责显式创建 subagent
- `subagent executor` 负责并发、超时、追踪和结果回收
- 其他 tools 负责所有具体能力调用
- `workflow` 负责 run 生命周期
- `state` 负责跨节点共享信息
- `workspace` 负责中间产物落盘

这里的“具体能力”包括但不限于：

- retrieval
- web search
- file operations
- shell / python execution
- research notes / final report 产出

固定 `ResearchAgent` / `WriterAgent` 这类角色 MAY 在迁移期作为参考实现保留，但 MUST NOT 作为目标架构中的长期能力承载点。

## 2. Required Directory Layout

实现 MUST 以以下结构为目标：

```text
app/
  agents/
    lead_agent.py
    common.py
  subagents/
    registry.py
    executor.py
    builtins.py
  tools/
    task_tool.py
    reporting.py
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
- 当前仓库里的 `orchestrator.py`、`research_agent.py`、`writer_agent.py` 可作为迁移参考，但不是目标终态
- `reporting.py` 是将 research / report 能力收敛到 tool 层的迁移方向

## 3. Runtime Flow

第一版 subagent harness MUST 用显式流程函数驱动：

```python
def run_task(user_task: str) -> RunState:
    state = init_state(user_task)
    workspace = create_workspace(state)
    state = run_lead_agent(state, workspace)
    state = persist_outputs(state, workspace)
    return state
```

其中 `run_lead_agent` 的行为约束是：

- 在真实模型路径下，lead agent SHOULD 由 LLM 自己决定是否调用 `task` 工具
- lead agent MAY 直接完成简单任务
- lead agent MAY 多次调用 `task` 工具
- `task` 工具 MUST 把请求交给 `subagent executor`
- executor MUST 返回结构化 subagent 结果
- lead agent MUST 基于结果完成综合并写出最终产物

以下约束必须满足：

- 节点调用顺序清晰
- 条件分支由 `RunState` 驱动
- subagent 创建只能通过 `task` 工具完成
- 节点之间不依赖隐式 prompt 历史传递关键数据
- graph-like 可以有，但第一版不得先造复杂 graph engine

## 4. Workspace Model

每次 run MUST 创建独立目录：

```text
runtime/threads/{thread_id}/
  input/
  workspace/
  outputs/
  logs/
  subagents/
```

### 4.1 File Convention

以下文件约定必须默认存在或由流程生成：

- `input/task.md`
- `outputs/final.md`
- `logs/run.log`
- `subagents/manifest.json`

subagent 产生的中间 notes、代码、草稿、分析结果 SHOULD 写入 `workspace/` 或 `subagents/{task_id}/`。

### 4.2 Workspace Principles

- 所有最终结果 MUST 落盘
- 关键中间结果 SHOULD 落盘
- lead agent 与 subagent SHOULD 通过结构化 state 和文件完成协作
- subagent 共享同一个 thread workspace
- subagent 结果必须可以按 `task_id` 回溯
- workspace 必须可以支持调试和失败恢复

## 5. Context Injection Strategy

`lead_agent` SHOULD 使用 middleware 注入动态上下文，但必须控制输入量。subagent 的上下文注入规则必须与 lead agent 区分开。

真实模型路径中，是否委派给 subagent SHOULD 由 lead agent 在 tool-calling 过程中决定，而不是由 Python 侧 heuristics 预先硬编码。

这里必须明确区分两层系统：

- `middleware` 负责注入上下文、系统约束、运行时摘要和观测信息
- `tool` 负责暴露具体能力，例如搜索、检索、文件操作、命令执行和委派

因此：

- middleware MUST NOT 替模型决定是否搜索、是否检索、是否读写文件、是否委派
- workflow SHOULD NOT 用业务 heuristics 预判这些动作
- 这些动作 SHOULD 由模型在 tool-calling 过程中自主决定

允许注入到 lead agent 的内容：

- task summary
- available tools summary
- workspace file summary
- retrieval summary
- 已完成 subagent 的摘要结果

允许注入到 subagent 的内容：

- 一条自包含的 task prompt
- 当前 thread 的必要元数据
- 共享 workspace / sandbox 访问能力

不得直接注入到 subagent 的内容：

- lead agent 的完整对话历史
- 其他 subagent 的完整消息历史
- 整个 workspace 原文
- 大量无筛选日志

### 5.1 Context Budget Rules

- 默认只传摘要
- 长文只传前若干段或压缩摘要
- retrieval 默认 `top_k = 3`
- subagent prompt MUST 自包含，不依赖父消息上下文
- lead agent 优先读取 subagent 摘要和 artifact 路径，而不是全量原文

### 5.2 Middleware And Tool Boundary

middleware 适合承载：

- task summary
- workspace summary
- retrieval / search 的已有结果摘要
- 安全约束
- trace / logging 元数据

tool 适合承载：

- `task(...)`
- `retrieve_knowledge(...)`
- `search_web(...)`
- `read_file(...)`
- `write_file(...)`
- `run_python_code(...)` 或 shell 工具
- research / report 产出 helper 或 tool

任何“是否执行某个能力”的判断，都 SHOULD 发生在模型调用 tool 时，而不是在 middleware 或 workflow 的 `if/else` 里。

### 5.3 Delegation Guardrails

- subagent MUST NOT 再创建 subagent
- 默认最大并发数 SHOULD 为 `3`
- 单个 subagent 默认超时 SHOULD 为 `900` 秒
- 每个 subagent MUST 有显式 `max_turns`

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
SUBAGENT_MAX_CONCURRENCY=3
SUBAGENT_TIMEOUT_SECONDS=900
```

## 7. Evolution Path

以下演进顺序必须遵守：

1. 先用显式 workflow 跑通 `lead_agent + task/subagent executor`
2. 再稳定 `RunState`、task、subagent contracts
3. 再补并发保护、artifact manifest、受控执行能力
4. 最后再考虑更复杂的图模型或 API 入口

当前阶段不得为了未来扩展而提前引入复杂调度框架。

## 8. Current Reference Implementation Notes

当前参考实现仍保留以下旧版工程取舍：

- 主 workflow 已不再依赖固定 `orchestrator -> research -> writer` 链路
- 复杂任务 fallback 会直接创建 `general-purpose` subagent，再由 tool/helper 产出 notes / report
- `orchestrator.py` 仍保留在仓库中作为 legacy planning 参考实现
- retrieval 使用本地 deterministic embedding 和 JSON vector store 作为 MVP 默认实现
- 没有模型配置时，agent 允许走 stub 路径，但对外 contract 不变
- stub 路径允许使用少量 deterministic heuristics 作为 fallback，但这不是目标中的委派决策机制
- web search 当前默认是 stub provider

这些实现细节会被后续 refactor 替换，但替换时不得破坏 `03-agent-and-tool-contracts.md` 中定义的接口稳定性。
