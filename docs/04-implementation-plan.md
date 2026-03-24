# 04 Implementation Plan

## Document Role

- Purpose: 给工程实现和 AI CLI 提供阶段化执行计划与交付方式
- Audience: 实现者、AI CLI、维护者
- Source of truth for: 开发顺序、阶段目标、交付要求

## 1. Execution Strategy

实现 MUST 优先交付可运行 MVP，不得先做平台化设计。

执行原则：

- 先骨架，后能力
- 先 contract，后优化
- 先 CLI，后 API
- 先显式流程，后抽象图模型
- 能 stub 的能力可以 stub，但 contract 必须稳定

## 2. Phase Plan

### Phase 1: Project Skeleton

必须完成：

- 项目骨架
- `settings`
- `RunState`
- `workspace`
- CLI entry

阶段完成条件：

- CLI 能接收任务字符串
- 能创建 thread workspace
- 能初始化状态对象并落盘输入

### Phase 2: Core Tools

必须完成：

- file tools
- retrieval pipeline
- retrieval tool

阶段完成条件：

- 文件工具具备安全校验
- retrieval 能从本地数据返回结构化结果
- tool 输出符合 contract

### Phase 3: Agents

必须完成：

- orchestrator agent
- research agent
- writer agent

阶段完成条件：

- orchestrator 能输出结构化决策
- research agent 能产出 notes
- writer agent 能产出 `final.md`

### Phase 4: Workflow Integration

必须完成：

- `run_task` 主流程
- 集成测试
- 最终打磨

阶段完成条件：

- 一次完整任务可以跑通
- 产物全部落盘
- 测试通过

### Deferred Backlog

以下内容放入后续阶段，不进入当前 MVP：

- web search 真正 provider
- python exec tool
- FastAPI
- graph engine

## 3. AI Execution Rules

AI CLI 或自动化实现时，必须遵守以下规则：

- 先建立目录结构，再补模块
- 每阶段结束前先校验 contract 和测试
- 不得引入 `langchain_classic`
- 不得把业务主流程改成 LCEL chain 串联
- 对暂未完成能力，使用 stub 而不是跳过接口

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
