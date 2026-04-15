## ADDED Requirements

### Requirement: 用户作用域会话身份
系统 SHALL 将 `user_id` 作为聊天会话的一等作用域，并 MUST 在聊天、流式聊天、历史加载、事件持久化、memory 同步和 Agent runtime 缓存中同时使用 `user_id` 与 `thread_id` 识别会话。

#### Scenario: 不同用户使用同名会话
- **WHEN** 用户 `alice` 和用户 `bob` 都使用 `thread_id=default` 发起聊天
- **THEN** 系统 SHALL 为两个用户维护互不混淆的历史消息、runtime 缓存、memory 同步上下文和 session 文件目录

#### Scenario: 未指定用户时使用默认用户
- **WHEN** CLI 或 API 请求未显式提供 `user_id`
- **THEN** 系统 SHALL 使用默认用户 `default` 处理该请求，并保持现有单用户调用方式可用

### Requirement: 用户隔离的 session 目录
系统 SHALL 将每个 session 的文件工作区、`skills/` 和 `memory/` 放在 `data/sessions/<user_id>/<session_id>` 目录下，并 MUST 对 `user_id` 和 `session_id` 执行安全路径片段清理。

#### Scenario: 创建用户 session 目录
- **WHEN** 用户 `alice` 使用 `thread_id=work` 发起聊天
- **THEN** 系统 SHALL 创建并使用 `data/sessions/alice/work` 作为 session 根目录

#### Scenario: 创建 session 子目录
- **WHEN** 系统初始化用户 `alice` 的 `work` session
- **THEN** 系统 SHALL 在该 session 根目录下创建 `skills/` 和 `memory/` 子目录

#### Scenario: 拒绝路径穿越
- **WHEN** 请求中的 `user_id` 或 `thread_id` 包含路径分隔符、上级目录片段或其他不安全字符
- **THEN** 系统 MUST 清理为安全路径片段，并 MUST 校验最终路径仍位于 configured sessions 根目录下

### Requirement: 用户作用域持久化存储
系统 SHALL 在 threads、messages 和 memory entries 的持久化读写中记录并使用 `user_id`，并 MUST 让不同用户的同名 `thread_id` 可以独立存在。

#### Scenario: 写入用户作用域消息
- **WHEN** 用户 `alice` 在 `thread_id=work` 中发送消息
- **THEN** 系统 SHALL 将 thread 和 message 记录写入 `user_id=alice` 且 `thread_id=work` 的作用域

#### Scenario: 加载用户作用域历史
- **WHEN** 用户 `bob` 读取 `thread_id=work` 的历史
- **THEN** 系统 SHALL 只返回 `user_id=bob` 且 `thread_id=work` 的用户/助手消息

#### Scenario: 迁移旧数据
- **WHEN** 初始化数据库时发现旧 threads 或 messages 记录没有 `user_id`
- **THEN** 系统 SHALL 将这些记录回填到默认用户 `default`

#### Scenario: 支持 SQLite 和 PostgreSQL
- **WHEN** 存储后端为 SQLite 或 PostgreSQL
- **THEN** 系统 SHALL 提供等价的 `user_id` 字段、用户作用域查询条件和支持历史查询的索引

### Requirement: CLI 用户选择与切换
CLI SHALL 支持启动时通过参数指定当前用户，并 SHALL 支持在交互式聊天中通过命令查看和切换当前用户。

#### Scenario: 启动时指定用户
- **WHEN** 用户运行 CLI 并传入 `--user-id alice`
- **THEN** CLI SHALL 使用 `alice` 作为当前用户处理后续聊天请求

#### Scenario: 查看当前用户
- **WHEN** 用户在交互式 CLI 中输入 `/user`
- **THEN** CLI SHALL 显示当前 `user_id`、当前 `thread_id` 和对应 session 目录

#### Scenario: 切换当前用户
- **WHEN** 用户在交互式 CLI 中输入 `/user bob`
- **THEN** CLI SHALL 将当前用户切换为 `bob`，并 SHALL 让后续消息进入 `bob` 用户下的当前 `thread_id`

#### Scenario: 切换用户不切换 Agent
- **WHEN** 用户在交互式 CLI 中切换 `user_id`
- **THEN** CLI MUST NOT 改变启动时选择的 Agent profile

### Requirement: API 聊天请求用户字段
API SHALL 允许同步聊天和流式聊天请求在 Body 中传入 `user_id`，并 MUST 在未传入时使用默认用户。

#### Scenario: 同步聊天指定用户
- **WHEN** 客户端向 `POST /chat` 或 `POST /agents/{agent_name}/chat` 发送包含 `user_id=alice`、`thread_id=work` 和 `message` 的请求
- **THEN** API SHALL 使用 `alice` 用户作用域处理该聊天，并在响应中返回对应的 `user_id` 和 `thread_id`

#### Scenario: 流式聊天指定用户
- **WHEN** 客户端向 `POST /chat/stream` 或 `POST /agents/{agent_name}/chat/stream` 发送包含 `user_id=alice` 的请求
- **THEN** API SHALL 使用 `alice` 用户作用域产生 SSE 事件流，并继续过滤内部状态事件

#### Scenario: 聊天请求未指定用户
- **WHEN** 客户端发送不包含 `user_id` 的聊天请求
- **THEN** API SHALL 使用默认用户 `default` 处理该请求

### Requirement: API 用户聊天列表
API SHALL 提供查询指定用户聊天会话列表的接口，并 MUST 支持分页。

#### Scenario: 查询用户聊天列表
- **WHEN** 客户端请求 `GET /users/alice/chats`
- **THEN** API SHALL 返回 `alice` 用户的聊天会话列表，且 MUST NOT 返回其他用户的会话

#### Scenario: 分页查询聊天列表
- **WHEN** 客户端请求 `GET /users/alice/chats?limit=20&offset=40`
- **THEN** API SHALL 返回从偏移量 40 开始、最多 20 条的 `alice` 用户聊天会话

#### Scenario: 限制分页大小
- **WHEN** 客户端请求的 `limit` 超过系统允许的最大分页大小
- **THEN** API SHALL 将分页大小限制在系统最大值或返回明确的参数错误

### Requirement: API 聊天历史分页
API SHALL 提供查询指定用户具体聊天历史的接口，并 MUST 支持分页返回消息。

#### Scenario: 查询具体聊天历史
- **WHEN** 客户端请求 `GET /users/alice/chats/work/messages`
- **THEN** API SHALL 返回 `user_id=alice` 且 `thread_id=work` 的历史消息，且 MUST NOT 返回其他用户或其他聊天的消息

#### Scenario: 分页查询聊天历史
- **WHEN** 客户端请求 `GET /users/alice/chats/work/messages?limit=50&offset=100`
- **THEN** API SHALL 返回从偏移量 100 开始、最多 50 条的聊天历史消息，并保持消息的创建顺序

#### Scenario: 查询不存在的聊天历史
- **WHEN** 客户端查询指定用户下不存在的 `thread_id`
- **THEN** API SHALL 返回空历史或明确的 not found 响应，且行为 MUST 在 API 文档中说明
