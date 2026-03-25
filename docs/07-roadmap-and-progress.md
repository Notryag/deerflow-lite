# 07 Roadmap And Progress

## Document Role

- Purpose: 记录当前实现进度、下一步任务拆解和推荐执行顺序
- Audience: 实现者、维护者、AI CLI
- Source of truth for: 当前阶段进度、近期任务列表、执行优先级

## 1. Current Snapshot

当前仓库状态：

- 文档体系已拆分并建立 source-of-truth 规则
- 文档目标架构已切换到 `Lead Agent + task/subagent`
- `RunState`、workspace、artifact manifest 已完成第一轮 subagent-aware 改造
- `lead_agent` 已接入简单任务直答路径
- `task` 工具和 `subagent registry` 已完成第一轮实现与测试
- 当前代码对复杂任务仍保留旧版 `orchestrator -> research -> writer` 回退流程
- CLI MVP 仍可运行
- 本地 retrieval 已可用
- stub agent 路径可用
- 真实模型路径已打通
- 测试已覆盖新状态对象、manifest、lead agent 直答路径和旧版 workflow 回退路径

当前验证状态：

- `python -m unittest discover -s tests -v` 已通过
- 当前共有 `16` 个测试通过
- 新架构已具备 `T1 + T2` 的基础验证，`T3` 已完成基础实现，但 `executor` 和 lead-agent delegation 还没有接上

## 2. Progress By Track

| Track | Status | Progress | Notes |
| --- | --- | --- | --- |
| 文档治理与拆分 | completed | 100% | 已建立 `01` 到 `06` 主规范 |
| 目标架构文档对齐 | completed | 100% | 目标已切换到 subagent harness |
| 旧版 CLI 主流程 | completed | 100% | 仍可创建 workspace 和 final output |
| harness state / workspace | completed | 100% | 已支持 trace、artifact、manifest，并保留旧字段兼容 |
| lead agent skeleton | completed | 100% | 简单任务可直答，复杂任务仍回退旧流程 |
| 本地 retrieval | completed | 85% | MVP 可用，质量和索引策略仍可加强 |
| file tools | completed | 90% | 安全校验和测试已具备 |
| lead agent runtime | in_progress | 35% | 已有直答路径，尚未接入 task/subagent delegation |
| task tool / registry | in_progress | 60% | registry 与 task tool 已实现，lead-agent wiring 仍未完成 |
| subagent executor | pending | 0% | 尚未开始 |
| web search | pending | 20% | 当前仍为 stub |
| python exec | pending | 15% | 已有基础函数，未纳入新架构 |
| 运行健壮性 | pending | 20% | 新架构的 timeout、manifest、失败恢复尚未实现 |
| API | deferred | 0% | 不属于当前优先级 |

## 3. Recommended Next Order

建议按以下顺序继续：

1. 把 `task` 工具接入 `lead_agent`
2. 实现 `subagent executor` 的并发、超时和单层委派保护
3. 把旧版 research / writer 逻辑迁移成可复用的 subtask prompt 或模板
4. 再做真实 `search_web` provider 和受控执行能力
5. 最后再考虑 API

原因：

- `T1` 和 `T2` 已把基础状态和 lead-agent 入口搭起来
- `T3` 已经提供了 registry 和 task tool，当前真正的缺口是把它们接到 lead agent 和 executor 上
- 在 delegation 主链完成前继续补 provider，收益仍然有限

## 4. Task Breakdown

### T1. Harness State And Workspace Refactor

Status: `completed`

目标：

- 让 `RunState` 支持 task / result / artifact / trace
- 为 workspace 增加 `subagents/manifest.json` 约定
- 保持旧版 CLI 可迁移

子任务：

- 更新 `RunState` 字段
- 设计 manifest 写入格式
- 调整 workspace 目录约定
- 明确旧版字段的兼容或删除策略
- 为状态和 workspace 变更补测试

完成定义：

- 新状态结构可以支撑 subagent runtime
- workspace 可以记录 subagent 产物和执行记录

当前结果：

- `RunState` 已支持 `trace_id`、`subagent_tasks`、`subagent_results`、`artifact_files`
- workspace 已创建 `workspace/`、`subagents/` 并自动生成 `subagents/manifest.json`
- 旧版 notes / output 路径仍保持兼容

### T2. Lead Agent Skeleton

Status: `completed`

目标：

- 用 `lead_agent` 取代固定 orchestrator / research / writer 终态设计

子任务：

- 新建 `lead_agent.py`
- 定义简单任务直答路径
- 定义最终输出写入路径
- 保留可迁移的 prompt / fallback 逻辑

完成定义：

- 简单任务在不创建 subagent 的情况下可完成
- `outputs/final.md` 可由 lead agent 直接生成

当前结果：

- 已新增 `lead_agent.py`
- 简单任务会被 `lead_agent` 直接完成并写出 `outputs/final.md`
- 复杂任务暂时继续回退到旧版 `orchestrator -> research -> writer` 流程

### T3. Task Tool And Registry

Status: `in_progress`

目标：

- 提供稳定的 subagent 创建入口和类型映射

子任务：

- 实现 `task` 工具 contract
- 实现 registry 与类型校验
- 先落地 `general-purpose`
- 预留 `bash`
- 为非法类型、空 prompt、默认值写测试

完成定义：

- `lead_agent` 能创建并跟踪 subagent task
- `task` 返回结构化结果

当前结果：

- 已新增 `app/subagents/registry.py`
- 已新增 `app/tools/task_tool.py`
- registry 已支持 `general-purpose` 和 `bash`
- `task` 工具已支持参数校验、类型校验、默认 `max_turns` 和 manifest 落盘
- lead-agent wiring 仍未完成，因此本主题仍处于进行中

### T4. Subagent Executor

Status: `next`

目标：

- 实现 subagent 生命周期管理

子任务：

- 实现 executor
- 增加最大并发限制
- 增加超时控制
- 禁止 nested delegation
- 补充日志和 trace 写入

完成定义：

- 1 到多个 subagent 可被稳定执行
- 超时和失败有清晰结果

### T5. Legacy Logic Migration

Status: `later`

目标：

- 把现有 `research_agent` / `writer_agent` 中能复用的逻辑迁移为模板、prompt 或 helper

子任务：

- 提取 notes / summary 渲染逻辑
- 识别可复用的 evidence 生成逻辑
- 清理固定三段式依赖

完成定义：

- 旧版固定角色代码不再是主流程依赖
- 可复用逻辑被保留而不是丢失

### T6. Real Web Search And Controlled Execution

Status: `later`

目标：

- 补全 subagent 在真实工具上的执行能力

子任务：

- 真实 `search_web` provider
- `run_python_code` 或 shell 执行闭环
- 为工具失败与 fallback 写测试

完成定义：

- subagent 使用真实工具时仍可控、可回退

### T7. API Layer

Status: `deferred`

目标：

- 在 CLI 足够稳定后补上最小 FastAPI 层

子任务：

- 设计 `POST /runs`
- 设计 `GET /runs/{id}`
- 设计 `GET /runs/{id}/artifacts`
- 复用 CLI workflow 而不是复制逻辑

完成定义：

- API 只是同一 runtime 的另一种入口，不引入第二套逻辑

## 5. Current Focus Recommendation

如果下一步只做一个主题，优先做 `T3. Task Tool And Registry`。

理由：

- lead agent 已经有了可用入口，下一步就该接上 delegation 的创建接口
- registry 会决定 subagent 类型、工具集和限制策略，是 executor 的前置条件
- 只有 `task` contract 落地后，后续 executor 和 subagent 测试才有稳定依附点

## 6. Progress Update Rule

更新本文件时，遵守以下规则：

- 完成一个主题后，先更新本文件，再更新相关主规范
- 不在 README 里维护重复的任务列表
- `Status` 只使用 `completed / in_progress / next / later / deferred`
- 如果优先级变化，必须同步更新 `Recommended Next Order`
