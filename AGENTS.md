# DPM Agent Project Instructions

## 基本角色

- 你是用户的个人 Agent，优先追求长期可用性、一致性和可维护性。
- 每次开始任务前先读取 `memory/` 目录中的长期记忆，并把它们视为高优先级用户上下文。
- 如果项目内存在 `skills/` 目录，读取与当前任务匹配的技能说明并严格遵循；当前仓库根目录没有固定 `skills/`，运行时技能默认在 `data/sessions/<thread-id>/skills/`。
- 当用户要求规划、执行、总结时，输出应清晰、可执行、不过度冗长。
- 当信息不足时，明确指出缺失信息，不要伪造事实。

## 项目概览

- 这是一个基于 `DeepAgents` 的个人 Agent Python 包，包名和命令入口为 `agents`。
- 当前目标是可运行、可扩展的 CLI/API Agent runtime，支持会话隔离、长期记忆、技能目录、工具 provider 和可切换持久化。
- Python 版本要求为 `>=3.11`。
- 主要依赖包括 `deepagents`、`langchain-openai`、`langchain-core`、`pydantic`、`pydantic-settings`；API 和 PostgreSQL 是可选 extra。
- 默认使用 OpenAI-compatible Chat Completions API，请求应走 `/v1/chat/completions`，不要改成 Responses API。

## 目录边界

- `src/agents/core/`：Agent runtime、事件归一化、工具 provider 接口。
- `src/agents/application/bootstrap.py`：装配 settings、数据库、repository、runtime 和 service。
- `src/agents/domain/`：领域数据模型，例如 `Message`、`AgentEvent`、`ChatResult`。
- `src/agents/storage/`：SQLite/PostgreSQL schema、连接工厂、repository。
- `src/agents/interfaces/cli/`：CLI 参数、交互流程、终端渲染。
- `src/agents/interfaces/api/`：FastAPI app、SSE、API server 启动。
- `src/agents/tools/`：内置或示例工具，目前包含 calculator。
- `src/agents/*.py` 顶层模块主要是兼容旧导入路径，新代码优先使用子包路径。
- `memory/`：仓库级长期记忆，修改行为前应先读取。
- `data/sessions/<thread-id>/`：运行时会话目录；每个会话拥有自己的 `memory/`、`skills/` 和文件工具工作区。
- `docs/architecture.md` 和 `README.md` 是架构与使用说明的主要事实来源，代码行为变化时要同步更新。

## 配置约定

- 配置统一由 `agents.config.Settings` 管理，读取环境变量和项目根目录 `.env`。
- 环境变量统一使用 `AGENT_` 前缀；不要新增旧式 `DPM_AGENT_*` 配置。
- 常用配置：
  - `AGENT_MODEL`，默认 `openai:gpt-4.1`。
  - `AGENT_OPENAI_API_KEY`。
  - `AGENT_OPENAI_BASE_URL`，默认 `https://api.openai.com/v1`。
  - `AGENT_STORAGE_BACKEND`，支持 `sqlite`、`postgres`、`postgresql`、`pg`。
  - `AGENT_DB_PATH`，默认 `./data/agent.sqlite3`。
  - `AGENT_POSTGRES_DSN`。
  - `AGENT_SESSIONS_DIR`，默认 `./data/sessions`。
  - `AGENT_API_HOST`、`AGENT_API_PORT`、`AGENT_API_RELOAD`。
  - `AGENT_CORS_ORIGINS` 为空时不启用 CORS。
  - `AGENT_CUSTOM_ENV_PREFIXES` 默认收集 `AGENT_CUSTOM_`、`AGENT_AGENT_`、`AGENT_TOOL_`。
- 日志默认保持干净；调试信息只能通过 `--debug`、`--no-debug` 或 CLI 内 `/debug on|off` 显式控制。
- 不要打印 API Key 明文。

## 运行命令

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

```bash
pip install -e ".[api]"
pip install -e ".[postgres]"
```

```bash
agents
agents chat --thread-id work
agents --new
agents chat --new --message "帮我整理今天的任务"
agents db_explorer chat --thread-id work
```

```bash
agents-api
python -m agents.interfaces.api
uvicorn agents.interfaces.api:app --reload
```

## 开发规则

- 优先保持现有分层：接入层不直接操作 DeepAgents，业务编排放在 `AgentService`，DeepAgents 细节放在 `core`。
- 新 Agent 配置优先通过 `AgentDefinition` 和 `DEFAULT_AGENT_REGISTRY` 扩展。
- 新工具优先实现 `AgentToolProvider.tools_for_thread(thread_id)`，再通过 `build_service(tool_providers=...)` 或 `agents.tools.default_tool_providers()` 注入。
- 会话文件必须限制在 `Settings.effective_session_dir(thread_id)` 下，不能绕过 session 隔离。
- 长期注入上下文放入 session `memory/*.md`；临时文件、缓存、中间结果和草稿放在 session 根目录。
- DeepAgents/LangGraph 内部状态同步事件，例如 middleware lifecycle 或 `Overwrite(...)`，不应展示给 CLI/API 用户，也不应作为可见历史持久化。
- 事件处理要继续过滤未完整的工具调用分片，并对工具调用、工具结果、内部状态事件去重。
- SQLite connection 使用 `check_same_thread=False`，repository 共享 `RLock`；不要移除这层串行化，否则 SSE 在线程池中可能触发跨线程错误。
- 对用户输入、历史消息、事件内容、事件元数据和 `thread_id` 进入 Agent/数据库前保持 surrogate 清理，避免 UTF-8 编码崩溃。
- 顶层兼容模块可以保留，但新增实现不要继续堆到顶层旧模块。

## 验证建议

- 仓库当前没有专门测试目录；做改动后至少运行语法和关键路径验证。
- Python 语法验证：

```bash
PYTHONDONTWRITEBYTECODE=1 python -m compileall -q src
```

- calculator 工具可用性可以用 `PYTHONPATH=src` 做轻量验证。
- CLI/API 入口变更后检查帮助输出：

```bash
PYTHONPATH=src python -m agents.interfaces.api --help
PYTHONPATH=src python -m agents.cli --help
```

- 提交前运行：

```bash
git diff --check
```

- 真实模型对话需要有效 OpenAI-compatible BaseURL/API Key；没有凭证时不要声称已经完成端到端模型验证。
- PostgreSQL 集成测试需要安装 `.[postgres]` 并提供真实 DSN；没有服务时只能验证配置解析和缺依赖提示。

## 文档同步

- 改 CLI、API、配置、存储、Agent registry、tool provider、memory/skills 行为时，同步更新 `README.md` 和必要的 `docs/architecture.md`。
- 如果继续跟踪 `src/agents.egg-info`，README、依赖或包文件变化后要注意它可能需要同步；更推荐后续从版本控制中移除生成产物。
