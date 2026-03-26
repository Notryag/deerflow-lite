# 04 Implementation Plan

## Document Role

- Purpose: 给工程实现和 AI CLI 提供阶段化执行计划与交付方式
- Audience: 实现者、AI CLI、维护者
- Source of truth for: 开发顺序、阶段目标、交付要求

## 1. Execution Strategy

实现 MUST 优先把现有旧版 MVP 迁移成可运行的 subagent harness，不得先做平台化设计。

执行原则：

- 先 contract，后重构
- 先 `lead_agent + task` 骨架，后补 subagent 类型
- 先 CLI，后 API
- 先显式 workflow，后抽象图模型
- 能 stub 的能力可以 stub，但 contract 必须稳定

## 2. Phase Plan

### Phase 0: Legacy Baseline

必须完成：

- 保持当前 CLI 可运行
- 保持现有 workspace / 基础测试可用
- 明确旧版固定流水线只是迁移起点

阶段完成条件：

- 现有旧版测试可通过
- 文档已明确目标架构与当前实现差距

### Phase 1: Harness Foundations

必须完成：

- `RunState` 升级为支持 subagent task / result
- workspace 增加 subagent manifest 约定
- `lead_agent` 骨架
- 基本 trace / logging 字段

阶段完成条件：

- CLI 能创建新结构的 thread workspace
- `lead_agent` 能处理简单任务并写出 `final.md`
- 新旧状态迁移有清晰路径

### Phase 2: Delegation Interface

必须完成：

- `task` 工具
- `subagent registry`
- 至少一个内置 `general-purpose` subagent 类型

阶段完成条件：

- `lead_agent` 能通过 `task` 创建 subagent
- `task` 返回结构化结果
- 无效 `subagent_type` 会被稳定拒绝

### Phase 3: Subagent Execution

必须完成：

- `subagent executor`
- 最大并发控制
- 超时控制
- 单层委派限制

阶段完成条件：

- 至少一个任务能成功委派给 1 到多个 subagent
- subagent 共享 workspace 但消息上下文隔离
- 超时和失败能写回状态

### Phase 4: Synthesis And Artifacts

必须完成：

- lead agent 综合 subagent 结果
- `subagents/manifest.json`
- artifact 路径回填到 `RunState`
- 将旧版 research / writer 逻辑迁移成可复用 prompt 或模板

阶段完成条件：

- 一次完整任务可以跑通
- 产物全部落盘
- 最终输出能引用 subagent 结果

### Phase 5: Tool Quality

必须完成：

- 真实 `search_web` provider
- 受控 shell / python 执行闭环
- artifact 引用质量优化

阶段完成条件：

- subagent 可以稳定使用真实工具
- provider 失败时能 fallback 或清晰报错

### Deferred Backlog

以下内容放入后续阶段，不进入当前 MVP：

- FastAPI
- graph engine
- 长期 memory
- 多租户与权限系统
- 多层递归 subagent

## 3. AI Execution Rules

AI CLI 或自动化实现时，必须遵守以下规则：

- 先同步 `01/02/03` contract，再动实现
- 重构时尽量分层替换，不要一次性推倒全部旧代码
- 每阶段结束前先校验 contract 和测试
- 不得引入 `langchain_classic`
- 不得把业务主流程改成 LCEL chain 串联
- 对暂未完成能力，使用 stub 而不是跳过接口
- 不得把固定专用 agent 重新定义成目标终态

## 4. Delivery Contract

实现交付时，应按以下顺序输出：

1. 项目结构树
2. 关键设计说明
3. 完整代码文件
4. 测试代码
5. 运行方式
6. 下一步 TODO

## 5. Change Discipline

如果实现过程中发生工程取舍，必须优先满足以下顺序：

1. 简洁
2. 清晰
3. 可维护
4. 可扩展

不得为了“看起来完整”而牺牲当前可运行性。

## 6. Current MVP Status

截至当前版本，已经完成的是旧版基础能力，而不是目标中的 subagent harness：

- 项目骨架
- `RunState`、workspace、logger
- file tools、web search tool、reporting tool
- 旧版固定流水线残留
- 旧版 `run_task` workflow
- CLI 入口
- 基础测试

当前明确保留为 stub 或轻量实现的部分：

- web search provider
- online model path 在无 API key 时退回 stub agents
- embedding 和 vector store 使用本地轻量实现，而不是外部服务
- subagent runtime 尚未实现
