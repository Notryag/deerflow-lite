# North Agent

North Agent 是一个可嵌入 Python 产品的轻量 Agent Runtime。它把模型调用、工具执行、
Skills、运行事件和上下文持久化收敛到稳定边界，让宿主应用专注于业务、身份、数据和界面。

## 核心能力

- 基于 LangChain / LangGraph 的 Agent 装配与单次调用
- 同步聊天、流式输出和独立 Run 生命周期
- 工具注册、异步中间件、错误策略与循环检测
- 本地 Skill 发现、目录过滤和按需加载
- Memory、SQLite、PostgreSQL Checkpointer
- 上下文摘要压缩与宿主归档 Hook
- 首轮对话标题生成 Middleware，可选独立标题模型并自动写入 checkpoint state
- 模型及工具调用事件、Token 用量归一化
- 上传文件、Workspace、Output 等资源 URI

文件分析遵循按需闭环：发现线程文件、读取相关内容、直接回答或生成 Markdown 报告，
并通过 Artifact 把持久结果交还给宿主。

## 架构边界

```text
宿主应用
  -> north public API
  -> Agent / Runtime / Middleware
  -> LangChain + LangGraph
  -> Model / Tools / Checkpointer

RuntimeEventSink
  <- 模型与工具运行事件
  -> 宿主自己的数据库、SSE 或日志系统
```

North Agent 负责通用运行能力，但不负责：

- 用户、租户、权限和会话产品模型
- HTTP Gateway、页面或面向用户的文案
- 产品数据库、计费规则和 Token 预算
- 具体业务工具及其领域对象

## 快速开始

要求 Python 3.11+ 和 [uv](https://docs.astral.sh/uv/)。

```bash
git clone https://github.com/Notryag/north-agent.git
cd north-agent
cp .env.example .env
uv sync
```

最小环境变量：

```dotenv
OPENAI_API_KEY=your_openai_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
APP_MODEL_NAME=openai:gpt-4o-mini
```

运行 CLI：

```bash
uv run north-agent "解释一下 Agent Runtime 的职责"
uv run north-agent --stream --show-events "调研 LangGraph 的流式事件设计"
```

## Python 调用

```python
from pathlib import Path

from north import AppClient, AppConfig

app_root = Path(__file__).resolve().parent
config = AppConfig.from_env(
    env_path=app_root / ".env",
    skills_dir=app_root / "skills",
    thread_base_dir=app_root / ".north-data",
)
config.validate()

client = AppClient(config)
response = client.chat("给我一个工具调用可靠性检查清单")
print(response)
```

`north` 不推断宿主仓库根目录。环境文件、Skill 目录和线程文件目录均由宿主显式选择，
也可以分别通过 `APP_SKILLS_DIR` 和 `APP_THREAD_BASE_DIR` 覆盖。

产品服务可以使用更窄的单次调用入口，并注入自己的工具、Checkpointer 和事件接收器：

```python
from north import invoke_agent_once

result = await invoke_agent_once(
    agent_factory=lambda: product_agent,
    graph_input={"messages": product_messages},
    config={"configurable": {"thread_id": thread_id}},
    context=runtime_context,
    event_sink=event_sink,
)
```

## 作为依赖使用

`north` 尚未发布到 PyPI。使用方应固定 Git commit，保证构建可复现：

```toml
[project]
dependencies = ["north[postgres]"]

[tool.uv.sources]
north = {
  git = "https://github.com/Notryag/north-agent.git",
  rev = "<commit-sha>",
  subdirectory = "packages/harness"
}
```

可选依赖：

- `north[sqlite]`：本地持久化 Checkpointer
- `north[postgres]`：服务端 PostgreSQL Checkpointer

## 项目结构

```text
packages/harness/north/   可复用 Runtime 包
app/                      示例 CLI 宿主
skills/                   示例 Skills
tests/                    Runtime 与边界测试
docs/                     架构、演进计划和设计记录
```

重要入口：

- `north.invoke_agent_once`：产品服务的一次性 Agent 调用
- `north.stream_agent_once`：标准化 `values`、`messages`、`custom` graph 流
- `north.AppClient`：聊天与流式客户端
- `north.RuntimeJournal`：模型和工具运行事件
- `north.make_checkpointer`：Memory、SQLite、PostgreSQL 持久化
- `north.NorthSummarizationMiddleware`：上下文压缩
- `north.TitleMiddleware`：首轮对话标题生成；宿主决定是否启用及如何同步产品元数据

标题能力默认关闭。宿主可以通过 `AppConfig` 启用，标题在同一个 Agent Run 的
`after_model` 阶段生成并写入 `ThreadState.title`，不会创建额外 Run 或消息：

```python
config = AppConfig(
    model_name="openai:gpt-4o-mini",
    auto_title_enabled=True,
    title_model_name="openai:gpt-4o-mini",
    title_max_chars=32,
)
```

未配置可用标题模型或模型调用失败时，中间件使用首条用户消息的有界截取作为兜底。

## 开发

```bash
uv sync --all-extras
uv run pytest -q
```

架构边界见 [docs/architecture](./docs/architecture/README.md)，当前任务见
[docs/TODO.md](./docs/TODO.md)。

## 状态

North Agent 仍处于早期开发阶段。公开接口会继续围绕真实宿主应用收敛；提交兼容性要求较高
的集成前，请固定经过验证的 commit。

## 参考项目

- [DeerFlow](https://github.com/bytedance/deer-flow)
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [LangChain](https://github.com/langchain-ai/langchain)
