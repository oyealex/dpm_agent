## ADDED Requirements

### Requirement: 加载固定结构的 Agent YAML 配置
系统 SHALL 支持从 YAML 文件加载 Agent 配置，且顶层结构 MUST 固定为 `llms`、`tools`、`agents` 三段。

#### Scenario: 加载有效三段式配置
- **WHEN** 当前目录存在有效的 `agents.yaml`，且包含 `llms`、`tools`、`agents` 三段
- **THEN** 系统 SHALL 成功加载其中的 LLM、Tool 和 Agent 定义

#### Scenario: 拒绝缺失 Agent 段的配置
- **WHEN** 配置文件缺少 `agents` 顶层段
- **THEN** 系统 SHALL 在启动阶段返回明确的配置错误

### Requirement: 配置文件来源
系统 SHALL 默认读取当前工作目录下的 `agents.yaml`，并 MUST 支持 CLI/API 启动参数指定其他配置文件路径。

#### Scenario: 默认配置文件不存在
- **WHEN** 用户未显式指定配置文件，且当前工作目录不存在 `agents.yaml`
- **THEN** 系统 SHALL 使用内置默认 Agent registry 启动

#### Scenario: 显式配置文件不存在
- **WHEN** 用户通过启动参数显式指定一个不存在的配置文件
- **THEN** 系统 SHALL 启动失败并说明配置文件不存在

### Requirement: 同名定义覆盖
系统 SHALL 在加载 YAML 配置后按名称合并定义，且 YAML 中的同名定义 MUST 覆盖内置默认定义。

#### Scenario: YAML 覆盖 default Agent
- **WHEN** YAML 中定义名为 `default` 的 Agent
- **THEN** 系统 SHALL 使用 YAML 中的 `default` Agent 定义覆盖内置 `default` 定义

### Requirement: LLM 资源定义
系统 SHALL 支持在 `llms` 段定义命名 LLM 资源，字段包括唯一名称、模型名称、API Key、BaseUrl 和额外调用参数。

#### Scenario: Agent 引用已定义 LLM
- **WHEN** Agent 定义通过名称引用 `llms` 中存在的 LLM 资源
- **THEN** 系统 SHALL 使用该 LLM 资源构建 Agent 的 Chat Completions 模型

#### Scenario: Agent 引用不存在的 LLM
- **WHEN** Agent 定义引用 `llms` 中不存在的 LLM 名称
- **THEN** 系统 SHALL 在配置校验阶段返回明确的引用错误

### Requirement: LLM 环境变量注入
系统 SHALL 支持 LLM 资源的 `model`、`api_key`、`base_url` 使用 `${VAR}` 或 `${VAR:-default}` 语法从环境变量注入。

#### Scenario: 解析已设置的环境变量
- **WHEN** LLM 配置中 `api_key` 为 `${AGENT_OPENAI_API_KEY}`，且环境变量已设置
- **THEN** 系统 SHALL 使用该环境变量值作为 API Key

#### Scenario: 使用环境变量默认值
- **WHEN** LLM 配置中 `model` 为 `${AGENT_MODEL:-openai:gpt-4.1}`，且环境变量未设置
- **THEN** 系统 SHALL 使用 `openai:gpt-4.1` 作为模型名称

#### Scenario: 缺失无默认值的环境变量
- **WHEN** LLM 配置引用未设置且无默认值的环境变量
- **THEN** 系统 SHALL 在配置校验阶段返回只包含变量名、不包含 secret 值的错误

### Requirement: Secret 脱敏
系统 MUST 允许 API Key 明文配置，但 MUST NOT 在日志、错误信息、CLI 输出、API 响应或 SSE 事件流中输出 API Key 或 provider 凭证明文。

#### Scenario: 明文 API Key 配置失败
- **WHEN** YAML 中包含明文 API Key 且配置校验失败
- **THEN** 系统 SHALL 返回脱敏后的错误信息，不包含该 API Key 明文

### Requirement: Tool 资源定义
系统 SHALL 支持在 `tools` 段定义命名 Tool 资源，字段包括唯一名称、Provider 类名和自定义配置项。

#### Scenario: Agent 引用已定义 Tool
- **WHEN** Agent 定义通过名称引用 `tools` 中存在的 Tool 资源
- **THEN** 系统 SHALL 实例化对应 Provider 并把其工具加入该 Agent runtime

#### Scenario: Agent 引用不存在的 Tool
- **WHEN** Agent 定义引用 `tools` 中不存在的 Tool 名称
- **THEN** 系统 SHALL 在配置校验阶段返回明确的引用错误

### Requirement: Tool 配置环境变量注入
系统 SHALL 支持 Tool `config` 中的字符串值使用 `${VAR}` 或 `${VAR:-default}` 语法从环境变量注入。

#### Scenario: 数据库 DSN 从环境变量注入
- **WHEN** Tool 配置中 `dsn` 为 `${AGENT_TOOL_DB_DSN}`，且环境变量已设置
- **THEN** 系统 SHALL 使用环境变量值初始化对应 Tool Provider

### Requirement: Agent 定义
系统 SHALL 支持在 `agents` 段定义命名 Agent，字段包括唯一名称、引用的 LLM、引用的 Tool 列表、系统提示词、SKILLS 设置、MEMORY 设置、SubAgent 列表、默认工具开关和 DeepAgents 额外参数。

#### Scenario: 加载完整 Agent 定义
- **WHEN** YAML 中存在包含 LLM、Tools、系统提示词、SKILLS、MEMORY 和 DeepAgents 参数的 Agent 定义
- **THEN** 系统 SHALL 构建与该定义一致的 Agent runtime

### Requirement: 系统提示词来源
系统 SHALL 支持 Agent 系统提示词在 YAML 中内联配置或通过外部文件引用配置，且二者 MUST NOT 同时出现。

#### Scenario: 使用内联系统提示词
- **WHEN** Agent 定义包含 `system_prompt`
- **THEN** 系统 SHALL 使用该文本作为 Agent 的系统提示词

#### Scenario: 使用相对路径提示词文件
- **WHEN** Agent 定义包含相对路径 `system_prompt_file`
- **THEN** 系统 SHALL 按 YAML 文件所在目录解析该路径并读取 UTF-8 文本作为系统提示词

#### Scenario: 同时配置两种提示词来源
- **WHEN** Agent 定义同时包含 `system_prompt` 和 `system_prompt_file`
- **THEN** 系统 SHALL 在配置校验阶段返回明确错误

### Requirement: Skills 配置
系统 SHALL 支持 Agent 通过布尔值或对象配置 SKILLS；启用且未指定路径时 MUST 使用当前 session 默认 skills 目录，指定路径时 MUST 额外加载这些路径。

#### Scenario: 启用默认 Skills
- **WHEN** Agent 定义中 `skills` 为 `true`
- **THEN** 系统 SHALL 加载当前 session 的默认 `skills` 目录

#### Scenario: 启用额外 Skills 路径
- **WHEN** Agent 定义中 `skills.enabled` 为 `true` 且包含 `paths`
- **THEN** 系统 SHALL 加载当前 session 默认 `skills` 目录和配置中的额外路径

#### Scenario: 禁用 Skills
- **WHEN** Agent 定义中 `skills` 为 `false`
- **THEN** 系统 SHALL 不向 DeepAgents runtime 注入 skills

### Requirement: Memory 配置
系统 SHALL 支持 Agent 通过布尔值或对象配置 MEMORY；启用且未指定路径时 MUST 使用当前 session 默认 memory 目录，指定路径时 MUST 额外加载这些路径。

#### Scenario: 启用默认 Memory
- **WHEN** Agent 定义中 `memory` 为 `true`
- **THEN** 系统 SHALL 加载当前 session 默认 `memory` 目录下的 Markdown 记忆文件

#### Scenario: 启用额外 Memory 路径
- **WHEN** Agent 定义中 `memory.enabled` 为 `true` 且包含 `paths`
- **THEN** 系统 SHALL 加载当前 session 默认 memory 文件和配置中的额外 memory 路径

#### Scenario: 禁用 Memory
- **WHEN** Agent 定义中 `memory` 为 `false`
- **THEN** 系统 SHALL 不向 DeepAgents runtime 注入 memory 文件

### Requirement: 配置路径解析
系统 SHALL 对 YAML 中的外部文件和目录路径执行一致的路径解析：相对路径按 YAML 文件所在目录解析，绝对路径按原路径解析。

#### Scenario: 解析相对 memory 路径
- **WHEN** YAML 位于 `/app/config/agents.yaml`，且 memory 额外路径为 `./memory/project.md`
- **THEN** 系统 SHALL 将其解析为 `/app/config/memory/project.md`

### Requirement: SubAgent 名称引用
系统 SHALL 支持 Agent 通过名称引用已配置的其他 Agent 作为可用 SubAgent。

#### Scenario: 引用已配置 SubAgent
- **WHEN** Agent 定义中 `subagents` 包含已存在的 Agent 名称
- **THEN** 系统 SHALL 将该 SubAgent 转换为 DeepAgents runtime 可用的 subagent 参数

#### Scenario: 引用不存在的 SubAgent
- **WHEN** Agent 定义中 `subagents` 包含不存在的 Agent 名称
- **THEN** 系统 SHALL 在配置校验阶段返回明确的引用错误

#### Scenario: 检测 SubAgent 循环引用
- **WHEN** Agent A 引用 Agent B，且 Agent B 直接或间接引用 Agent A
- **THEN** 系统 SHALL 在配置校验阶段返回循环引用错误

### Requirement: 默认工具开关
系统 SHALL 支持 Agent 配置是否包含内置默认工具。

#### Scenario: 禁用默认工具
- **WHEN** Agent 定义中 `include_builtin_tools` 为 `false`
- **THEN** 系统 SHALL 不向该 Agent 注入内置默认工具

### Requirement: CLI 启动时选择 Agent
CLI SHALL 支持启动时通过参数选择 Agent 和配置文件，且 CLI 启动后 MUST NOT 支持切换 Agent。

#### Scenario: CLI 使用指定 Agent 启动
- **WHEN** 用户启动 CLI 时指定 Agent 名称和配置文件路径
- **THEN** CLI SHALL 使用该配置文件中的指定 Agent 创建会话 runtime

#### Scenario: CLI 请求未知 Agent
- **WHEN** 用户启动 CLI 时指定不存在的 Agent 名称
- **THEN** CLI SHALL 启动失败并列出可用 Agent 名称

### Requirement: API URL 级 Agent 路由
API SHALL 通过 `/agents/{agent_name}/chat` 和 `/agents/{agent_name}/chat/stream` 路由选择 Agent，且请求体 MUST NOT 支持切换 Agent。

#### Scenario: API 调用指定 Agent 的流式聊天
- **WHEN** 客户端向 `/agents/db_explorer/chat/stream` 发送聊天请求
- **THEN** API SHALL 使用 `db_explorer` Agent 处理该请求并返回 SSE 事件流

#### Scenario: API 请求未知 Agent
- **WHEN** 客户端请求 `/agents/unknown/chat`
- **THEN** API SHALL 返回明确的 unknown agent 错误

### Requirement: 默认行为兼容
系统 SHALL 在未显式指定配置文件且当前目录不存在 `agents.yaml` 时保持现有默认 Agent、`db_explorer`、session memory、session skills 和内置工具行为兼容。

#### Scenario: 无配置文件运行默认 CLI
- **WHEN** 当前目录不存在 `agents.yaml`，且用户运行默认 CLI 命令
- **THEN** 系统 SHALL 使用内置 `default` Agent 并保持现有会话行为

### Requirement: DeepAgents 额外参数透传
系统 SHALL 支持 Agent 定义通过结构化字段配置 DeepAgents 支持的额外参数，并 MUST 将其透传给 `create_deep_agent`。

#### Scenario: 配置 DeepAgents 额外参数
- **WHEN** Agent 定义包含 DeepAgents 额外参数
- **THEN** 系统 SHALL 在创建该 Agent runtime 时把这些参数传递给 `create_deep_agent`
