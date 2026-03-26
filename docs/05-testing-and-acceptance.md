# 05 Testing And Acceptance

## Document Role

- Purpose: 定义测试范围、验收门槛和完成定义
- Audience: 工程实现、测试实现、维护者、AI CLI
- Source of truth for: 测试要求、验收标准、完成定义

## 1. Testing Principles

测试必须优先覆盖 contract、委派边界和主流程。

原则如下：

- 优先 fake 或 stub 外部依赖
- 不依赖真实 web search
- 不依赖真实线上数据库
- 单测覆盖 contract，集测覆盖 lead-agent 到 subagent 的链路

## 2. Required Unit Tests

至少必须覆盖以下单元测试：

- workspace 创建与路径安全
- `RunState` 默认值和 task / result 更新
- subagent registry 配置解析
- `task` 工具参数校验与结果结构
- `subagent executor` 的超时与并发保护
- 单层委派限制是否生效
- workspace file tools 输出结构

## 3. Required Integration Tests

至少必须有以下两类集成测试：

### 3.1 Simple Task Without Delegation

输入一个简单任务，并断言：

- 创建了 workspace
- 没有创建 subagent 或只创建了空 manifest
- 生成了 `outputs/final.md`
- `final_answer` 非空

### 3.2 Delegated Task With Subagents

输入一个需要拆解的任务，并断言：

- 创建了 workspace
- 生成了 `subagents/manifest.json`
- 至少一个 subagent 结果被记录
- 生成了 `outputs/final.md`
- `final_answer` 非空

## 4. Minimum Test Count

当前目标架构的最低要求是：

- 至少 `7` 个测试通过

更推荐的下限是：

- `9` 个以上测试，其中至少 `2` 个为集成测试

## 5. Acceptance Criteria

以下条件同时满足，才算 MVP 完成：

1. 能通过 CLI 接收一个任务
2. 能创建独立 workspace
3. `lead_agent` 能直接完成简单任务
4. `lead_agent` 能通过 `task` 创建 subagent
5. subagent 共享 workspace，但上下文隔离
6. nested subagent 被禁止
7. 最终结果已落盘
8. 至少 7 个测试通过
9. 架构中没有 `langchain_classic`
10. 核心主流程不是 LCEL chain 拼接

## 6. Done Definition

一个功能只有在满足以下条件后才能视为完成：

- 实现代码存在
- 对应 contract 已满足
- 必要测试已补齐
- 文档已同步更新
- 若为 stub，已明确标注限制和后续 TODO
