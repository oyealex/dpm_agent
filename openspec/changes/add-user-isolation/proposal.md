## Why

当前 runtime 只按 `thread_id` 隔离会话；当多个用户共用同一个 CLI/API 服务时，对话历史、memory、skills 和文件工作区会产生归属歧义。引入显式用户隔离可以让项目更适合作为可复用的个人 Agent runtime，并为多用户 API 客户端打下基础。

## What Changes

- 为对话身份和持久化聊天记录增加一等 `user_id` 维度。
- 将 session 目录布局从 `data/sessions/<session_id>` 调整为 `data/sessions/<user_id>/<session_id>`。
- 改造数据库 schema 和 repository，使 threads、messages 和 memory entries 都按用户作用域读写。
- 支持 CLI 启动时指定当前用户，并支持在交互式 CLI 中通过命令切换用户。
- 支持 API 聊天请求在 Body 中传入 `user_id`。
- 新增 API 接口：查询指定用户的聊天会话列表，以及分页查询指定聊天的历史记录。
- 当未显式指定 `user_id` 时，通过默认用户值保持现有单用户使用体验。

## Capabilities

### New Capabilities

- `user-isolation`：用户作用域的 session、存储、CLI/API 用户选择，以及分页聊天历史查询。

### Modified Capabilities

- 无。

## Impact

- 影响代码：`src/agents/config.py`、`src/agents/domain/`、`src/agents/core/`、`src/agents/storage/`、`src/agents/application/bootstrap.py`、`src/agents/interfaces/cli/` 和 `src/agents/interfaces/api/`。
- 影响存储：SQLite 和 PostgreSQL schema、迁移/回填行为、repository 查询契约，以及面向用户作用域历史查询的索引。
- 影响运行时数据：session 目录、每个 session 的 `memory/` 和 `skills/` 发现路径，以及文件工具工作区。
- 影响接口：CLI 参数与交互命令、API 请求 schema、API 响应 schema，以及新的历史列表/详情接口。
- 需要同步更新 `README.md` 和 `docs/architecture.md`。
