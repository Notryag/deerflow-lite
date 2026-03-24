# 01 Product And Scope

## Document Role

- Purpose: 定义项目目标、范围、非目标和必须遵守的技术边界
- Audience: 产品设计、架构设计、实现执行、AI CLI
- Source of truth for: 目标、MVP、非目标、技术约束

## 1. Product Goal

`deerflow-lite` MUST 从 DeerFlow 中抽离最有价值的核心能力，交付一个轻量、可维护、可扩展的 Agent 工作流 MVP。

这个项目不是 DeerFlow 的复刻品，而是一个聚焦以下场景的精简实现：

- Agentic RAG
- research 工作流
- 多工具调用
- 中间产物落盘
- 多步骤任务编排
- 主 agent 加少量专用 agent 协作

## 2. Product Keywords

以下关键词必须同时成立：

- Lite
- Local-first
- Practical
- Extensible
- Minimal but powerful

## 3. MVP Scope

MVP MUST 只包含以下能力：

### 3.1 Runtime Modes

- CLI 运行入口
- 本地 workspace 管理
- 单次 run 的显式流程编排

### 3.2 Agents

- `orchestrator`
- `research_agent`
- `writer_agent`

### 3.3 Tools

- `retrieve_knowledge`
- `search_web`
- `read_file`
- `write_file`
- `list_workspace_files`

### 3.4 Retrieval

- 本地文档加载
- chunk 切分
- embedding
- vector store
- top-k retrieval

### 3.5 Outputs

- notes 落盘
- 最终结果落盘
- 面向 CLI 的简要终端输出

## 4. Explicit Non-Goals

以下内容 MUST NOT 进入当前 MVP：

- 完整前端 UI
- Slack、Telegram、Feishu 等 channel 接入
- 多租户和权限系统
- 长期 memory 平台
- 工作流可视化编辑器
- 复杂数据库 schema
- 消息队列
- 云原生编排
- 全量 artifact 平台
- 把所有能力都 agent 化

## 5. Technical Constraints

### 5.1 Language And Runtime

以下约束必须满足：

- Python `3.11+`
- 依赖管理工具固定为 `uv`
- MUST 支持 CLI 本地运行
- API 不是 MVP 必需项

### 5.2 Agent Framework Constraints

以下约束必须满足：

- 使用 LangChain 新版模式
- 使用 `create_agent`
- 可以使用 `middleware`
- 可以使用 `tool`
- 可以使用消息对象
- MUST NOT 使用 `langchain_classic.*`
- MUST NOT 使用旧式 chain 组合
- MUST NOT 使用 `RunnableSequence`
- MUST NOT 使用 `prompt | model | parser` 这类 LCEL 链作为业务主流程
- 主流程 MUST 体现为显式调度加状态对象

### 5.3 Design Philosophy

以下原则指导所有设计决策：

- 显式优于隐式
- 状态驱动优于黑盒链式拼接
- 组合优于继承
- 文件工作区优于纯内存临时状态
- 每个核心模块都应可单测

## 6. Product Form

### 6.1 MVP Form

MVP ONLY 需要 CLI 形态，输入一个任务，完成一次 run。

CLI run 的基本行为必须是：

1. 创建独立 workspace
2. 保存任务输入
3. 执行 orchestrator 决策
4. 触发需要的 tool 和 agent
5. 保存中间 notes 和最终输出
6. 返回最终回答摘要与关键路径

### 6.2 Deferred Form

FastAPI MAY 在 MVP 之后加入，但不得影响 CLI 优先级和实现顺序。

## 7. Success Definition

如果满足以下条件，说明产品范围被正确实现：

- 能处理本地文档驱动的 research/report 任务
- 能在有无 retrieval 的情况下跑通同一主流程
- 能把中间产物和最终产物落到 workspace
- 能通过测试验证关键 contracts
