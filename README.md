# Agents

一个基于 `DeepAgents` 的个人 Agent 骨架，目标是支持：

- `skills/` 目录式技能加载
- `memory/` 目录式长期记忆注入
- SQLite / PostgreSQL 持久化会话和消息历史
- 可扩展到 CLI / API / Web UI

## 架构概览

- `src/agents/core/`
  - Agent 运行核心，负责创建 DeepAgents runtime、装配模型、skills、memory、session 文件 backend、工具提供器和配置化 Agent 定义
- `src/agents/core/definitions.py`
  - `agents.yaml` 配置模型、环境变量注入、引用校验和 Agent registry loader
- `src/agents/core/service.py`
  - 应用服务层，编排一次对话请求：加载历史、调用 agent、归一化事件、写入 SQLite
- `src/agents/core/events.py`
  - DeepAgents/LangGraph 流事件解析、过滤和去重
- `src/agents/core/tools.py`
  - Agent 可用工具的扩展接口，后续自定义 tool 通过 `AgentToolProvider` 接入
- `src/agents/tools/`
  - 内置和示例工具，目前包含四则运算 `calculator_tool`
- `src/agents/storage/`
  - SQLite 初始化、会话、消息和记忆元数据读写
- `src/agents/interfaces/cli/`
  - CLI 参数解析、交互命令和终端渲染
- `src/agents/interfaces/api/`
  - FastAPI REST API，包含同步 `/chat` 和 SSE 流式 `/chat/stream`
- `src/agents/application/bootstrap.py`
  - 应用装配入口，连接配置、数据库、repository、runtime 和 service
- `src/agents/*.py`
  - 顶层兼容模块，保留旧导入路径和 `agents` 命令入口
- `memory/`
  - 默认位于 `data/sessions/<user-id>/<session-id>/memory/`，以文件形式维护该用户会话的长期记忆，作为 agent 启动时的注入上下文
- `skills/`
  - 默认位于 `data/sessions/<user-id>/<session-id>/skills/`，以 `SKILL.md` 组织该用户会话可用的技能目录
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

## 运行时配置（agents.yaml / settings 节）

运行时配置统一从 `agents.yaml` 顶层的 `settings` 节读取（和 `llms/tools/agents` 在同一个文件）。不再直接从 `.env` 或 `AGENT_*` 环境变量加载配置。

如果你希望在 YAML 中引用环境变量，可以使用 `${ENV_NAME}` 语法（仅支持这种形式，不支持 `:-` 默认值 fallback）。

完整配置示例见仓库根目录 `agents.yaml` 的 `settings` 节。

```yaml
settings:
  app_name: agents
  debug: false
  default_user_id: default
  storage:
    backend: sqlite
    postgres_dsn: ${AGENT_POSTGRES_DSN}
    db_path: ./data/agent.sqlite3
    sessions_dir: ./data/sessions
  api:
    host: 127.0.0.1
    port: 8000
    reload: false
    cors:
      origins: ""
      allow_credentials: false
      allow_methods: "*"
      allow_headers: "*"
    stream:
      include_event_name: false
      include_assistant_message: false
```

`settings.api.stream` 说明：

- `include_event_name: false`（默认）：SSE 仅输出 `data: {...}`，不输出 `event: ...` 行。
- `include_assistant_message: false`（默认）：流式过程中只发送 `thinking` 和 `assistant_delta`，避免在尾部重复发送最终 `assistant_message`。

常用启动方式：

```bash
agents --agent-config ./agents.yaml
agents-api --agent-config ./agents.yaml
```

在代码中可通过 `Settings.load()` 读取：

```python
from agents.config import Settings

settings = Settings.load()
print(settings.effective_sessions_dir)
print(settings.effective_storage_backend)
```

默认数据目录是当前目录下的 `data/`。SQLite 对话历史是全局共享数据库，默认是 `./data/agent.sqlite3`；PostgreSQL 使用 `agents.yaml` 中 `settings.storage.postgres_dsn`。每个对话会按 `user_id` 和 `thread_id` 在 `./data/sessions/` 下创建独立文件目录，里面包含该用户会话自己的 `skills/` 和 `memory/`。`user_id` 是隔离标识，不是认证或授权机制；未指定时使用 `default`。

```text
data/
  agent.sqlite3
  sessions/
    <user-id>/
      <session-id>/
        memory/
        skills/
```

如果 Agent 或工具链需要写入临时文件、中间结果、下载缓存、生成草稿等运行期产物，直接写到当前 `sessions/<user-id>/<session-id>/` 目录下。`memory/` 只放应该长期注入上下文的记忆文件。旧数据库记录会归属默认用户 `default`；新版本会为访问到的用户会话创建新的双层 session 目录。

## 运行

启动连续对话：

```bash
agents
```

指定 Agent 启动：

```bash
agents db_explorer
agents db_explorer chat --thread-id work
agents research_assistant --agent-config ./agents.yaml
```

开启一个随机 ID 的新会话：

```bash
agents --new
agents chat --new
```

指定 sessions 目录：

```bash
agents --sessions-dir ./data/sessions
agents chat --sessions-dir ./data/sessions --thread-id work
```

指定用户隔离标识：

```bash
agents --user-id oye
agents chat --user-id oye --thread-id work
```

默认不会显示中间请求日志，只显示交互内容。需要调试时可以启动时打开：

```bash
agents --debug
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
agents chat --thread-id work
```

交互模式中输入 `/exit` 或 `/quit` 退出。同一个 `user_id` + `thread_id` 的历史会自动从 SQLite 读取并继续。使用 `--new` 会生成随机 `thread_id`，因此会进入一个全新的 `data/sessions/<user-id>/<session-id>/` 目录。

交互模式支持查看和切换用户：

```text
/user
/user alice
```

切换用户只影响后续消息的用户作用域，不会改变当前 `thread_id` 或启动时选择的 Agent。

也可以发送单条消息后退出：

```bash
agents chat --thread-id demo --message "帮我整理今天的任务"
agents chat --new --message "帮我整理今天的任务"
```

首次运行会自动创建 SQLite 表。

CLI 会区分显示用户输入、Agent 流式输出、思考/步骤、工具调用和工具结果。SQLite 的 `messages` 表会通过 `message_type` 和 `metadata_json` 保存这些不同类型的事件；普通历史续聊只会把用户消息和最终助手消息重新送入模型上下文。

## 配置化 Agent

启动时默认读取当前目录下的 `agents.yaml`。如果这个文件不存在，系统使用内置 `default` 和 `db_explorer`。也可以通过 `--agent-config` 指定其他配置文件；显式指定的文件不存在时会启动失败。

YAML 顶层固定为四段（运行时配置 + Agent 资源定义）：

```yaml
settings: {}
llms:
  - name: main
    model: ${AGENT_MODEL}
    api_key: ${AGENT_OPENAI_API_KEY}
    base_url: ${AGENT_OPENAI_BASE_URL}

tools:
  - name: calculator
    provider: agents.tools.calculator.CalculatorToolProvider
    config: {}

agents:
  - name: helper
    llm: main
    tools: [calculator]
    system_prompt_file: ./prompts/helper.md
    skills: false
    memory: false

  - name: research_assistant
    llm: main
    tools: [calculator]
    system_prompt: |
      你是研究助理 Agent。先澄清问题，再给出结构化结论。
    include_builtin_tools: true
    skills:
      enabled: true
      paths:
        - ./skills/common
    memory:
      enabled: true
      paths:
        - ./memory/project.md
    event_content_limits:
      tool_events: 500
    subagents: [helper]
    create_kwargs:
      debug: false
```

配置规则：

- `llms` 定义 LLM 资源，`model` 保持 DeepAgents 的 `provider:model` 格式；当前 OpenAI-compatible 路径仍强制使用 Chat Completions。
- `model`、`api_key`、`base_url` 支持 `${VAR}` 环境变量引用（不支持 fallback 默认值）。
- `tools` 定义 Tool Provider，`provider` 是完整类路径，`config` 会作为关键字参数传给 provider 构造函数；`config` 内字符串也支持环境变量引用。
- `agents` 定义命名 Agent，`llm`、`tools`、`subagents` 都通过名称引用前面已配置的资源。
- `system_prompt` 可直接写在 YAML 中；`system_prompt_file` 可引用外部 UTF-8 文件。二者不能同时配置。相对路径按配置文件所在目录解析，绝对路径按原路径解析。
- `skills` 和 `memory` 可写布尔值，也可写 `{ enabled, paths }`。启用但不写 `paths` 时使用当前 session 默认目录；写了 `paths` 时会在启动 Agent 前复制到当前 session 的 `skills/` 或 `memory/` 目录，同名文件或目录会覆盖并记录日志。DeepAgents 创建参数固定引用 session 内的 `/skills` 和 `/memory/*.md`。
- `event_content_limits` 可限制该 Agent 输出的事件内容长度。`tool_events` 同时限制 `tool_call` 和 `tool_result`；也可分别写 `tool_call`、`tool_result`。超出限制时会保留前缀，并追加 `... (remaining N chars)`。
- YAML 中的同名 Agent 会覆盖内置同名 Agent。
- API Key 允许明文配置，但日志、错误信息、CLI 输出、API 响应和 SSE 事件流都不会输出 secret 明文。

### 启动配置化 Agent

#### CLI 启动

```bash
agents research_assistant --agent-config ./agents.yaml
agents research_assistant chat --thread-id research-demo --agent-config ./agents.yaml
agents research_assistant chat --thread-id research-demo --message "帮我调研一下向量数据库选型" --agent-config ./agents.yaml
```

CLI 启动后不支持切换 Agent。要使用另一个 Agent，需要重新启动命令。

#### API 启动

```bash
agents-api --agent default --agent-config ./agents.yaml --host 127.0.0.1 --port 8000
python -m agents.interfaces.api --agent default --agent-config ./agents.yaml --host 127.0.0.1 --port 8000
```

API 启动时加载完整 registry。旧路由仍使用启动参数中的默认 Agent，新路由通过 URL 选择 Agent：

```text
POST /chat
POST /chat/stream
POST /agents/{agent_name}/chat
POST /agents/{agent_name}/chat/stream
GET /users/{user_id}/chats
GET /users/{user_id}/chats/{thread_id}/messages
```

请求体不支持切换 Agent；用户通过 Body 中的 `sendUserAccount` 区分（兼容旧字段 `user_id`），未传时使用默认用户 `default`。

### 自定义 Tool Provider

例如新增文件 `src/agents/tools/research.py`：

```python
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from langchain_core.tools import tool


@tool
def web_search(query: str) -> str:
    """Search relevant information for the user query."""
    # 这里只是示例，实际可接入你自己的搜索服务
    return f"search result for: {query}"


class ResearchToolProvider:
    def __init__(self, timeout: int = 15) -> None:
        self.timeout = timeout

    def tools_for_thread(self, thread_id: str) -> Iterable[Any]:
        return (web_search,)
```

然后在 `agents.yaml` 中引用：

```yaml
tools:
  - name: research
    provider: agents.tools.research.ResearchToolProvider
    config:
      timeout: ${AGENT_TOOL_SEARCH_TIMEOUT}
```

> 提示：如果你启动时出现 `Unknown agent 'xxx'`，说明该名称没有出现在内置 registry 或当前加载的 `agents.yaml` 中。

### 在 PyCharm 中启动 CLI

1. `Run | Edit Configurations...` 新建 **Python** 配置。
2. `Run kind` 选择 **Module name**，填入 `agents.cli`。
3. `Python interpreter` 选择项目 `.venv`。
4. `Working directory` 设为项目根目录。
5. 准备 `agents.yaml`，并在顶层 `settings` 节按需写入 `${...}` 环境变量引用。
6. `Parameters` 可选：
   - 连续对话：留空（等价 `agents`）
   - 新会话：`--new`
   - 单条消息：`chat --thread-id demo --message "你好"`
   - 指定配置：`research_assistant --agent-config ./agents.yaml`

## 自定义 Tool 示例

项目内置了一个四则运算示例工具：

- 位置：[src/agents/tools/calculator.py](src/agents/tools/calculator.py)
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
from agents.application.bootstrap import build_service

service = build_service(tool_providers=(MyToolProvider(),))
```

## API

安装 API 依赖后可启动 FastAPI：

```bash
uvicorn agents.interfaces.api:app --reload
```

也可以直接通过 Python 启动：

```bash
python -m agents.interfaces.api --host 127.0.0.1 --port 8000
python -m agents.interfaces.api --agent default --agent-config ./agents.yaml --host 127.0.0.1 --port 8000
```

安装为可执行命令后也支持：

```bash
agents-api --host 127.0.0.1 --port 8000
agents-api --agent default --agent-config ./agents.yaml --host 127.0.0.1 --port 8000
```

### 宿主进程拉起 `agents.api` 的 UTF-8 编码建议

若 `agents-api` 由外层宿主进程（如桌面端或服务编排器）通过子进程拉起，建议统一采用 UTF-8：

1. 文本模式读取 stdout/stderr 时，显式指定 `encoding="utf-8"` + `errors="replace"`。
2. 子进程环境变量补齐 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`。
3. Windows 若经过 `cmd` / `powershell` 中转，先切换 UTF-8 code page（如 `chcp 65001`），或改为字节模式读取再自行解码。
4. 日志采集器应提供“解码失败降级策略”（`replace` + 原始字节摘要），避免 reader 线程因单条脏数据崩溃。

Python 宿主示例：

```python
import hashlib
import os
import subprocess

env = os.environ.copy()
env.setdefault("PYTHONUTF8", "1")
env.setdefault("PYTHONIOENCODING", "utf-8")

proc = subprocess.Popen(
    ["python", "-m", "agents.api", "--host", "127.0.0.1", "--port", "8000"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    encoding="utf-8",
    errors="replace",
    env=env,
)

# 若使用 bytes 模式读取，可在 decode 失败时输出摘要用于定位：
def decode_with_fallback(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    digest = hashlib.sha256(raw).hexdigest()[:12]
    return f"{text} [raw_sha256={digest}]"
```

### 在 PyCharm 中启动 API

1. `Run | Edit Configurations...` 新建 **Python** 配置。
2. `Run kind` 选择 **Module name**，填入 `agents.interfaces.api`（或 `agents.api`）。
3. `Python interpreter` 选择项目 `.venv`（需先 `pip install -e ".[api]"`）。
4. `Working directory` 设为项目根目录。
5. `Parameters` 可选：`--host 127.0.0.1 --port 8000 --no-reload --agent default --agent-config ./agents.yaml`。
6. 通过 `--agent-config` 指向 `agents.yaml`，并在 `settings` 节调整 `api_host`、`api_port`、`cors_origins` 等字段。

接口：

- `GET /healthz`：健康检查
- `POST /chat`：同步对话，返回标准响应包（`code/message/error/isFinish/data`）
- `POST /chat/stream`：SSE 流式对话，逐条返回标准响应包，结束时发送 `done`
- `POST /agents/{agent_name}/chat`：按 URL 中的 Agent 名称同步对话
- `POST /agents/{agent_name}/chat/stream`：按 URL 中的 Agent 名称 SSE 流式对话
- `GET /users/{user_id}/chats`：分页查询指定用户的聊天会话列表
- `GET /users/{user_id}/chats/{thread_id}/messages`：分页查询指定用户、指定聊天的历史消息

请求体不包含 `agent_name`，Agent 只能通过启动参数或 URL 选择。SSE 请求体与同步接口一致：

```json
{
  "sendUserAccount": "default",
  "topicId": "default",
  "type": "text",
  "content": "帮我整理今天的任务",
  "imGroupId": null,
  "clientLang": "zh",
  "clientType": "asst-pc",
  "messageId": "msg-001",
  "chatModel": "thin",
  "tenant_id": "acme",
  "scene": "daily_planning"
}
```

字段说明：

- `sendUserAccount`：用户账号（兼容旧字段 `user_id`）。
- `topicId`：会话 ID（兼容旧字段 `thread_id`）。
- `type`：消息类型，`text`（默认）或 `IMAGE-V1`。
- `content`：消息内容。`text` 时为文本；`IMAGE-V1` 时传 `{fileId,extractCode}` 的 JSON 列表字符串。
- `imGroupId`：群 ID，可为 `null`。
- `clientLang`：客户端语言，`zh`（默认）或 `en`。
- `clientType`：客户端类型，`asst-pc` / `asst-wecode`，未知可为 `null`。
- `messageId`：消息 ID，可选。
- `chatModel`：聊天输出模式（兼容旧字段 `chat_model`），默认 `thin`。
  - `thin`：仅返回**主 Agent**的 `assistant_message`。
  - `normal`：返回**主 Agent**的 `assistant_message`、`tool_call`、`thinking`。
  - `full`：在 `normal` 基础上，额外返回**子 Agent**同类型消息，并在响应 `data.subAgent` 标注子 Agent 名称。

同步与流式响应均使用统一结构：

```json
{
  "code": 0,
  "message": "",
  "error": "",
  "isFinish": true,
  "data": {
    "type": "text",
    "content": "...",
    "planning": "",
    "searching": [],
    "searchResult": [],
    "references": [],
    "askMore": [],
    "subAgent": null
  }
}
```

其中 `data.type` 为事件类型：`assistant_message`、`tool_call`、`thinking`（不匹配时降级为 `text`）；`data.subAgent` 仅在 `chatModel=full` 且事件来自子 Agent 时返回。历史查询支持 `limit` 和 `offset`，例如：

```text
GET /users/default/chats?limit=20&offset=0
GET /users/default/chats/work/messages?limit=50&offset=0
```

不存在的聊天历史返回空消息列表。`limit` 会被限制在系统允许的最大分页大小内。

SSE 流不会返回 `internal_state` 事件；这类事件属于 DeepAgents/LangGraph 内部状态同步，不适合作为前端可见过程展示。

建议重点回归子 Agent/工具链路（`chatModel=full`）：

```bash
curl -N -X POST "http://127.0.0.1:8000/agents/db_explorer/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{
    "sendUserAccount": "default",
    "topicId": "db-regression",
    "content": "帮我检查数据库表结构并给出建议",
    "chatModel": "full"
  }'
```

### API 过滤层扩展（请求 / 响应 / SSE）

API 入口新增可组合过滤层 `ApiFilterPipeline`，可在不改动 `AgentService` 的情况下做定制：

- 解析和改写入参（包括与 `topicId/content/sendUserAccount` 平级的自定义字段，兼容旧字段）
- 按条件过滤或改写 SSE 事件对象
- 为同步响应和 SSE 事件追加顶层自定义字段

核心位置：

- `agents.interfaces.api.filters.ApiFilter`
- `agents.interfaces.api.filters.ApiFilterPipeline`
- `agents.interfaces.api.app.create_app(..., api_filters=...)`

示例：

```python
from agents.interfaces.api.app import create_app
from agents.interfaces.api.filters import BaseApiFilter, ApiFilterContext


class TenantFilter(BaseApiFilter):
    def transform_chat_request(self, request, context: ApiFilterContext):
        tenant_id = request.extension_fields.get("tenant_id")
        if not tenant_id:
            return request
        return request.model_copy(
            update={"thread_id": f"{tenant_id}:{request.thread_id}"}
        )

    def chat_response_fields(self, result, context: ApiFilterContext):
        return {"tenant_thread_id": result.thread_id}

    def event_fields(self, event, context: ApiFilterContext):
        return {"agent": context.agent_name, "event_type": event.event_type}


app = create_app(agent_name="default", api_filters=(TenantFilter(),))
```

浏览器跨域访问需要配置 CORS，例如：

```yaml
cors_origins: http://localhost:3000,http://127.0.0.1:5173
```

不配置 `cors_origins`（空字符串）时，API 不启用 CORS。
