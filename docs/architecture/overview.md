# Architecture Overview

## 定位

North Agent 是可嵌入 Python 产品的轻量 Agent Runtime。它负责模型、工具、Skill、运行事件、
上下文和持久化的通用执行契约，不负责宿主产品的身份、权限、业务数据、计费或界面。

项目不是一次性 Agent Demo，也不以复制其他 Agent 产品的完整功能为目标。能力演进由真实宿主
任务推动，并沉淀为可复用 Runtime 边界。

## 总体架构

```text
Host CLI / API / Worker
  -> north public API
  -> Agent / Runtime / Middleware
  -> LangChain + LangGraph
  -> Model / Tools / Checkpointer

Runtime Event Sink
  <- model/tool lifecycle and token usage
  -> host database, logs, metrics or stream transport
```

依赖方向始终为 `host -> north`。North 不反向读取宿主业务模型，也不推断宿主仓库路径。

## 稳定边界

### 宿主装配

- `AppConfig` 承载 Runtime 配置和宿主选择的路径
- `build_agent` 装配模型、Skill、Checkpointer 和宿主提供的 Plugin
- Plugin 负责注册工具、Middleware、Provider 和 `AgentDefinition`；子 Agent 在委派时懒创建
- `invoke_agent_once` 提供产品无关的单次执行入口
- `AppClient` 提供示例聊天和流式 Run 封装

### 运行状态

- `thread_id` 隔离持续任务的 Checkpoint 和文件资源
- `ThreadState` 只包含 Runtime 共享状态，不承载产品会话模型
- 上传、Workspace、Output 和 Memory 通过 Resource URI 暴露

### 可观测性

- 模型与工具调用转换为稳定 Runtime Event
- Token 用量在 Runtime 层归一化
- 子 Agent 模型调用在同一父 Run 中使用 `subagent:<name>` 归属
- 宿主决定事件持久化、传输、审计和计费方式

### 运行保护

- 工具错误转换为可恢复结果
- 重复工具循环可以截断
- 缺少关键信息时通过结构化澄清暂停
- 上下文摘要可通过 Hook 交给宿主归档

## 已验证任务闭环

```text
Web question -> search/fetch -> Markdown report -> Artifact
Uploaded file -> discover/read -> inline answer or report -> Artifact
```

这些闭环用于验证 Runtime 契约，不限定宿主产品方向。

## 演进规则

1. 新能力必须由可复现的宿主问题或任务闭环证明价值
2. 产品特有逻辑留在宿主，通用执行契约才进入 Harness
3. 公开 API、持久化、并发和执行边界优先保持明确和可测试
4. Sandbox、Memory 产品模型、MCP 和 Subagent 不因参考项目存在而自动进入路线图
