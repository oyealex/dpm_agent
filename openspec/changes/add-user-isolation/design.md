## Context

当前项目已经按 `core`、`domain`、`storage`、`interfaces` 和 `application` 分层，聊天主路径由 CLI/API 调用 `AgentService`，再进入 `AgentRuntime` 和 repository。现有会话身份只有 `thread_id`，对应数据库 `threads.id`、`messages.thread_id`，以及 `Settings.effective_session_dir(thread_id)` 生成的 `data/sessions/<thread_id>` 目录。

这次改造会横跨 runtime 路径、持久化 schema、CLI 参数/命令、API schema/路由和文档。必须保持默认单用户体验兼容，同时为多用户场景提供明确的目录隔离和查询接口。

## Goals / Non-Goals

**Goals:**

- 将 `user_id` 作为一等作用域传入聊天、流式聊天、历史查询、memory 同步和 session 目录解析。
- 将 runtime 文件目录调整为 `data/sessions/<user_id>/<session_id>`，其中 `session_id` 对应现有 `thread_id` 语义。
- 改造 SQLite/PostgreSQL schema，使同名 session 可以在不同用户下独立存在。
- 支持 CLI 启动参数指定用户，并支持交互式命令切换当前用户。
- 支持 API 请求 Body 指定 `user_id`，并新增用户聊天列表和分页聊天历史接口。
- 未显式传入 `user_id` 时使用默认用户，避免破坏当前单用户 CLI/API 调用。

**Non-Goals:**

- 不实现认证、授权、密码、Token 校验或用户注册体系。
- 不改变 DeepAgents 调用协议；仍使用 OpenAI-compatible Chat Completions API。
- 不把 Agent profile 选择改为可在 CLI 会话内动态切换；该能力仍遵循现有 Agent 定义设计。
- 不做跨用户共享 memory、skills 或文件工作区。

## Decisions

### 1. 显式传递 `user_id`，不拼接进 `thread_id`

`AgentService.chat()`、`AgentService.chat_stream()`、repository 方法和 settings session 路径方法都接收 `user_id` 与 `thread_id/session_id` 两个独立参数。DeepAgents `configurable.thread_id` 使用组合后的稳定运行时 key，例如 `<safe_user_id>/<safe_session_id>` 或等价的内部 key，避免不同用户同名 session 在 LangGraph 状态中碰撞。

理由：如果把 `user_id` 直接拼进对外 `thread_id`，API 历史查询、数据库唯一约束和目录结构会混合展示层与存储层语义，后续迁移和分页查询更难维护。

备选方案是只在入口层拼接 `thread_id = f"{user_id}:{session_id}"`。该方案实现更快，但会污染现有 thread ID 语义，也不利于查询“某个用户的全部聊天”。

### 2. 默认用户使用固定值 `default`

配置层增加默认用户概念，默认值为 `default`。CLI/API 未传 `user_id` 时都使用该值。所有进入数据库和路径解析的 `user_id` 都必须经过与 session ID 类似的 surrogate 清理和安全路径片段清理。

理由：默认值可保留现有命令和请求体兼容性，也能让旧数据迁移有明确归属。

备选方案是要求所有入口必须传 `user_id`。该方案边界更严格，但会立即破坏当前 CLI/API 使用方式，不符合项目当前 MVP 的兼容要求。

### 3. 数据库使用复合会话键

`threads` 表增加 `user_id` 字段，并将唯一身份改为 `(user_id, id)`；`messages` 增加 `user_id` 字段，并通过 `(user_id, thread_id)` 关联会话。索引至少覆盖：

- `threads(user_id, updated_at, id)`：支持查询指定用户的会话列表。
- `messages(user_id, thread_id, id)`：支持分页读取指定聊天历史。

SQLite 迁移为现有 `threads`、`messages` 增加 `user_id TEXT NOT NULL DEFAULT 'default'`，并补充索引。PostgreSQL schema 同步定义相同字段和索引。由于 SQLite 难以原地修改主键，repository 查询必须始终带 `user_id`，并通过唯一索引保障新写入数据不跨用户冲突；必要时在后续任务中使用表重建迁移提升约束强度。

理由：复合身份能允许不同用户拥有相同 session ID，例如每个用户都有 `default` 会话。

备选方案是新增内部 `thread_pk` 作为 messages 外键。该方案关系模型更规整，但对当前轻量 repository 和迁移改动更大；本阶段优先保持可运行骨架简单。

### 4. 目录结构由 Settings 统一生成

`Settings.effective_session_dir()` 改为接收 `user_id` 和 `thread_id`，生成 `effective_sessions_dir / safe_user_id / safe_session_id`。`effective_session_skills_dir()`、`effective_session_memory_dir()` 和 `ensure_session_directories()` 同步接收用户参数，并继续校验最终路径必须位于 sessions 根目录下。

理由：路径安全和目录布局应集中在配置层，避免 CLI、API 或 service 各自拼路径造成绕过 session 隔离。

备选方案是在 service 层拼出相对路径后传给 Settings。该方案会让路径安全逻辑分散，不利于长期维护。

### 5. CLI 用户切换只影响后续消息

CLI 增加启动参数 `--user-id`。交互模式新增 `/user` 查看当前用户，`/user <id>` 切换当前用户。切换用户后保留当前 `thread_id`，但后续消息进入新用户下的同名 session；CLI 应重新展示当前用户、session 目录、skills 和 memory 路径。`--new` 仍只生成新的 session ID，不生成用户 ID。

理由：用户切换是运行时上下文切换，不应隐式修改 session ID；这样“用户 + session”两个维度保持可预测。

备选方案是切换用户时自动创建新 session ID。该方案减少误用，但会让用户难以回到同名 session，也偏离用户提出的 `<user_id>/<session_id>` 模型。

### 6. API 使用 Body 字段区分用户，历史查询使用路径参数和分页参数

`ChatRequest` 增加可选 `user_id` 字段。`ChatResponse` 和 SSE 事件外层仍保持现有事件结构，但同步返回/可追踪 `user_id` 与 `thread_id`。新增接口建议为：

- `GET /users/{user_id}/chats?limit=&offset=`：分页列出指定用户的聊天会话。
- `GET /users/{user_id}/chats/{thread_id}/messages?limit=&offset=`：分页读取指定聊天历史。
- Agent 路由保持现有 `/agents/{agent_name}/chat` 和 `/agents/{agent_name}/chat/stream`，用户仍从 Body 传入。

分页参数应设置上限，默认值保持较小；返回结果包含 `limit`、`offset` 和 `has_more` 或等价字段。

理由：聊天调用按 Body 传用户符合用户要求；历史查询是资源读取，用路径表达用户和会话资源更直接。

备选方案是所有接口都通过 Body 传 `user_id`。该方案风格统一，但 GET 查询不适合依赖 Body，客户端兼容性较差。

## Risks / Trade-offs

- [Risk] 旧 SQLite 数据只有 `thread_id`，没有用户归属 -> 迁移时统一回填到默认用户 `default`，并在文档中说明旧数据归属。
- [Risk] SQLite 原地修改复合主键成本高 -> 初期用新增列和唯一索引约束新数据；如发现旧表结构阻碍外键，可采用建新表、复制、重命名的迁移步骤。
- [Risk] 用户 ID 进入目录路径可能造成路径穿越 -> 所有 `user_id` 和 `thread_id` 都使用安全片段清理，并保留 sessions 根目录 containment 校验。
- [Risk] API 无认证时调用方可读取任意 `user_id` 历史 -> 文档明确这是“用户隔离标识”而非安全认证；后续认证能力应在单独 change 中设计。
- [Risk] Agent runtime 缓存当前按 `thread_id` 缓存，会发生跨用户复用 -> 缓存 key 改为 `(user_id, thread_id)` 或内部组合 key。

## Migration Plan

1. 增加默认用户配置和 user/session 安全片段 helper。
2. 扩展 SQLite/PostgreSQL schema：为 `threads` 和 `messages` 增加 `user_id`，为旧数据回填 `default`，并创建用户作用域索引。
3. 更新 repository 方法签名和查询条件，确保所有读写都带 `user_id`。
4. 更新 `AgentService`、runtime 缓存 key、memory 同步路径和 DeepAgents configurable thread key。
5. 更新 CLI 参数、交互命令和启动提示。
6. 更新 API request/response schema、聊天入口和历史查询接口。
7. 更新 README 与架构文档，并执行语法、帮助输出、repository 轻量路径验证。

回滚策略：如果迁移后需要回退代码，默认用户 `default` 下的数据仍保留在新增列中；旧代码无法识别新增多用户数据，因此回退前应只使用 `default` 用户或备份数据库。

## Open Questions

- API 历史分页响应是否需要返回总数 `total`，还是只返回 `has_more` 以避免额外计数查询？
- 是否需要提供一次性迁移工具，把现有 `data/sessions/<session_id>` 目录移动到 `data/sessions/default/<session_id>`，还是在首次访问默认用户时兼容读取旧目录？
