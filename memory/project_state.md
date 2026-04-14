# 项目状态

## 当前能力

- 项目是一个基于 DeepAgents 的个人 Agent。
- 源码已按功能拆分为 `core/`、`domain/`、`storage/`、`interfaces/` 和 `application/` 子模块；顶层旧模块保留为兼容导出。
- `core/agent.py` 负责 DeepAgents runtime 创建，`core/service.py` 负责应用编排，`core/events.py` 负责流事件解析和去重。
- `core/tools.py` 提供 `AgentToolProvider` 扩展点，后续自定义 tool 可通过 provider 注入 DeepAgents runtime。
- `tools/calculator.py` 提供四则运算自定义工具示例，默认通过 `default_tool_providers()` 注入 Agent runtime。
- CLI 代码已拆到 `interfaces/cli/`，参数解析、交互流程和终端渲染相互解耦。
- REST API 代码已拆到 `interfaces/api/`，支持同步 `POST /chat` 和 SSE 流式 `POST /chat/stream`。
- API 服务可通过 `uvicorn dpm_agent.interfaces.api:app`、`python -m dpm_agent.interfaces.api` 或安装后的 `dpm-agent-api` 命令启动。
- SQLite connection 已配置 `check_same_thread=False`，并由 `ChatRepository` 与 `MemoryRepository` 共享同一把 `RLock` 串行化访问，避免 FastAPI/Starlette 线程池执行同步 SSE generator 时触发跨线程 SQLite 错误。
- API SSE 响应与 CLI 一样不返回 `internal_state` 事件，只返回面向调用方可展示的 Agent 过程事件。
- 支持 `skills/` 目录，技能以 `SKILL.md` 描述。
- 支持 `memory/` 目录，长期记忆以 Markdown 文件维护。
- 支持 SQLite 持久化 `threads`、`messages` 和 `memory_entries`。
- `messages` 现在支持 `message_type` 和 `metadata_json`，可记录用户消息、助手消息、思考/步骤、工具调用和工具结果等事件。
- DeepAgents/LangGraph 的 middleware state update（例如 `SkillsMiddleware.before_agent updated`、`Overwrite(value=[...])`）属于内部状态同步，不是 LLM 思考内容；CLI 默认不展示，也不写入历史库。
- CLI 事件层会忽略 `AIMessageChunk` 中尚未完整组装的工具调用分片，并对工具调用、工具结果、内部状态事件去重，避免空工具调用或重复工具结果刷屏。
- CLI 支持连续对话，默认使用 `thread_id=default`。
- 同一个 `thread_id` 会从 SQLite 读取历史消息并继续对话。
- CLI 支持流式显示 Agent 输出，并用颜色区分用户、助手、工具和步骤事件。
- SQLite 对话历史库是多个对话共享的应用级数据库，默认仍为 `./data/agent.sqlite3`。
- sessions 默认位于 `./data/sessions`，可通过 `--sessions-dir` 指定。
- 每个对话的文件工具工作目录、skills 和 memory 都按 `thread_id` 隔离到 `data/sessions/<session-id>`。
- 不再单独创建 `runtime/` 目录；运行期临时文件、中间结果、缓存和生成草稿直接放入当前 session 根目录，长期上下文应放入该 session 的 `memory/`。
- 用户输入、历史消息、事件内容、事件元数据和 `thread_id` 会在进入 Agent/SQLite 前清理非法 surrogate 字符；清理时优先按 surrogateescape 还原有效 UTF-8，避免中文引号等字符被错误替换，同时避免 OpenAI SDK 在 UTF-8 编码请求 JSON 时崩溃。

## 最近工作记录

- 本轮完成了一次结构性重构：将原先集中在顶层的 `agent_factory.py`、`service.py`、`repository.py`、`db.py`、`cli.py`、`api.py` 拆到功能子包，并保留顶层薄包装以兼容旧导入路径和 `dpm-agent` 入口。
- 新模块边界：
  - `application/bootstrap.py`：装配 settings、SQLite connection、repository、AgentRuntime 和 AgentService。
  - `core/agent.py`：DeepAgents runtime 创建、模型、memory、skills、filesystem backend 和工具注入。
  - `core/service.py`：聊天业务编排、历史加载、Agent 调用、事件持久化。
  - `core/events.py`：DeepAgents/LangGraph stream chunk 到 `AgentEvent` 的转换、过滤和去重。
  - `core/tools.py`：`AgentToolProvider` 和 `StaticToolProvider`，作为自定义工具扩展点。
  - `domain/models.py`：`Message`、`AgentEvent`、`ChatResult`。
  - `storage/db.py`、`storage/repository.py`：SQLite schema、迁移、会话/消息/记忆读写。
  - `interfaces/cli/`：CLI parser、renderer 和交互 app。
  - `interfaces/api/`：FastAPI app、schema 和 SSE 编码。
  - `tools/`：内置/示例工具。
- 已新增 `tools/calculator.py` 作为自定义 Tool 示例：
  - `calculate(operation, left, right)` 是纯计算函数，方便测试。
  - `calculator_tool(operation, left, right)` 使用 `langchain_core.tools.tool` 暴露给 Agent。
  - 支持 `add`、`subtract`、`multiply`、`divide`。
  - 除零返回 `error: division by zero`，避免工具调用直接崩溃。
  - `CalculatorToolProvider` 默认通过 `tools.default_tool_providers()` 注入。
- `build_service()` 现在支持：
  - `tool_providers=(...)` 追加自定义工具 provider。
  - `include_builtin_tools=False` 关闭内置工具。
- REST API 已有 `POST /chat/stream`，返回 `text/event-stream`，每个 SSE event 对应一个 `AgentEvent`，结束时发送 `done`。
- 文档已同步更新：`README.md` 记录模块结构、API、calculator tool 和新增工具方式；`docs/architecture.md` 记录分层和 provider 模式。
- `pyproject.toml` 已显式加入 `langchain-core>=0.3.0`，因为自定义工具示例依赖 `langchain_core.tools.tool`。

## 验证状态

- 已用 AST 解析验证 `src/dpm_agent` 下 35 个 Python 文件语法正确。
- 已用 `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src` 验证 calculator 的加、减、乘、除和除零错误路径。
- 已验证 `default_tool_providers()` 返回内置 provider。
- 未完整启动 DeepAgents/CLI/API 对话；当前系统环境未安装运行依赖，且系统 Python 受 PEP 668 限制，禁止全局 editable install。
- 曾尝试 `python -m pip install -e . --no-deps` 刷新 egg-info，但被 externally-managed-environment 拒绝；随后手动同步了已跟踪的 `src/dpm_agent.egg-info/PKG-INFO`、`SOURCES.txt` 和 `requires.txt`。

## 后续建议

- 下一步可以增加一个正式的 Agent 定义层，例如 `agents/` 或 `profiles/`，让不同 Agent 声明 system prompt、默认 skills、memory 策略和 tool providers。
- 给 `calculator_tool` 增加单元测试，并为 `AgentToolProvider` 的组合逻辑增加测试。
- 在可安装依赖的虚拟环境里运行 `pip install -e ".[api]"`，再验证 `dpm-agent`、`uvicorn dpm_agent.interfaces.api:app --reload` 和 SSE 流。
- 后续如果继续跟踪 `src/dpm_agent.egg-info`，每次 README/依赖/包文件变化后都需要同步；更推荐后续将 egg-info 从版本控制中移除。

## 模型与接口

- 用户使用 OpenAI-compatible 服务，而不是固定使用 OpenAI 官方 endpoint。
- 支持通过 `DPM_AGENT_OPENAI_BASE_URL` 和 `DPM_AGENT_OPENAI_API_KEY` 配置服务。
- `DPM_AGENT_MODEL` 可使用 `openai:<model-name>` 格式。
- 当前强制使用 Chat Completions API。
- 当前不使用 Responses API，避免请求 `/v1/responses`。
- 预期请求路径是 `/v1/chat/completions`。

## CLI 行为

- `dpm-agent` 默认进入交互式连续对话。
- `dpm-agent chat --thread-id <id>` 可指定会话。
- `dpm-agent --new` 或 `dpm-agent chat --new` 会生成随机 `thread_id` 并开启新 session。
- `dpm-agent chat --message "..."`
  可发送单条消息后退出。
- 交互中 `/exit` 和 `/quit` 退出。
- 交互中 `/debug on` 开启日志，`/debug off` 关闭日志。
- 默认日志级别为 warning，普通聊天不显示中间 info 日志。

## 已修复问题

- 避免 DeepAgents 默认走 OpenAI Responses API。
- 修复 `AIMessage` 响应提取，CLI 只输出助手纯文本。
- 添加模型、BaseURL、API 模式、SQLite 路径等调试日志。
- 修复包含非法 surrogate 字符的输入或历史记录导致 `UnicodeEncodeError: surrogates not allowed` 的问题。
- 修复 surrogateescape 形式的有效 UTF-8 字符（如中文弯引号）被清洗成问号的问题。
- 修复把 LangGraph `Overwrite(...)` 状态更新误显示为 `Thinking>` 的问题。
- 修复 `stream_mode=["messages", "updates"]` 同时开启时工具调用/工具结果重复打印，以及工具调用 chunk 过早显示为空调用的问题。
