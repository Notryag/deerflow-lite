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
- `lead_agent` 已统一走 LangChain `create_agent(..., tools=[...])` 路径
- `task` 工具、`subagent registry` 和最小 `subagent executor` 已完成第一轮实现与测试
- `lead_agent` 在真实模型路径下已改为通过 `task` tool-calling 决定是否委派
- 本地无 API 时，lead agent 和 subagent 统一复用 fake tool-calling model，而不是单独的程序化 stub 分支
- `subagent executor` 已补上批量并发上限检查和 nested delegation contract 校验
- `subagent executor` 已补上线程池调度加子进程 worker、timeout 结果回填
- 主 workflow 对复杂任务已经直接创建 `general-purpose` subagent，不再依赖固定 `orchestrator -> research -> writer` 链路
- `app/subagents/rendering.py` 已落地第一版共享 helper 层，research / report 产出逻辑开始同时服务 legacy agent 和 subagent runtime
- `app/tools/reporting.py` 已承接 fallback workflow 的 notes / final report 产出
- middleware / tool 边界已经记入主规范：middleware 只管上下文与约束，能力和业务决策必须回到 tool-calling
- `app/tools/langchain_toolset.py` 已把 retrieval / web / file / python / task 封装成可挂载的 `@tool` 集合，并接到 `lead_agent` 真实模型路径
- subagent executor 已开始按 registry 解析 runtime tool bundle，并把实际工具面写进 subagent task/result artifact
- `app/subagents/runner.py` 已替代脚本式 built-in worker，subagent 现在在子进程里运行真实 `create_agent(..., tools=[...])`
- CLI MVP 仍可运行
- 本地 retrieval 已可用
- 本地 fake tool-calling agent 路径可用
- 真实模型路径已打通
- 测试已覆盖新状态对象、manifest、统一 lead-agent runtime、共享 helper 和复杂任务 delegation 路径

当前验证状态：

- `python -m unittest discover -s tests -v` 已通过
- 当前共有 `42` 个测试通过
- 新架构已具备 `T1` 到 `T4` 的更完整验证，`T5` 已进入“去除固定 legacy agent 主流程依赖”的第二轮迁移

## 2. Progress By Track

| Track | Status | Progress | Notes |
| --- | --- | --- | --- |
| 文档治理与拆分 | completed | 100% | 已建立 `01` 到 `06` 主规范 |
| 目标架构文档对齐 | completed | 100% | 目标已切换到 subagent harness |
| 旧版 CLI 主流程 | completed | 100% | 仍可创建 workspace 和 final output |
| harness state / workspace | completed | 100% | 已支持 trace、artifact、manifest，并保留旧字段兼容 |
| lead agent skeleton | completed | 100% | 简单任务可直答，复杂任务可落到 fallback subagent 路径 |
| 本地 retrieval | completed | 85% | MVP 可用，质量和索引策略仍可加强 |
| file tools | completed | 90% | 安全校验和测试已具备 |
| lead agent runtime | in_progress | 88% | lead 与本地 fake model 已统一走 `create_agent(..., tools=[...])`，剩余工作主要是继续清理 legacy 参考实现 |
| task tool / registry | completed | 100% | registry、task tool、lead-agent wiring 已打通 |
| subagent executor | in_progress | 96% | 已有线程池调度、子进程 agent worker、timeout 终止、并发上限检查、nested delegation 校验，并已切到真实 tool-calling runtime |
| legacy logic migration | in_progress | 85% | 主 workflow 已摆脱固定 `research/writer` 依赖，主缺口变成移除 `orchestrator` 的残留参考地位 |
| web search | pending | 20% | 当前仍为 stub |
| python exec | pending | 15% | 已有基础函数，未纳入新架构 |
| 运行健壮性 | pending | 20% | 新架构的 timeout、manifest、失败恢复尚未实现 |
| API | deferred | 0% | 不属于当前优先级 |

## 3. Recommended Next Order

建议按以下顺序继续：

1. 继续清理 legacy 参考实现，把 `orchestrator` / `research_agent` / `writer_agent` 的残留地位进一步边缘化
2. 再做真实 `search_web` provider 和受控执行能力
3. 补强 subagent 的多轮工具能力与观测记录
4. 最后再考虑 API

原因：

- `T1`、`T2`、`T3` 已经把状态、lead-agent、task contract 串起来
- 当前 delegation 主链已经可跑，executor 也已经有基础隔离和 timeout 终止
- 脚本式 subagent worker 已删除，当前核心缺口变成 legacy 代码收口和真实 provider
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
- 真实模型路径下，是否委派由 `lead_agent` 通过 `task` tool-calling 决定
- lead agent 在真实模型和本地 fake model 下都走同一套 `create_agent(..., tools=[...])` 路径
- 当 `lead_agent` 未完成任务时，workflow 才会进入 fallback subagent 路径

### T3. Task Tool And Registry

Status: `completed`

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
- `lead_agent` 已能创建并跟踪 subagent task

### T4. Subagent Executor

Status: `in_progress`

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

当前结果：

- 已新增 `app/subagents/executor.py`
- 已新增 `app/subagents/runner.py`
- executor 已能执行单个或多个 task、回填 task/result 状态并写入 `subagents/{task_id}/result.md`
- executor 已有线程池调度
- executor 已有子进程 worker 隔离
- executor 已有批量并发上限检查
- executor 已有 timeout 结果回填
- executor 已显式拒绝 nested delegation contract
- subagent worker 已切到真实 LangChain tool-calling runtime，因此本主题接近完成

### T5. Legacy Logic Migration

Status: `in_progress`

目标：

- 把现有 `research_agent` / `writer_agent` 中能复用的逻辑迁移为共享 helper
- 让 research / report 渲染逻辑同时服务 legacy agent 和 subagent runtime

子任务：

- 提取 notes / summary 渲染逻辑
- 提取 evidence 归一化和 markdown 渲染逻辑
- 让 subagent runner 复用相同的 report helper
- 继续提取 prompt 模板和最终汇总逻辑
- 用 tool / helper 替换 workflow 中剩余的固定 `ResearchAgent` / `WriterAgent` 依赖
- 清理固定三段式依赖

完成定义：

- 旧版固定角色代码不再独占 report / research 渲染逻辑
- legacy agent 和 subagent runtime 复用同一组 helper
- 可复用逻辑被保留而不是丢失

当前结果：

- 已新增 `app/subagents/rendering.py`
- 已新增 `app/tools/reporting.py`
- `general-purpose` 默认上限已提升到 `50` turns，`bash` 提升到 `30` turns
- `research_agent` 与 `writer_agent` 已改为复用共享 helper
- `runner.py` 已复用共享 subagent summary / artifact 渲染逻辑
- `run_task` 的 fallback research / final report 产出已改走 `reporting.py`
- `run_task` 的复杂任务 fallback 已直接创建 `general-purpose` subagent
- executor 已会按 registry 过滤 subagent runtime tools，并把工具面写入 result artifact
- subagent runtime 已切到真实模型驱动 tool-calling worker
- 共享层目前已覆盖数据形状、summary、markdown 渲染和 prompt 模板；主缺口是继续收口 legacy agent 的残留角色定位

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

如果下一步只做一个主题，优先继续做 `T5. Legacy Logic Migration`。

理由：

- delegation 主链已经打通，executor 也已经具备基础可控性
- prompt 模板和 fallback 产出已经开始 tool 化，下一步最有价值的是继续清理程序侧 heuristics
- 这样后续接真实 tool/provider 时，workflow 和 subagent runtime 都能沿用同一套输出 contract
- 先统一产出层，再扩工具层，能减少后续重构次数

## 6. Progress Update Rule

更新本文件时，遵守以下规则：

- 完成一个主题后，先更新本文件，再更新相关主规范
- 不在 README 里维护重复的任务列表
- `Status` 只使用 `completed / in_progress / next / later / deferred`
- 如果优先级变化，必须同步更新 `Recommended Next Order`
