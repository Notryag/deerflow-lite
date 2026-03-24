# DeerFlow Lite Docs

这个仓库目前以文档为主，目标是定义一个适合 AI CLI 和工程实现协作的 `deerflow-lite` MVP。

文档已经从单文件 PRD 拆成多份规范文件，原则是：

- 根文档只做入口和导航，不承载详细规范
- 每个主题只有一个主文档，避免重复定义
- 用 `MUST / SHOULD / MAY` 表达约束强度，减少歧义
- 文档按任务拆分，便于 AI 按需加载，控制上下文长度

## Read First

完整实现或首次进入仓库时，按这个顺序读取：

1. [docs/01-product-and-scope.md](./docs/01-product-and-scope.md)
2. [docs/02-architecture-and-runtime.md](./docs/02-architecture-and-runtime.md)
3. [docs/03-agent-and-tool-contracts.md](./docs/03-agent-and-tool-contracts.md)
4. [docs/04-implementation-plan.md](./docs/04-implementation-plan.md)
5. [docs/05-testing-and-acceptance.md](./docs/05-testing-and-acceptance.md)
6. [docs/06-documentation-governance.md](./docs/06-documentation-governance.md)
7. [docs/07-roadmap-and-progress.md](./docs/07-roadmap-and-progress.md)
8. [docs/08-codebase-map.md](./docs/08-codebase-map.md)

## Task-Based Reading

按任务裁剪上下文时，建议这样读取：

- 实现项目骨架或主流程：`01 + 02 + 04 + 05`
- 实现 agent、tool、state、workspace：`01 + 02 + 03 + 05`
- 只做测试：`03 + 05`
- 看当前进度和接下来做什么：`04 + 07`
- 快速找代码入口和热点文件：`07 + 08`
- 更新文档结构或规则：`06 + 相关主题文档`

## Source Of Truth

每个主题只在一个文档里做主定义：

| Topic | Source of truth |
| --- | --- |
| 产品目标、MVP 边界、非目标 | [docs/01-product-and-scope.md](./docs/01-product-and-scope.md) |
| 运行时架构、目录结构、workspace、上下文注入策略 | [docs/02-architecture-and-runtime.md](./docs/02-architecture-and-runtime.md) |
| `RunState`、agent 输出、tool I/O 合同 | [docs/03-agent-and-tool-contracts.md](./docs/03-agent-and-tool-contracts.md) |
| 实现阶段、交付顺序、AI 执行方式 | [docs/04-implementation-plan.md](./docs/04-implementation-plan.md) |
| 测试范围、验收标准、完成定义 | [docs/05-testing-and-acceptance.md](./docs/05-testing-and-acceptance.md) |
| 文档写法、冲突处理、维护流程 | [docs/06-documentation-governance.md](./docs/06-documentation-governance.md) |
| 当前进度、下一步任务和执行优先级 | [docs/07-roadmap-and-progress.md](./docs/07-roadmap-and-progress.md) |
| 代码入口、模块位置、任务与文件映射 | [docs/08-codebase-map.md](./docs/08-codebase-map.md) |

## Working Rules

- 如果两个文档内容冲突，以更具体的主题文档为准，不以本文件为准
- 修改实现约束时，必须同步更新对应的 source-of-truth 文档
- 新增功能前，先判断它是否属于 MVP；如果不属于，写入 backlog，不要混入主规范

## Current Intent

`deerflow-lite` 的当前目标是做一个偏 `agentic RAG / research / tool calling` 的本地优先 MVP：

- CLI 优先，API 延后
- 显式编排优先，拒绝黑盒链式主流程
- workspace 落盘优先，便于调试、恢复和后续 UI/API 接入
- 允许 stub，但接口必须稳定、测试必须覆盖

## Current Implementation

当前仓库已经包含一个可运行的 MVP 骨架：

- CLI: `python -m app.cli.main run "...task..." --data-dir ./docs`
- 测试: `python -m unittest discover -s tests -v`
- 默认行为: 没有模型配置时走本地 stub agents；retrieval 使用本地 deterministic embedding 和 JSON vector store
- 使用真实模型时，确保 `.env` 中 `USE_STUB_AGENTS=false`
