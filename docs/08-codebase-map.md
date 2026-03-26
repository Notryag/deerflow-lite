# 08 Codebase Map

## Document Role

- Purpose: 给新进入仓库的人或 AI 提供最短路径的代码定位图
- Audience: 实现者、维护者、AI CLI
- Source of truth for: 当前代码入口、核心模块位置、任务与文件映射

## 0. Architecture Status Note

本文件描述的是“当前代码”而不是“目标架构”。

当前需要同时记住两件事：

- `docs/01-05` 已经把目标定义成 `Lead Agent + task/subagent`
- 当前代码已经有了 `lead_agent`、`task tool`、`subagent registry`、最小 `executor`，复杂任务 fallback 会直接创建 `general-purpose` subagent，research / report 产出走 tool/helper
- `T5` 的迁移重点是把 `research` / `writer` 中的 notes、summary、evidence、markdown 渲染逻辑抽成共享 helper 和 reporting tool，让 legacy agent 和 subagent runtime 复用同一层产出代码

因此，本文件的作用是帮助你定位迁移起点，而不是证明当前实现已经符合目标架构。

## 1. How To Read The Codebase

第一次进入代码时，建议按这个顺序看：

1. CLI 入口
2. 当前主 workflow
3. runtime 核心对象
4. 当前 agent 实现
5. tools 与 retrieval
6. 对应测试

推荐阅读顺序：

1. [app/cli/main.py](D:/workspace/github/deerflow-lite/app/cli/main.py)
2. [app/workflows/run_task.py](D:/workspace/github/deerflow-lite/app/workflows/run_task.py)
3. [app/runtime/state.py](D:/workspace/github/deerflow-lite/app/runtime/state.py)
4. [app/runtime/workspace.py](D:/workspace/github/deerflow-lite/app/runtime/workspace.py)
5. [app/agents/lead_agent.py](D:/workspace/github/deerflow-lite/app/agents/lead_agent.py)
6. [app/agents/local_model.py](D:/workspace/github/deerflow-lite/app/agents/local_model.py)
7. [app/tools/langchain_toolset.py](D:/workspace/github/deerflow-lite/app/tools/langchain_toolset.py)
8. [app/tools/task_tool.py](D:/workspace/github/deerflow-lite/app/tools/task_tool.py)
9. [app/subagents/registry.py](D:/workspace/github/deerflow-lite/app/subagents/registry.py)
10. [app/subagents/rendering.py](D:/workspace/github/deerflow-lite/app/subagents/rendering.py)
11. [app/subagents/runner.py](D:/workspace/github/deerflow-lite/app/subagents/runner.py)
12. [app/tools/reporting.py](D:/workspace/github/deerflow-lite/app/tools/reporting.py)
13. [app/subagents/executor.py](D:/workspace/github/deerflow-lite/app/subagents/executor.py)
14. [tests/test_workflow.py](D:/workspace/github/deerflow-lite/tests/test_workflow.py)

## 2. Code Entry Points

### CLI Entry

文件：

- [app/cli/main.py](D:/workspace/github/deerflow-lite/app/cli/main.py)

职责：

- 解析 `run` 命令
- 接收 `task`、`data_dir`、`thread_id`
- 调用 `run_task`
- 输出最终 JSON 摘要

### Main Workflow

文件：

- [app/workflows/run_task.py](D:/workspace/github/deerflow-lite/app/workflows/run_task.py)

职责：

- 初始化 `RunState`
- 创建 workspace
- 优先执行 `lead_agent`
- 在匹配 delegation 时创建 task 并调用 `subagent executor`
- 对复杂任务走 fallback subagent 路径
- 调用 reporting tool 写出 `notes/research.md` 和 `outputs/final.md`
- 写日志并更新 run 状态

这是当前最重要的迁移起点文件。

## 3. Runtime Core

### Settings

文件：

- [app/config/settings.py](D:/workspace/github/deerflow-lite/app/config/settings.py)

职责：

- 从 `.env` 和环境变量加载配置
- 管理 `model_name`、`base_url`、`runtime_dir`、`vector_db_dir`
- 管理 `subagent_max_concurrency`、`subagent_timeout_seconds`
- 控制是否使用本地 fake tool-calling model

### RunState

文件：

- [app/runtime/state.py](D:/workspace/github/deerflow-lite/app/runtime/state.py)

职责：

- 定义 run 的共享状态
- 记录 plan、task_type、tool 输出、notes、final answer、errors

这是状态 contract 的代码实现入口。

### Workspace

文件：

- [app/runtime/workspace.py](D:/workspace/github/deerflow-lite/app/runtime/workspace.py)

职责：

- 创建 `runtime/threads/{thread_id}` 目录
- 管理 `input/`、`notes/`、`outputs/`、`logs/`
- 提供安全路径解析、读写和文件列表能力

### Logger

文件：

- [app/runtime/logger.py](D:/workspace/github/deerflow-lite/app/runtime/logger.py)

职责：

- 为单次 run 创建日志
- 关闭 handler，避免 Windows 临时目录清理失败

## 4. Current Agents And Delegation Components

以下内容同时包含新架构组件和旧版固定角色 agent。

### Lead Agent

文件：

- [app/agents/lead_agent.py](D:/workspace/github/deerflow-lite/app/agents/lead_agent.py)

职责：

- 在真实模型路径下通过 `task` tool-calling 决定是否委派
- 处理简单任务直答或委派后的最终汇总
- 汇总单个 delegated result 并写出 `outputs/final.md`

当前限制：

- 当 `lead_agent` 未直接完成复杂任务时，workflow 会进入 fallback subagent 路径

### Shared Agent Helpers

文件：

- [app/agents/common.py](D:/workspace/github/deerflow-lite/app/agents/common.py)
- [app/agents/local_model.py](D:/workspace/github/deerflow-lite/app/agents/local_model.py)

职责：

- 构造 agent 上下文摘要
- 构造真实模型或本地 fake tool-calling model
- 提供 evidence、summary 等公用函数

如果要调整真实模型路径、fallback、上下文注入，先看这个文件。

### Orchestrator

文件：

- [app/agents/orchestrator.py](D:/workspace/github/deerflow-lite/app/agents/orchestrator.py)

职责：

- 决定 `task_type`
- 生成 `plan`
- 决定 `needs_retrieval`、`needs_web_search`、`needs_python`
- 对真实模型输出做归一化兜底

迁移意义：

- 可作为未来 `lead_agent` 的 planning 参考
- 但不能直接等同于目标中的 subagent harness

### Task Tool

文件：

- [app/tools/task_tool.py](D:/workspace/github/deerflow-lite/app/tools/task_tool.py)

职责：

- 校验 `description`、`prompt`、`subagent_type`、`max_turns`
- 将 task 记录到 `RunState.subagent_tasks`
- 将 task 写入 `subagents/manifest.json`

### LangChain Toolset

文件：

- [app/tools/langchain_toolset.py](D:/workspace/github/deerflow-lite/app/tools/langchain_toolset.py)

职责：

- 把 retrieval / web / file / python / task 能力包装成可挂载的 `@tool`
- 绑定 `RunState`、`Workspace` 和 `Settings`
- 为真实模型路径提供统一 tool bundle

### Subagent Registry

文件：

- [app/subagents/registry.py](D:/workspace/github/deerflow-lite/app/subagents/registry.py)

职责：

- 维护内置 `subagent_type`
- 校验类型是否合法
- 控制每种类型的 `max_turns` 和工具集

### Subagent Executor

文件：

- [app/subagents/executor.py](D:/workspace/github/deerflow-lite/app/subagents/executor.py)

职责：

- 执行单个或多个 task
- 将 task 从 `pending` 更新为 `completed`
- 生成 `subagents/{task_id}/result.md`
- 将结果回填到 `RunState.subagent_results` 和 manifest
- 在 timeout 时返回结构化 `timeout` 结果
- 按 registry 解析 subagent runtime tool bundle

当前限制：

- 当前并发层是“线程池调度 + 子进程 worker”
- 已有并发上限检查和 nested delegation 校验
- 子进程里已经运行真实 `create_agent(..., tools=[...])`

### Subagent Runner

文件：

- [app/subagents/runner.py](D:/workspace/github/deerflow-lite/app/subagents/runner.py)

职责：

- 在子进程里创建真实 LangChain subagent
- 复用共享渲染 helper 生成 subagent 摘要和 artifact
- 作为子进程 worker 的入口函数
- 支持测试用的可控延时
- 通过 agent 返回的消息流提取 executed tools 和 tool observations
- 在 artifact 中记录当前 subagent 的 runtime tools 和执行轨迹

### Shared Rendering Helpers

文件：

- [app/subagents/rendering.py](D:/workspace/github/deerflow-lite/app/subagents/rendering.py)

职责：

- 定义共享的 `ResearchNotes` 和 `WriterOutput`
- 生成 research / final report markdown
- 从 `RunState` 构造 stub notes / output
- 生成 subagent runner 复用的 summary 和 artifact markdown

### Research Agent

文件：

- [app/agents/research_agent.py](D:/workspace/github/deerflow-lite/app/agents/research_agent.py)

职责：

- 把 retrieval / web search 结果整理成 `notes/research.md`
- 在真实模型输出质量不足时回退到本地 stub notes

迁移意义：

- 可提取为共享 research helper
- 可与 subagent runner 复用同一套 notes / evidence / markdown 逻辑
- 当前更接近 legacy reference，不应再作为主 workflow 的长期能力节点

### Writer Agent

文件：

- [app/agents/writer_agent.py](D:/workspace/github/deerflow-lite/app/agents/writer_agent.py)

职责：

- 生成 `outputs/final.md`
- 写入 `final_answer`
- 在真实模型输出不可靠时回退到 stub output

迁移意义：

- 可提取为共享 report helper
- 可与 lead agent 和 subagent runner 复用同一套 final report 逻辑
- 当前更接近 legacy reference，不应再作为主 workflow 的长期能力节点

## 5. Tools

### File Tools

文件：

- [app/tools/file_ops.py](D:/workspace/github/deerflow-lite/app/tools/file_ops.py)

职责：

- 通过 `Workspace` 暴露 `read_file`、`write_file`、`list_workspace_files`

### Retrieval Tool

文件：

- [app/tools/retrieval.py](D:/workspace/github/deerflow-lite/app/tools/retrieval.py)

职责：

- 暴露 `retrieve_knowledge`
- 封装 retrieval pipeline 调用

### Web Search Tool

文件：

- [app/tools/web_search.py](D:/workspace/github/deerflow-lite/app/tools/web_search.py)

职责：

- 当前返回 deterministic stub 结果

在新规划里，这会在 harness 基础层完成后再升级。

### Python Execution Tool

文件：

- [app/tools/python_exec.py](D:/workspace/github/deerflow-lite/app/tools/python_exec.py)

职责：

- 提供基础 python 执行函数
- 当前尚未接入正式 workflow 分支

在新规划里，它会被放到 subagent 工具能力补全阶段。

### Reporting Tool

文件：

- [app/tools/reporting.py](D:/workspace/github/deerflow-lite/app/tools/reporting.py)

职责：

- 用共享 helper 生成 `notes/research.md`
- 用共享 helper 生成 `outputs/final.md`
- 更新 `RunState.notes_files`、`RunState.output_files`、`RunState.artifact_files`

这是把固定 `ResearchAgent` / `WriterAgent` 产出能力下沉到 tool 层的第一步。

## 6. Retrieval Stack

文件：

- [app/rag/loaders.py](D:/workspace/github/deerflow-lite/app/rag/loaders.py)
- [app/rag/splitter.py](D:/workspace/github/deerflow-lite/app/rag/splitter.py)
- [app/rag/embeddings.py](D:/workspace/github/deerflow-lite/app/rag/embeddings.py)
- [app/rag/vectorstore.py](D:/workspace/github/deerflow-lite/app/rag/vectorstore.py)
- [app/rag/retriever.py](D:/workspace/github/deerflow-lite/app/rag/retriever.py)

当前实现方式：

- loader 负责读文件
- splitter 负责切块
- embeddings 使用本地 deterministic hash embedding
- vectorstore 使用本地 JSON 文件
- retriever 负责索引和检索调度

如果要提升检索质量或索引复用，主要改这一组文件。

## 7. Tests Map

测试文件和覆盖点：

- [test_workspace.py](D:/workspace/github/deerflow-lite/tests/test_workspace.py): workspace 创建与路径安全
- [test_file_ops.py](D:/workspace/github/deerflow-lite/tests/test_file_ops.py): file tools 读写与越界
- [test_state.py](D:/workspace/github/deerflow-lite/tests/test_state.py): `RunState` 默认值
- [test_retrieval.py](D:/workspace/github/deerflow-lite/tests/test_retrieval.py): retrieval 输出结构
- [test_subagent_registry.py](D:/workspace/github/deerflow-lite/tests/test_subagent_registry.py): registry 类型和 `max_turns` 校验
- [test_task_tool.py](D:/workspace/github/deerflow-lite/tests/test_task_tool.py): task 创建、manifest 写入、参数校验
- [test_langchain_toolset.py](D:/workspace/github/deerflow-lite/tests/test_langchain_toolset.py): 完整 tool bundle 暴露、检索和搜索 tool 的 state 回填
- [test_langchain_tool_execution.py](D:/workspace/github/deerflow-lite/tests/test_langchain_tool_execution.py): file/python tool 的实际执行与 artifact 更新
- [test_subagent_executor.py](D:/workspace/github/deerflow-lite/tests/test_subagent_executor.py): executor 执行、批量执行、timeout、并发上限与 nested delegation 校验
- [test_orchestrator.py](D:/workspace/github/deerflow-lite/tests/test_orchestrator.py): 旧版 orchestrator 决策
- [test_reporting_tool.py](D:/workspace/github/deerflow-lite/tests/test_reporting_tool.py): reporting tool 落盘与 state 更新
- [test_reporting_helpers.py](D:/workspace/github/deerflow-lite/tests/test_reporting_helpers.py): 共享 prompt、markdown renderer 与 subagent artifact contract
- [test_workflow.py](D:/workspace/github/deerflow-lite/tests/test_workflow.py): 统一 lead-agent runtime、delegation、复杂任务 fallback subagent 主流程

## 8. Hot Files By Task

### 做 `T1. Harness State And Workspace Refactor`

优先看：

- [app/workflows/run_task.py](D:/workspace/github/deerflow-lite/app/workflows/run_task.py)
- [app/runtime/state.py](D:/workspace/github/deerflow-lite/app/runtime/state.py)
- [app/runtime/workspace.py](D:/workspace/github/deerflow-lite/app/runtime/workspace.py)
- [app/runtime/logger.py](D:/workspace/github/deerflow-lite/app/runtime/logger.py)
- [docs/03-agent-and-tool-contracts.md](D:/workspace/github/deerflow-lite/docs/03-agent-and-tool-contracts.md)
- [docs/07-roadmap-and-progress.md](D:/workspace/github/deerflow-lite/docs/07-roadmap-and-progress.md)

### 做 `T2. Lead Agent Skeleton`

优先看：

- [app/agents/lead_agent.py](D:/workspace/github/deerflow-lite/app/agents/lead_agent.py)
- [app/agents/common.py](D:/workspace/github/deerflow-lite/app/agents/common.py)
- [app/workflows/run_task.py](D:/workspace/github/deerflow-lite/app/workflows/run_task.py)
- [app/runtime/state.py](D:/workspace/github/deerflow-lite/app/runtime/state.py)
- [docs/02-architecture-and-runtime.md](D:/workspace/github/deerflow-lite/docs/02-architecture-and-runtime.md)

### 做 `T3. Task Tool And Registry`

优先看：

- [app/tools/task_tool.py](D:/workspace/github/deerflow-lite/app/tools/task_tool.py)
- [app/subagents/registry.py](D:/workspace/github/deerflow-lite/app/subagents/registry.py)
- [app/config/settings.py](D:/workspace/github/deerflow-lite/app/config/settings.py)
- [docs/03-agent-and-tool-contracts.md](D:/workspace/github/deerflow-lite/docs/03-agent-and-tool-contracts.md)
- [docs/04-implementation-plan.md](D:/workspace/github/deerflow-lite/docs/04-implementation-plan.md)

### 做 `T4. Subagent Executor`

优先看：

- [app/subagents/runner.py](D:/workspace/github/deerflow-lite/app/subagents/runner.py)
- [app/subagents/executor.py](D:/workspace/github/deerflow-lite/app/subagents/executor.py)
- [app/agents/lead_agent.py](D:/workspace/github/deerflow-lite/app/agents/lead_agent.py)
- [app/workflows/run_task.py](D:/workspace/github/deerflow-lite/app/workflows/run_task.py)
- [app/runtime/logger.py](D:/workspace/github/deerflow-lite/app/runtime/logger.py)
- [app/runtime/workspace.py](D:/workspace/github/deerflow-lite/app/runtime/workspace.py)
- [docs/02-architecture-and-runtime.md](D:/workspace/github/deerflow-lite/docs/02-architecture-and-runtime.md)
- [docs/05-testing-and-acceptance.md](D:/workspace/github/deerflow-lite/docs/05-testing-and-acceptance.md)

### 做 `T5. Legacy Logic Migration`

优先看：

- [app/agents/common.py](D:/workspace/github/deerflow-lite/app/agents/common.py)
- [app/agents/orchestrator.py](D:/workspace/github/deerflow-lite/app/agents/orchestrator.py)
- [app/agents/research_agent.py](D:/workspace/github/deerflow-lite/app/agents/research_agent.py)
- [app/agents/writer_agent.py](D:/workspace/github/deerflow-lite/app/agents/writer_agent.py)
- [app/subagents/runner.py](D:/workspace/github/deerflow-lite/app/subagents/runner.py)
- [app/subagents/rendering.py](D:/workspace/github/deerflow-lite/app/subagents/rendering.py)
- [app/tools/reporting.py](D:/workspace/github/deerflow-lite/app/tools/reporting.py)
- [docs/07-roadmap-and-progress.md](D:/workspace/github/deerflow-lite/docs/07-roadmap-and-progress.md)

## 9. Expected Remaining New Files

按目标架构，后续大概率还会新增新的 subagent runtime / provider 文件，但共享渲染层已经先落在：

- [app/subagents/rendering.py](D:/workspace/github/deerflow-lite/app/subagents/rendering.py)

后续新增文件时，应以 `docs/02`、`docs/03` 为准，而不是沿用旧版角色划分。

## 10. Fast Orientation Prompt

如果新窗口的 AI 需要快速进入状态，可以给它这个提示：

```text
先读 README.md，然后读 docs/07-roadmap-and-progress.md 和 docs/08-codebase-map.md。
如果要改实现，先区分“目标架构”和“当前代码”，再按代码地图定位入口和热点文件。
严格遵守 docs/01-06 的 source-of-truth 规则。
先汇报你理解的当前状态、目标任务、要改的文件，再动手。
```
