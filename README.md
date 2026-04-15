# DPM Agent

一个基于 `DeepAgents` 的个人 Agent 骨架，目标是支持：

- `skills/` 目录式技能加载
- `memory/` 目录式长期记忆注入
- SQLite / PostgreSQL 持久化会话和消息历史
- 可扩展到 CLI / API / Web UI

## 架构概览

- `src/dpm_agent/core/`
  - Agent 运行核心，负责创建 DeepAgents runtime、装配模型、skills、memory、session 文件 backend 和工具提供器
- `src/dpm_agent/core/service.py`
  - 应用服务层，编排一次对话请求：加载历史、调用 agent、归一化事件、写入 SQLite
- `src/dpm_agent/core/events.py`
  - DeepAgents/LangGraph 流事件解析、过滤和去重
- `src/dpm_agent/core/tools.py`
  - Agent 可用工具的扩展接口，后续自定义 tool 通过 `AgentToolProvider` 接入
- `src/dpm_agent/tools/`
  - 内置和示例工具，目前包含四则运算 `calculator_tool`
- `src/dpm_agent/storage/`
  - SQLite 初始化、会话、消息和记忆元数据读写
- `src/dpm_agent/interfaces/cli/`
  - CLI 参数解析、交互命令和终端渲染
- `src/dpm_agent/interfaces/api/`
  - FastAPI REST API，包含同步 `/chat` 和 SSE 流式 `/chat/stream`
- `src/dpm_agent/application/bootstrap.py`
  - 应用装配入口，连接配置、数据库、repository、runtime 和 service
- `src/dpm_agent/*.py`
  - 顶层兼容模块，保留旧导入路径和 `dpm-agent` 命令入口
- `memory/`
  - 默认位于 `data/sessions/<session-id>/memory/`，以文件形式维护该会话的长期记忆，作为 agent 启动时的注入上下文
- `skills/`
  - 默认位于 `data/sessions/<session-id>/skills/`，以 `SKILL.md` 组织该会话可用的技能目录
- `docs/architecture.md`
  - 详细设计说明

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

如果你需要 API：

```bash
pip install -e ".[api]"
```

## 环境变量

配置会从当前环境变量和项目根目录 `.env` 文件读取。统一使用 `AGENT_` 前缀，不再提供额外 fallback 变量。

最小配置示例：

```bash
export AGENT_OPENAI_API_KEY="..."
export AGENT_OPENAI_BASE_URL="https://your-openai-compatible-endpoint/v1"
export AGENT_MODEL="openai:gpt-4.1"
```

完整配置项：

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `AGENT_APP_NAME` | `dpm-agent` | 应用名称，主要用于日志。 |
| `AGENT_DEBUG` | `false` | 开启 debug 日志；CLI/API 的 `--debug` / `--no-debug` 可覆盖。 |
| `AGENT_MODEL` | `openai:gpt-4.1` | LLM 模型。`openai:<model>` 会在请求 provider 时去掉 `openai:` 前缀。 |
| `AGENT_OPENAI_API_KEY` | 空 | OpenAI-compatible API key。 |
| `AGENT_OPENAI_BASE_URL` | `https://api.openai.com/v1` | OpenAI-compatible base URL。 |
| `AGENT_STORAGE_BACKEND` | `sqlite` | 存储后端。支持 `sqlite`、`postgres`、`postgresql`、`pg`。 |
| `AGENT_DB_PATH` | `./data/agent.sqlite3` | SQLite 数据库路径。仅 SQLite 后端使用。 |
| `AGENT_POSTGRES_DSN` | 空 | PostgreSQL DSN。 |
| `AGENT_SESSIONS_DIR` | `./data/sessions` | 会话文件根目录；每个 `thread_id` 会拥有独立 `memory/`、`skills/` 和运行期文件目录。CLI 的 `--sessions-dir` 可覆盖。 |
| `AGENT_API_HOST` | `127.0.0.1` | Python 方式启动 API 时监听的 host；`--host` 可覆盖。 |
| `AGENT_API_PORT` | `8000` | Python 方式启动 API 时监听的 port；`--port` 可覆盖。 |
| `AGENT_API_RELOAD` | `false` | Python 方式启动 API 时是否启用 reload；`--reload` / `--no-reload` 可覆盖。 |
| `AGENT_CORS_ORIGINS` | 空 | API CORS 允许的 origin，逗号分隔。为空时不启用 CORS；本地开发可设为 `*`。 |
| `AGENT_CORS_ALLOW_CREDENTIALS` | `false` | CORS 是否允许 credentials。设为 `true` 时不要把 origins 配成 `*`，应明确列出前端域名。 |
| `AGENT_CORS_ALLOW_METHODS` | `*` | CORS 允许的方法，逗号分隔。 |
| `AGENT_CORS_ALLOW_HEADERS` | `*` | CORS 允许的请求头，逗号分隔。 |
| `AGENT_CUSTOM_ENV_PREFIXES` | `AGENT_CUSTOM_,AGENT_AGENT_,AGENT_TOOL_` | 自定义环境变量前缀（逗号分隔）。匹配到的环境变量会被 `Settings.effective_custom_env` 收集，供后续自定义 Agent/Tool 读取。 |
| `NO_COLOR` | 空 | 设置后关闭 CLI 彩色输出。 |

SQLite 配置示例：

```bash
export AGENT_STORAGE_BACKEND="sqlite"
export AGENT_DB_PATH="./data/agent.sqlite3"
```

PostgreSQL 需要先安装可选依赖：

```bash
pip install -e ".[postgres]"
```

然后配置：

```bash
export AGENT_STORAGE_BACKEND="postgres"
export AGENT_POSTGRES_DSN="postgresql://user:password@localhost:5432/dpm_agent"
```

API 服务配置示例：

```bash
export AGENT_API_HOST="0.0.0.0"
export AGENT_API_PORT="8000"
export AGENT_API_RELOAD="false"
export AGENT_CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:5173"
```

自定义 Agent/Tool 配置环境变量示例：

```bash
export AGENT_AGENT_PROFILE="researcher"
export AGENT_TOOL_SEARCH_TIMEOUT="15"
export AGENT_CUSTOM_FOO="bar"
```

在代码中可通过 `Settings` 读取：

```python
from dpm_agent.config import Settings

settings = Settings()
all_custom = settings.effective_custom_env
agent_custom = settings.effective_custom_agent_env
tool_custom = settings.effective_custom_tool_env
```

默认数据目录是当前目录下的 `data/`。SQLite 对话历史是全局共享数据库，默认是 `./data/agent.sqlite3`；PostgreSQL 使用 `AGENT_POSTGRES_DSN`。每个对话会按 `thread_id` 在 `./data/sessions/` 下创建独立文件目录，里面包含该会话自己的 `skills/` 和 `memory/`。

```text
data/
  agent.sqlite3
  sessions/
    <session-id>/
      memory/
      skills/
```

如果 Agent 或工具链需要写入临时文件、中间结果、下载缓存、生成草稿等运行期产物，直接写到当前 `sessions/<session-id>/` 目录下。`memory/` 只放应该长期注入上下文的记忆文件。

## 运行

启动连续对话：

```bash
dpm-agent
```

开启一个随机 ID 的新会话：

```bash
dpm-agent --new
dpm-agent chat --new
```

指定 sessions 目录：

```bash
dpm-agent --sessions-dir ./data/sessions
dpm-agent chat --sessions-dir ./data/sessions --thread-id work
```

默认不会显示中间请求日志，只显示交互内容。需要调试时可以启动时打开：

```bash
dpm-agent --debug
```

也可以在交互模式中动态开关：

```text
/debug on
/debug off
```

调试日志会打印当前模型、BaseURL、SQLite 路径和 sessions 目录。不会打印 API Key 明文。

当前 OpenAI-compatible 调用强制使用 Chat Completions API，即请求路径应为：

```text
/v1/chat/completions
```

不会使用 Responses API 的 `/v1/responses`。

指定会话 ID 启动连续对话：

```bash
dpm-agent chat --thread-id work
```

交互模式中输入 `/exit` 或 `/quit` 退出。同一个 `thread_id` 的历史会自动从 SQLite 读取并继续。使用 `--new` 会生成随机 `thread_id`，因此会进入一个全新的 `data/sessions/<session-id>/` 目录。

也可以发送单条消息后退出：

```bash
dpm-agent chat --thread-id demo --message "帮我整理今天的任务"
dpm-agent chat --new --message "帮我整理今天的任务"
```

首次运行会自动创建 SQLite 表。

CLI 会区分显示用户输入、Agent 流式输出、思考/步骤、工具调用和工具结果。SQLite 的 `messages` 表会通过 `message_type` 和 `metadata_json` 保存这些不同类型的事件；普通历史续聊只会把用户消息和最终助手消息重新送入模型上下文。

### 在 PyCharm 中启动 CLI

1. `Run | Edit Configurations...` 新建 **Python** 配置。
2. `Run kind` 选择 **Module name**，填入 `dpm_agent.cli`。
3. `Python interpreter` 选择项目 `.venv`。
4. `Working directory` 设为项目根目录。
5. 在 `Environment variables` 中至少配置：
   - `AGENT_OPENAI_API_KEY=...`
   - `AGENT_OPENAI_BASE_URL=https://<your-endpoint>/v1`
   - `AGENT_MODEL=openai:gpt-4.1`
6. `Parameters` 可选：
   - 连续对话：留空（等价 `dpm-agent`）
   - 新会话：`--new`
   - 单条消息：`chat --thread-id demo --message "你好"`

## 自定义 Tool 示例

项目内置了一个四则运算示例工具：

- 位置：[src/dpm_agent/tools/calculator.py](src/dpm_agent/tools/calculator.py)
- 工具名：`calculator_tool`
- 参数：
  - `operation`：`add`、`subtract`、`multiply`、`divide`
  - `left`：左操作数
  - `right`：右操作数

默认 `build_service()` 会注册这个工具，所以 CLI 和 API 启动后 Agent 可以直接使用它。例如：

```text
帮我用工具计算 12.5 乘以 8
```

新增自定义工具的推荐方式：

```python
from collections.abc import Iterable
from typing import Any

from langchain_core.tools import tool


@tool
def my_tool(value: str) -> str:
    """Describe what this tool does for the agent."""
    return value


class MyToolProvider:
    def tools_for_thread(self, thread_id: str) -> Iterable[Any]:
        return (my_tool,)
```

然后在自定义启动代码里传入：

```python
from dpm_agent.application.bootstrap import build_service

service = build_service(tool_providers=(MyToolProvider(),))
```

## API

安装 API 依赖后可启动 FastAPI：

```bash
uvicorn dpm_agent.interfaces.api:app --reload
```

也可以直接通过 Python 启动：

```bash
python -m dpm_agent.interfaces.api --host 127.0.0.1 --port 8000
```

安装为可执行命令后也支持：

```bash
dpm-agent-api --host 127.0.0.1 --port 8000
```

### 在 PyCharm 中启动 API

1. `Run | Edit Configurations...` 新建 **Python** 配置。
2. `Run kind` 选择 **Module name**，填入 `dpm_agent.interfaces.api`（或 `dpm_agent.api`）。
3. `Python interpreter` 选择项目 `.venv`（需先 `pip install -e ".[api]"`）。
4. `Working directory` 设为项目根目录。
5. `Parameters` 可选：`--host 127.0.0.1 --port 8000 --no-reload`。
6. `Environment variables` 可按需配置：`AGENT_API_HOST`、`AGENT_API_PORT`、`AGENT_CORS_ORIGINS` 等。

接口：

- `GET /healthz`：健康检查
- `POST /chat`：同步对话，返回最终回复
- `POST /chat/stream`：SSE 流式对话，逐条返回面向调用方可展示的 `AgentEvent`，结束时发送 `done`

SSE 请求体与同步接口一致：

```json
{
  "thread_id": "default",
  "message": "帮我整理今天的任务"
}
```

SSE 流不会返回 `internal_state` 事件；这类事件属于 DeepAgents/LangGraph 内部状态同步，不适合作为前端可见过程展示。

浏览器跨域访问需要配置 CORS，例如：

```bash
export AGENT_CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:5173"
```

不配置 `AGENT_CORS_ORIGINS` 时，API 不启用 CORS。
