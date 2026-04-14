# 项目状态

## 当前能力

- 项目是一个基于 DeepAgents 的个人 Agent。
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
