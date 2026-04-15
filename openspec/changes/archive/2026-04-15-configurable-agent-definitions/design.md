## Context

当前项目已经有 `AgentDefinition`、`AgentRegistry` 和 `AgentRuntime` 的基础结构，但 Agent 定义仍写在 `src/agents/core/agent.py` 的 Python 代码里。LLM 资源来自全局 `Settings`，工具通过 `AgentToolProvider` 注入，skills 和 memory 固定按 session 目录收集，CLI/API 只能按内置 registry 选择 Agent。

本次变更需要把 Agent 装配提升为 YAML 配置能力：同一个配置文件可以声明 LLM 资源、Tool 列表和 Agent 列表，并通过名称引用把它们组合起来。设计必须继续遵守当前项目边界：配置仍由 `Settings` 统筹，DeepAgents 细节留在 `core`，业务编排留在 `AgentService`，CLI/API 只负责选择和传参。

## Goals / Non-Goals

**Goals:**

- 支持从 YAML 文件加载命名 LLM、Tool 和 Agent 定义。
- 支持 LLM 的模型名称、API Key、BaseUrl 从环境变量注入。
- 支持 Tool 自定义配置中的字符串值从环境变量注入。
- 支持 Agent 系统提示词内联配置或引用外部文件；相对路径按 YAML 文件所在目录解析。
- 支持 Agent 通过名称引用 LLM、Tool 和 SubAgent。
- 支持 Agent 控制是否启用 session skills、session memory 和默认工具，并可额外指定 skills/memory 路径。
- 支持把 DeepAgents 兼容的额外参数透传给 `create_deep_agent`。
- 保持未配置 YAML 时的默认 Agent 行为兼容。
- 防止 API Key、数据库连接信息等 secret 出现在日志、错误事件或 SSE 内容中。

**Non-Goals:**

- 不实现远程配置中心、热重载或运行时动态修改配置。
- 不改变 DeepAgents 的底层调用方式，仍使用 Chat Completions，不切到 Responses API。
- 不改变现有 session 隔离规则；Agent 配置不能让文件工具绕过 `Settings.effective_session_dir(thread_id)`。
- 不把任意 Python 表达式放进 YAML 执行；Tool provider 只通过明确的类路径导入和结构化参数初始化。
- 不在本次变更中提供完整插件市场或图形化 Agent 管理界面。

## Decisions

### 1. 新增配置模型和 YAML loader

新增 `src/agents/core/definitions.py` 或相近模块，承载声明式配置模型和 loader，避免继续扩大 `core/agent.py`。YAML 顶层结构固定为三段：`llms`、`tools`、`agents`。建议模型分为：

- `AgentConfigFile`：顶层 YAML 文档，包含 `llms`、`tools`、`agents`。
- `LlmResourceDefinition`：`name`、`model`、`api_key`、`base_url`、`kwargs`。
- `ToolResourceDefinition`：`name`、`provider`、`config`。
- `ConfiguredAgentDefinition`：`name`、`llm`、`tools`、`system_prompt`、`system_prompt_file`、`skills`、`memory`、`include_builtin_tools`、`subagents`、`create_kwargs`。
- `AgentResourceToggle`：用于 `skills` 和 `memory`，包含 `enabled` 和 `paths`。

YAML 解析使用 `yaml.safe_load`，因此需要新增 `PyYAML` 依赖。Pydantic 负责结构校验、唯一名称校验和引用关系校验。替代方案是用 JSON 或 TOML，但 YAML 更适合写长提示词和列表型资源，且符合本次需求。

### 2. 环境变量注入采用显式引用语法

LLM 的 `model`、`api_key`、`base_url` 以及 Tool `config` 中的字符串值支持两种值：

- 普通字符串：直接使用。
- 环境变量引用：例如 `${AGENT_OPENAI_API_KEY}` 或 `${AGENT_MODEL:-openai:gpt-4.1}`。

解析规则放在 loader 层，解析后再进入 runtime。未设置且无默认值时抛出配置错误；错误信息只能包含变量名，不能包含 secret 值。API Key 允许在 YAML 中明文配置，但日志、错误信息和事件流必须脱敏。替代方案是复用 shell 展开，但 shell 规则过宽且错误不可控；显式解析更容易测试和脱敏。

### 3. LLM 资源构建与 AgentDefinition 解耦

现有 `build_chat_model(settings)` 只使用全局 Settings。变更后引入可选 `LlmResourceDefinition`，由 `AgentRuntime` 按 Agent 引用的 LLM 构建 `ChatOpenAI`：

- `model` 保持 DeepAgents 要求的 provider 格式，例如 `openai:gpt-4.1`。
- 传给 `ChatOpenAI` 前继续移除 `openai:` 前缀。
- `base_url` 默认可回退到 `Settings.effective_openai_base_url`。
- `api_key` 默认可回退到 `Settings.openai_api_key`。
- 始终设置 `use_responses_api=False`。

这样既支持 YAML 多 LLM，也保留现有 Settings 默认路径。

### 4. Tool provider 通过类路径和结构化配置实例化

YAML 中的 Tool 定义使用唯一名称引用 provider 类，例如：

```yaml
tools:
  - name: reporting-db
    provider: agents.tools.database.DatabaseToolProvider
    config:
      dsn: ${AGENT_TOOL_REPORTING_DB_DSN}
```

loader 使用 `importlib` 导入类，并要求实例满足 `AgentToolProvider` 协议或提供 `tools_for_thread(thread_id)` 方法。`config` 先完成环境变量解析，再作为关键字参数传入 provider 构造函数。默认工具仍通过 `include_builtin_tools` 控制。第一版暂不增加 provider allowlist，配置文件按可信输入处理。替代方案是 YAML 直接声明单个 LangChain tool，但这会把 Python 对象序列化问题暴露给配置层，不适合作为第一版。

### 5. 系统提示词支持内联和文件引用

Agent 支持以下两种方式配置系统提示词：

- `system_prompt`：YAML 中直接写入文本。
- `system_prompt_file`：引用外部文件。

二者同时配置时应报错，避免优先级歧义。`system_prompt_file` 为相对路径时按 YAML 文件所在目录解析，为绝对路径时直接读取。文件读取使用 UTF-8，并通过现有 surrogate 清理逻辑处理文本。未配置时回退到 `DEFAULT_SYSTEM_PROMPT`。

### 6. Skills 和 Memory 支持开关加额外路径

Agent 的 `skills` 和 `memory` 字段支持布尔值或对象：

```yaml
agents:
  - name: default
    skills: true
    memory:
      enabled: true
      paths:
        - ./memory/project.md
```

当字段为 `true` 或 `{ enabled: true }` 且未指定 `paths` 时，继续使用当前 session 默认目录：`data/sessions/<thread-id>/skills` 和 `data/sessions/<thread-id>/memory`。当指定 `paths` 时，额外加载这些路径；相对路径按 YAML 文件所在目录解析，绝对路径按原路径解析。`false` 或 `{ enabled: false }` 表示不启用对应能力。

默认 session skills/memory 仍受 session 隔离规则约束；额外只读路径用于注入上下文，不扩大文件工具的可写工作区。

### 7. SubAgent 只采用名称引用

Agent 的 `subagents` 字段保存已配置 Agent 的名称列表，例如 `subagents: ["researcher", "coder"]`。loader 校验引用存在，并禁止直接或间接循环引用。runtime 构建主 Agent 时，将被引用的 Agent 转换为 DeepAgents 支持的 subagent 参数。

该转换应在 `core` 内完成，不让 CLI/API 关心 subagent 细节。第一版只支持指定可使用的 subagent 名称，不支持为每个 subagent 单独配置触发条件、描述或远程 Agent。

### 8. 配置来源和选择路径

默认从当前工作目录读取 `agents.yaml`。CLI 和 API 启动命令支持通过入参指定配置文件路径；不新增环境变量配置入口。指定路径或默认 `agents.yaml` 存在时加载 YAML，并与默认 registry 合并：

- 同名定义使用覆盖策略，YAML 中的 Agent 覆盖内置同名 Agent。
- YAML 不存在且未显式指定配置文件时，继续使用现有 `DEFAULT_AGENT_REGISTRY`。
- CLI 现有位置参数 `agent_name` 继续可用。
- API 启动时加载完整 registry，但不支持请求体内切换 Agent；Agent 体现在 URL 中，例如 `/agents/{agent_name}/chat` 和 `/agents/{agent_name}/chat/stream`。

这样可以最小化 CLI 破坏面，同时让 API 通过 URL 明确表达 Agent 选择。替代方案是在请求体中传 `agent_name`，但这会让单个 service 实例的 runtime 切换和缓存策略更复杂，因此第一版不采用。

## Risks / Trade-offs

- [Risk] YAML 中出现 secret 明文，或错误信息泄露 secret → Mitigation：文档推荐环境变量引用；日志只输出是否配置，不输出值；配置错误对 secret 字段做脱敏。
- [Risk] 任意 provider 类导入带来执行风险 → Mitigation：只允许显式类路径；不执行 YAML 表达式；第一版配置文件按可信输入处理，后续可增加 allowlist。
- [Risk] SubAgent 循环引用导致递归构建失败 → Mitigation：loader 阶段做有向图环检测，错误信息列出 Agent 名称链路。
- [Risk] 多 LLM 配置与现有 Settings 产生优先级混乱 → Mitigation：明确规则为 Agent 引用的 LLM 优先，缺省字段回退 Settings。
- [Risk] 提示词文件路径读取越界 → Mitigation：提示词文件允许绝对路径是需求的一部分，但读取失败必须给出明确错误；session 文件工具仍不得因此扩大可写范围。
- [Risk] 新增 PyYAML 增加依赖面 → Mitigation：仅使用 `safe_load`，依赖较小，且 YAML 是该能力的核心输入格式。

## Migration Plan

1. 增加 YAML 配置模型、loader、环境变量解析和引用校验。
2. 调整 `AgentRuntime` 和 `build_agent`，支持按 Agent 引用的 LLM 构建模型，并接收配置化 tools、subagents、system prompt 和 DeepAgents kwargs。
3. 调整 `build_service`，从默认 `agents.yaml` 或 CLI/API 启动参数指定路径加载配置 registry；未找到默认文件时使用现有默认 registry。
4. 保持 CLI 启动时 Agent 选择入口兼容；API 增加 `/agents/{agent_name}/chat` 和 `/agents/{agent_name}/chat/stream` 路由。
5. 更新 README 和 `docs/architecture.md`，给出 YAML 示例、环境变量注入示例和安全注意事项。
6. 验证无 YAML 配置时现有默认 Agent、`db_explorer`、calculator tool、CLI/API help 仍可用。

回滚策略：如果显式指定的配置文件加载失败，启动阶段应失败并给出明确配置错误；移除指定参数且当前目录没有 `agents.yaml` 时应恢复现有默认 registry 行为。

## Open Questions

- DeepAgents 当前版本对 subagents 的精确入参结构是否需要包一层适配器，还是可以直接传配置字典。
