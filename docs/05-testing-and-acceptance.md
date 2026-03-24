# 05 Testing And Acceptance

## Document Role

- Purpose: 定义测试范围、验收门槛和完成定义
- Audience: 工程实现、测试实现、维护者、AI CLI
- Source of truth for: 测试要求、验收标准、完成定义

## 1. Testing Principles

测试必须优先覆盖 contract 和主流程。

原则如下：

- 优先 fake 或 stub 外部依赖
- 不依赖真实 web search
- 不依赖真实线上数据库
- 单测覆盖 contract，集测覆盖链路

## 2. Required Unit Tests

至少必须覆盖以下单元测试：

- workspace 创建
- file tools 路径安全校验
- `RunState` 默认值和更新
- retrieval tool 输出结构
- orchestrator 决策解析

## 3. Required Integration Test

至少必须有一个完整链路集成测试，输入一个简单的 `txt/md` 数据目录，并断言：

- 创建了 workspace
- 生成了 `notes/research.md`
- 生成了 `outputs/final.md`
- `final_answer` 非空

## 4. Minimum Test Count

当前 MVP 的最低要求是：

- 至少 `5` 个测试通过

更推荐的下限是：

- `6` 个以上测试，其中至少 `1` 个为集成测试

## 5. Acceptance Criteria

以下条件同时满足，才算 MVP 完成：

1. 能通过 CLI 接收一个任务
2. 能创建独立 workspace
3. 能根据任务决定是否检索
4. retrieval 作为 tool 工作
5. research agent 能生成 notes
6. writer agent 能生成 `final.md`
7. 最终结果已落盘
8. 至少 5 个测试通过
9. 架构中没有 `langchain_classic`
10. 核心主流程不是 LCEL chain 拼接

## 6. Done Definition

一个功能只有在满足以下条件后才能视为完成：

- 实现代码存在
- 对应 contract 已满足
- 必要测试已补齐
- 文档已同步更新
- 若为 stub，已明确标注限制和后续 TODO
