## 1. 配置与领域模型

- [x] 1.1 在 `Settings` 中增加默认用户配置，并提供规范化后的默认 `user_id`
- [x] 1.2 抽取或扩展安全路径片段清理逻辑，使 `user_id` 和 `thread_id` 共用一致规则
- [x] 1.3 将 session 路径方法改为接收 `user_id` 和 `thread_id`，生成 `<sessions_dir>/<user_id>/<session_id>`
- [x] 1.4 更新 `ChatResult`、历史列表项和消息响应所需的领域模型，使结果可携带 `user_id`

## 2. 存储 Schema 与 Repository

- [x] 2.1 更新 SQLite schema，为 `threads` 和 `messages` 增加 `user_id` 字段、用户作用域索引和旧数据默认用户回填逻辑
- [x] 2.2 更新 PostgreSQL schema，提供与 SQLite 等价的 `user_id` 字段和索引
- [x] 2.3 改造 `ChatRepository.ensure_thread()`、消息写入和事件写入方法，所有写入都带 `user_id`
- [x] 2.4 改造 `ChatRepository.list_messages()`，只读取指定 `user_id` 和 `thread_id` 的可见历史消息
- [x] 2.5 新增 repository 方法，用于分页列出指定用户的聊天会话
- [x] 2.6 新增 repository 方法，用于分页读取指定用户、指定聊天的完整历史消息
- [x] 2.7 确认 `MemoryRepository.sync_directory()` 记录的 memory path 不跨用户复用，并保持 SQLite/PostgreSQL 兼容

## 3. Core Service 与 Runtime

- [x] 3.1 更新 `AgentService.chat()` 和 `chat_stream()` 签名，接收可选 `user_id` 并默认使用 settings 默认用户
- [x] 3.2 更新 session 目录创建、memory 同步、thread 确保、历史加载和事件持久化调用，全部传递 `user_id`
- [x] 3.3 将 Agent runtime 缓存 key 从单一 `thread_id` 改为 `(user_id, thread_id)` 或稳定内部组合 key
- [x] 3.4 更新 DeepAgents `configurable.thread_id`，避免不同用户同名 session 共享 LangGraph 状态
- [x] 3.5 保持现有 surrogate 清理覆盖 `user_id`、`thread_id`、消息内容、事件内容和事件 metadata

## 4. CLI 用户支持

- [x] 4.1 在 CLI parser 中增加 `--user-id` 参数，默认使用 settings 默认用户
- [x] 4.2 更新单条消息模式，将 `user_id` 传入 service 并在输出中保持现有干净格式
- [x] 4.3 更新交互式启动提示，显示当前 `user_id`、`thread_id`、session 目录、skills 目录和 memory 目录
- [x] 4.4 增加 `/user` 命令查看当前用户和路径信息
- [x] 4.5 增加 `/user <id>` 命令切换当前用户，并确保切换后不改变当前 `thread_id` 或 Agent profile
- [x] 4.6 更新 `/help` 输出，包含用户查看和切换命令

## 5. API 用户字段与历史接口

- [x] 5.1 更新 `ChatRequest`，增加可选 `user_id` 字段，并在缺省时使用默认用户
- [x] 5.2 更新 `ChatResponse`，返回实际使用的 `user_id` 和 `thread_id`
- [x] 5.3 更新 `/chat`、`/chat/stream`、`/agents/{agent_name}/chat` 和 `/agents/{agent_name}/chat/stream`，将 Body 中的 `user_id` 传入 service
- [x] 5.4 新增聊天会话列表响应 schema，包含 `user_id`、`thread_id`、`title`、`created_at`、`updated_at` 和分页信息
- [x] 5.5 实现 `GET /users/{user_id}/chats`，支持 `limit`、`offset`，并限制最大分页大小
- [x] 5.6 新增聊天历史响应 schema，包含消息 role、type、content、metadata、created_at 和分页信息
- [x] 5.7 实现 `GET /users/{user_id}/chats/{thread_id}/messages`，按创建顺序分页返回指定聊天历史
- [x] 5.8 明确不存在聊天的返回行为，并在 API 文档中保持一致

## 6. 文档与兼容性

- [x] 6.1 更新 `README.md`，说明 `--user-id`、`/user`、API `user_id`、用户聊天列表和分页历史接口
- [x] 6.2 更新 `docs/architecture.md`，说明用户作用域、目录结构、数据库作用域和默认用户兼容策略
- [x] 6.3 说明该 change 只提供用户隔离标识，不提供认证或授权
- [x] 6.4 说明旧数据默认归属 `default` 用户，旧 session 目录迁移或兼容策略与实现保持一致

## 7. 验证

- [x] 7.1 运行 `PYTHONDONTWRITEBYTECODE=1 python -m compileall -q src`
- [x] 7.2 运行 `PYTHONPATH=src python -m agents.cli --help`，确认 CLI 参数可见
- [x] 7.3 运行 `PYTHONPATH=src python -m agents.interfaces.api --help`，确认 API 入口仍可用
- [x] 7.4 使用轻量 repository 验证不同 `user_id` 下同名 `thread_id` 的消息不会互相读取
- [x] 7.5 使用轻量路径验证确认 session 目录为 `<user_id>/<session_id>`，且不安全 ID 被清理后仍在 sessions 根目录内
- [x] 7.6 运行 `openspec validate add-user-isolation --strict`
- [x] 7.7 运行 `git diff --check`
