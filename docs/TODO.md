# North Agent TODO

这份文件只做一件事：

> 维护当前阶段可直接执行的任务清单。

已完成事项归档到 [TODO_ARCHIVE](./TODO_ARCHIVE.md)。

如果需要看阶段原因、优先级来源、长期演进顺序，请看 `docs/LITE_EVOLUTION_PLAN.md`。

如果需要看模块职责、目录边界、未来目标结构，请看 `docs/LITE_ARCHITECTURE.md`。

## 快速索引

- 查已完成历史：看 [TODO_ARCHIVE](./TODO_ARCHIVE.md)
- 判断下一阶段：看 [roadmap](./plan/roadmap.md)
- 判断代码执行能否开始：看 [code-execution-boundary](./architecture/code-execution-boundary.md)

## 使用规则

- `[ ]` 未完成，属于当前或近期应做任务
- `[x]` 已完成，一般不保留在本文件主体，完成后移动到归档
- `[-]` 明确暂缓，不属于当前阶段主线

每个任务都应尽量包含：

1. 目标
2. 关联文件
3. 完成标准

后续 AI 更新本文件时，按这几个规则处理：

1. 完成代码后，优先回写本文件中的 checkbox 状态
2. 如果实际改动文件与 TODO 中列出的文件不同，要同步修正“关联文件”
3. 完成项应移动到 `docs/TODO_ARCHIVE.md`
4. 如果改动改变了阶段顺序，更新 `docs/LITE_EVOLUTION_PLAN.md`
5. 如果改动改变了模块边界，更新 `docs/LITE_ARCHITECTURE.md`

默认不需要完整阅读 `docs/LITE_EVOLUTION_PLAN.md` 和 `docs/LITE_ARCHITECTURE.md`。

只有当任务涉及优先级调整或模块边界变化时，才需要补读。

## 当前阶段目标

以下闭环已经打通：

> Web 调研 -> 信息整理 -> Markdown 报告 -> artifact 输出

> 文件输入 -> 文件发现 -> 文件读取 -> Markdown 报告 -> artifact 输出

架构收敛已经完成：

> 可复用 Runtime 位于 `packages/harness/north`，`app` 只负责示例 CLI 宿主装配

## Active TODO

当前没有待实现的 Active TODO。新任务应由真实宿主需求产生，并先确认是否符合 Runtime 边界。

## Parked

- [-] S1. sandbox
  原因：
  当前没有经过验证的宿主需求和隔离执行器，不直接引入完整 Sandbox。

- [-] S2. memory
  原因：
  当前还没有形成值得持久化的长期任务流。

- [-] S3. MCP
  原因：
  现在优先做内建最小工具链，不引入额外接入面。

- [-] S4. vision
  原因：
  当前闭环不依赖图像理解。

- [x] S5. title middleware
  已由 Lexora 的真实宿主需求驱动完成。标题是可选的通用 `ThreadState` 元数据能力，
  在首轮 Agent Run 的 middleware hook 中生成，不创建独立 Run 或消息；宿主负责把 state
  投影到产品自己的会话元数据。

- [-] S5b. todo middleware
  原因：
  尚无第二个真实宿主需求，不提前泛化。

- [-] S7. 大而全工具注册系统
  原因：
  现在应先让最小工具链跑通，而不是提前泛化。
