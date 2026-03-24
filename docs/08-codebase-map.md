# 08 Codebase Map

## Document Role

- Purpose: 给新进入仓库的人或 AI 提供最短路径的代码定位图
- Audience: 实现者、维护者、AI CLI
- Source of truth for: 当前代码入口、核心模块位置、任务与文件映射

## 1. How To Read The Codebase

第一次进入代码时，建议按这个顺序看：

1. CLI 入口
2. 主 workflow
3. runtime 核心对象
4. agent 实现
5. tools 与 retrieval
6. 对应测试

推荐阅读顺序：

1. [app/cli/main.py](D:/workspace/github/deerflow-lite/app/cli/main.py)
2. [app/workflows/run_task.py](D:/workspace/github/deerflow-lite/app/workflows/run_task.py)
3. [app/runtime/state.py](D:/workspace/github/deerflow-lite/app/runtime/state.py)
4. [app/runtime/workspace.py](D:/workspace/github/deerflow-lite/app/runtime/workspace.py)
5. [app/agents/orchestrator.py](D:/workspace/github/deerflow-lite/app/agents/orchestrator.py)
6. [app/agents/research_agent.py](D:/workspace/github/deerflow-lite/app/agents/research_agent.py)
7. [app/agents/writer_agent.py](D:/workspace/github/deerflow-lite/app/agents/writer_agent.py)
8. [app/tools/retrieval.py](D:/workspace/github/deerflow-lite/app/tools/retrieval.py)
9. [app/tools/web_search.py](D:/workspace/github/deerflow-lite/app/tools/web_search.py)
10. [tests/test_workflow.py](D:/workspace/github/deerflow-lite/tests/test_workflow.py)

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
- 执行 orchestrator
- 根据 state 触发 retrieval 和 web search
- 执行 research 和 writer
- 写日志并更新 run 状态

这是当前最重要的主流程文件。

## 3. Runtime Core

### Settings

文件：

- [app/config/settings.py](D:/workspace/github/deerflow-lite/app/config/settings.py)

职责：

- 从 `.env` 和环境变量加载配置
- 管理 `model_name`、`base_url`、`runtime_dir`、`vector_db_dir`
- 决定是否走 stub agents

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

## 4. Agents

### Shared Agent Helpers

文件：

- [app/agents/common.py](D:/workspace/github/deerflow-lite/app/agents/common.py)

职责：

- 构造 agent 上下文摘要
- 构造 `ChatOpenAI`
- 控制 stub / real model 路径切换
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

### Research Agent

文件：

- [app/agents/research_agent.py](D:/workspace/github/deerflow-lite/app/agents/research_agent.py)

职责：

- 把 retrieval / web search 结果整理成 `notes/research.md`
- 在真实模型输出质量不足时回退到本地 stub notes

### Writer Agent

文件：

- [app/agents/writer_agent.py](D:/workspace/github/deerflow-lite/app/agents/writer_agent.py)

职责：

- 生成 `outputs/final.md`
- 写入 `final_answer`
- 在真实模型输出不可靠时回退到 stub output

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

这是接下来 `T1` 的主要改造点。

### Python Execution Tool

文件：

- [app/tools/python_exec.py](D:/workspace/github/deerflow-lite/app/tools/python_exec.py)

职责：

- 提供基础 python 执行函数
- 当前尚未接入正式 workflow 分支

这是接下来 `T2` 的主要改造点。

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
- [test_orchestrator.py](D:/workspace/github/deerflow-lite/tests/test_orchestrator.py): orchestrator 决策
- [test_workflow.py](D:/workspace/github/deerflow-lite/tests/test_workflow.py): 端到端主流程

## 8. Hot Files By Task

### 做 `T1. Real Web Search Provider`

优先看：

- [app/tools/web_search.py](D:/workspace/github/deerflow-lite/app/tools/web_search.py)
- [app/config/settings.py](D:/workspace/github/deerflow-lite/app/config/settings.py)
- [app/workflows/run_task.py](D:/workspace/github/deerflow-lite/app/workflows/run_task.py)
- [app/agents/orchestrator.py](D:/workspace/github/deerflow-lite/app/agents/orchestrator.py)
- [docs/03-agent-and-tool-contracts.md](D:/workspace/github/deerflow-lite/docs/03-agent-and-tool-contracts.md)
- [docs/07-roadmap-and-progress.md](D:/workspace/github/deerflow-lite/docs/07-roadmap-and-progress.md)

### 做 `T2. Controlled Python Execution`

优先看：

- [app/tools/python_exec.py](D:/workspace/github/deerflow-lite/app/tools/python_exec.py)
- [app/workflows/run_task.py](D:/workspace/github/deerflow-lite/app/workflows/run_task.py)
- [app/runtime/workspace.py](D:/workspace/github/deerflow-lite/app/runtime/workspace.py)
- [app/runtime/state.py](D:/workspace/github/deerflow-lite/app/runtime/state.py)

### 做 `T3. Model Reliability And Fallback`

优先看：

- [app/agents/common.py](D:/workspace/github/deerflow-lite/app/agents/common.py)
- [app/agents/orchestrator.py](D:/workspace/github/deerflow-lite/app/agents/orchestrator.py)
- [app/agents/research_agent.py](D:/workspace/github/deerflow-lite/app/agents/research_agent.py)
- [app/agents/writer_agent.py](D:/workspace/github/deerflow-lite/app/agents/writer_agent.py)
- [app/runtime/logger.py](D:/workspace/github/deerflow-lite/app/runtime/logger.py)

## 9. Fast Orientation Prompt

如果新窗口的 AI 需要快速进入状态，可以给它这个提示：

```text
先读 README.md，然后读 docs/07-roadmap-and-progress.md 和 docs/08-codebase-map.md。
如果要改实现，再按代码地图定位入口和热点文件。
严格遵守 docs/01-06 的 source-of-truth 规则。
先汇报你理解的当前状态、目标任务、要改的文件，再动手。
```
