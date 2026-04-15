# 应用设计

## 目标

构建一个“个人 Agent”应用，而不是单纯的单次调用脚本。核心要求：

1. 基于 `DeepAgents` 作为推理与工具编排内核。
2. 支持 `SKILL` 机制，让不同任务场景可以通过目录和 `SKILL.md` 组织。
3. 支持 `MEMORY` 机制，让稳定的长期上下文可以持久保存并注入。
4. 将对话历史持久化到可切换的存储后端，便于回放、审计、二次加工和后续检索。

## 建议分层

### 1. 接入层

- CLI：本地个人使用的最低成本入口。
- API：后续用于 Web、桌面端、IM Bot。

这一层只负责接收输入和返回结果，不直接操作 DeepAgents。

当前代码位置：

- `agents.interfaces.cli.parser`：命令行参数。
- `agents.interfaces.cli.renderer`：终端事件渲染。
- `agents.interfaces.cli.app`：CLI 交互流程。
- `agents.interfaces.api.app`：FastAPI app、REST 与 SSE endpoint。
- `agents.interfaces.api.sse`：SSE 事件编码。
- `agents.interfaces.api.server`：Python 方式启动 API 服务，支持 host、port、reload 和 debug 配置。

API 当前支持：

- `GET /healthz`：健康检查。
- `POST /chat`：同步对话，返回最终回复。
- `POST /chat/stream`：SSE 流式对话，逐条返回面向调用方可展示的 `AgentEvent`。

SSE 接口复用 `AgentService.chat_stream()`，因此与 CLI 使用同一套事件归一化逻辑。API 会过滤 `internal_state`，不会把 DeepAgents/LangGraph 的内部状态同步事件暴露给前端。跨域访问通过 FastAPI `CORSMiddleware` 实现，只有设置 `AGENT_CORS_ORIGINS` 后才启用 CORS。

### 2. 应用服务层

由 `AgentService` 负责一次完整会话：

1. 获取或创建会话
2. 读取历史消息
3. 组装本轮输入
4. 流式调用 `DeepAgents`
5. 将用户消息、助手输出、思考/步骤、工具调用和工具结果归一为事件
6. 写入结构化消息事件
7. 返回结构化结果

这一层是业务核心，也是未来接入：

- RAG
- 用户画像
- 权限控制
- 成本统计
- 多 Agent 编排

的最佳位置。

当前代码位置：`agents.core.service.AgentService`。

### 3. Agent 运行层

`agents.core.agent` 负责创建 DeepAgents 实例，并统一处理：

- 模型配置
- 系统提示词
- skills 目录
- memory 文件列表
- 受限 session backend，并按 `thread_id` 使用 `data/sessions/<session-id>` 隔离文件工具、skills 和 memory
- 线程 ID 透传

这里建议把 DeepAgents 当成“可替换引擎”，不要让 SQLite 或产品逻辑反向污染它。

当前代码位置：

- `agents.core.agent.AgentRuntime`：创建每个 thread 的 DeepAgents runtime。
- `agents.core.agent.build_agent`：封装 DeepAgents 初始化。
- `agents.core.events`：将 DeepAgents/LangGraph 流输出归一为应用事件。
- `agents.core.tools.AgentToolProvider`：自定义工具扩展点。后续可以把 DeepAgents 兼容工具注册到 provider，再由 `AgentRuntime` 注入。
- `agents.tools.calculator.CalculatorToolProvider`：内置四则运算示例工具，展示自定义工具的接入方式。

## Tool 扩展方式

工具层采用 provider 模式：

1. 用 `langchain_core.tools.tool` 或 DeepAgents 支持的工具格式定义工具。
2. 实现 `AgentToolProvider.tools_for_thread(thread_id)`，按会话返回可用工具。
3. 通过 `build_service(tool_providers=(MyToolProvider(),))` 注入，或加入 `agents.tools.default_tool_providers()` 作为默认内置工具。

当前示例：

- `agents.tools.calculator.calculator_tool`
- 支持 `add`、`subtract`、`multiply`、`divide`
- 除零时返回错误文本而不是让工具调用崩溃

### 4. 配置层

配置统一集中在 `agents.config.Settings`，来源包括当前环境变量和项目根目录 `.env` 文件。统一使用 `AGENT_` 前缀，不再提供额外 fallback 变量。

主要配置范围：

- 应用与日志：`AGENT_APP_NAME`、`AGENT_DEBUG`
- LLM：`AGENT_MODEL`、`AGENT_OPENAI_API_KEY`、`AGENT_OPENAI_BASE_URL`
- 存储：`AGENT_STORAGE_BACKEND`、`AGENT_DB_PATH`、`AGENT_POSTGRES_DSN`
- 会话文件：`AGENT_SESSIONS_DIR`
- API：`AGENT_API_HOST`、`AGENT_API_PORT`、`AGENT_API_RELOAD`
- CORS：`AGENT_CORS_ORIGINS`、`AGENT_CORS_ALLOW_CREDENTIALS`、`AGENT_CORS_ALLOW_METHODS`、`AGENT_CORS_ALLOW_HEADERS`
- 自定义扩展：`AGENT_CUSTOM_ENV_PREFIXES`（默认 `AGENT_CUSTOM_,AGENT_AGENT_,AGENT_TOOL_`），可收集匹配前缀的环境变量供自定义 Agent/Tool 使用

CLI/API 的命令行参数仍可覆盖对应环境变量，例如 `--sessions-dir`、`--host`、`--port`、`--reload`、`--debug`。

### 5. 持久化层

持久化层存三类核心数据：

- `threads`：会话线程
- `messages`：对话消息和事件，使用 `message_type` 区分 `user_message`、`assistant_message`、`thinking`、`tool_call`、`tool_result` 等类型；DeepAgents/LangGraph 的内部状态更新如 middleware 生命周期事件和 `Overwrite(...)` 不作为可见对话事件持久化，工具调用分片和重复工具结果会在事件层过滤
- `memory_entries`：应用侧登记的长期记忆文件

对话历史库是应用级共享数据库，默认使用 SQLite，位于 `./data/agent.sqlite3`；也可通过 `AGENT_STORAGE_BACKEND=postgres` 与 `AGENT_POSTGRES_DSN` 切换到 PostgreSQL。

SQLite connection 使用 `check_same_thread=False`，并由 `ChatRepository` 与 `MemoryRepository` 共享同一把 `RLock` 串行化访问，避免 FastAPI/Starlette 在线程池中迭代同步 SSE generator 时触发跨线程 SQLite 错误。

每个会话按照 `thread_id` 分到 `data/sessions/<session-id>`，并拥有独立的 `skills/` 和 `memory/`。CLI 的 `--new` 会生成随机 `thread_id` 来开启新 session。DeepAgents 文件 backend 的根目录就是当前 session 目录，运行期临时文件、中间结果、缓存和生成草稿直接写入该 session 根目录。

当前代码位置：

- `agents.storage.db`：SQLite/PostgreSQL schema、连接工厂、统一 `Database` 包装和轻量迁移。
- `agents.storage.repository`：`ChatRepository` 与 `MemoryRepository`。

顶层的 `agents.db`、`agents.repository`、`agents.service`、`agents.agent_factory`、`agents.api` 和 `agents.cli` 仅作为兼容导出保留，新代码应优先使用子包路径。

为什么不只依赖 DeepAgents / LangGraph 内部状态：

- 内部 checkpoint 更适合运行时恢复，不适合产品化查询。
- 你通常还需要按时间、角色、标签、线程做筛选和分析。
- 后续如果切换模型或 agent 框架，业务历史仍然保留。

## SKILL 设计

采用目录式设计：

```text
skills/
  writing/
    SKILL.md
  planner/
    SKILL.md
```

每个技能由 `SKILL.md` 描述：

- 适用场景
- 使用规则
- 输入输出约束
- 必要模板

这样便于：

- 版本管理
- 人工编辑
- 未来做技能启停和权限控制

## MEMORY 设计

建议把长期记忆拆成两层：

### 1. 文件型长期记忆

保存在每个会话的 `memory/` 目录，例如：

- `profile.md`
- `preferences.md`
- `projects/current_focus.md`

这类记忆稳定、可人工维护、便于直接注入 DeepAgents。

运行期临时文件、中间结果、缓存和生成草稿直接放在 session 根目录；需要长期保留并注入上下文的信息应沉淀到 `memory/`。

### 2. 结构化元数据

在 SQLite 中记录：

- 记忆文件路径
- 标签
- 更新时间
- 来源

这样后续可做：

- 自动摘要
- 冲突检测
- 记忆检索
- 记忆生命周期管理

## 对话历史持久化策略

推荐双轨：

1. DeepAgents 负责本次 agent 推理上下文。
2. 应用自己把每轮消息落 SQLite。

当前骨架采用第二种作为主方案，原因是更稳定、可控、易查询。

后续如果你要做“可中断恢复”或更深的 LangGraph 持久化，可以再接入官方 checkpointer。

## 后续增强建议

优先顺序建议如下：

1. 增加自定义 Agent 定义层，让不同 Agent 能声明 system prompt、skills、memory 策略和工具 provider。
2. 增加 OpenAI 之外的模型适配。
3. 增加会话摘要表，控制长线程成本。
4. 增加记忆提取器，把对话自动沉淀到 `memory/`。
5. 增加向量检索，而不是把全部历史都直接送给模型。
