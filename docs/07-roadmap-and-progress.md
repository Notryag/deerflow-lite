# 07 Roadmap And Progress

## Document Role

- Purpose: 记录当前实现进度、下一步任务拆解和推荐执行顺序
- Audience: 实现者、维护者、AI CLI
- Source of truth for: 当前阶段进度、近期任务列表、执行优先级

## 1. Current Snapshot

当前仓库状态：

- 文档体系已拆分并建立 source-of-truth 规则
- CLI MVP 已可运行
- 本地 retrieval 已可用
- stub agent 路径可用
- 真实模型路径已打通
- 测试已覆盖 workspace、file tools、state、retrieval、orchestrator、workflow

当前验证状态：

- `python -m unittest discover -s tests -v` 已通过
- 真实模型路径已完成冒烟验证

## 2. Progress By Track

| Track | Status | Progress | Notes |
| --- | --- | --- | --- |
| 文档治理与拆分 | completed | 100% | 已建立 `01` 到 `06` 主规范 |
| CLI 主流程 | completed | 100% | 可创建 workspace、notes、final output |
| 本地 retrieval | completed | 85% | MVP 可用，质量和索引策略仍可加强 |
| agent 基础能力 | completed | 80% | 结构已稳定，真实模型产出质量仍需优化 |
| file tools | completed | 90% | 安全校验和测试已具备 |
| web search | pending | 20% | 当前仍为 stub |
| python exec | pending | 15% | 已有基础函数，未纳入正式执行分支 |
| 运行健壮性 | pending | 35% | 需要 timeout、fallback、manifest、失败恢复补强 |
| API | deferred | 0% | 不属于当前优先级 |

## 3. Recommended Next Order

建议按以下顺序继续：

1. 完成真实 `search_web` provider 接入
2. 完成 `run_python_code` 的受控执行闭环
3. 补强真实模型路径的健壮性和 fallback
4. 提升 retrieval 与 writer 的输出质量
5. 最后再考虑 API

原因：

- `search_web` 和 `python exec` 是当前主流程中最明显的功能缺口
- 真实模型路径已经跑通，下一步应该把失败处理和质量控制补齐
- 在 MVP 阶段先补全 CLI 工作链条，比新增 API 更有价值

## 4. Task Breakdown

### T1. Real Web Search Provider

Status: `next`

目标：

- 保留当前 `search_web` contract
- 接入至少一个真实 provider
- 在 provider 不可用时自动退回 stub

子任务：

- 在 `settings` 中加入 provider 相关配置
- 为 `search_web` 设计 provider adapter 层
- 实现一个真实 provider
- 保留 deterministic stub 作为 fallback
- 为 provider 成功、失败、fallback 写测试

完成定义：

- orchestrator 决定需要 web search 时可返回真实结构化结果
- 无 key 或 provider 出错时不会让主流程崩掉

### T2. Controlled Python Execution

Status: `next`

目标：

- 让 `run_python_code` 成为正式 workflow 分支
- 保证执行范围、超时和输出边界可控

子任务：

- 为 python execution 增加显式开关配置
- 明确执行目录和允许访问的路径
- 增加 stdout/stderr 长度限制
- 把执行结果写入 workspace
- 为成功、超时、异常写测试

完成定义：

- orchestrator 请求 python execution 时 workflow 能受控执行
- 失败信息能落盘并写回 `RunState.errors`

### T3. Model Reliability And Fallback

Status: `next`

目标：

- 提高真实模型路径在慢 provider 和坏输出场景下的稳定性

子任务：

- 为 `ChatOpenAI` 增加 timeout 和 retry 配置
- 明确模型失败时的 fallback 策略
- 为 structured output 失败增加兜底解析
- 在日志中记录 agent 级耗时和失败原因

完成定义：

- provider 变慢或失败时，流程要么降级完成，要么清晰失败
- 不能出现“命令长时间卡住但没有状态信息”的情况

### T4. Retrieval Quality Upgrade

Status: `later`

目标：

- 提高本地检索的命中质量和索引生命周期管理能力

子任务：

- 让 collection 命名与 `data_dir` 绑定，而不是只依赖 thread id
- 处理索引复用与重建策略
- 增加更多 loader 覆盖和失败提示
- 为结果增加更稳定的摘要和引用生成

完成定义：

- 同一数据目录重复执行时不必总是重建索引
- writer 产出中的 evidence 更稳定

### T5. Output Quality And Artifact Manifest

Status: `later`

目标：

- 提高 notes/final 的可读性，并把 run 产物整理成统一 manifest

子任务：

- 优化 writer 输出模板
- 统一 notes、final、logs 的引用关系
- 增加 `artifacts.json` 或类似清单文件
- 在 CLI 输出中附带更明确的产物摘要

完成定义：

- 用户能快速理解一次 run 生成了什么、依据什么生成

### T6. API Layer

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

如果下一步只做一个主题，优先做 `T1. Real Web Search Provider`。

理由：

- 它已经在 orchestrator contract 里占位
- 它能直接补全 research 任务的核心价值链
- 它比 API 更接近当前产品目标

## 6. Progress Update Rule

更新本文件时，遵守以下规则：

- 完成一个主题后，先更新本文件，再更新相关主规范
- 不在 README 里维护重复的任务列表
- `Status` 只使用 `completed / in_progress / next / later / deferred`
- 如果优先级变化，必须同步更新 `Recommended Next Order`
