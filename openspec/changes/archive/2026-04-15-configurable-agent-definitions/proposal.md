## Why

当前 runtime 对默认 Agent、LLM、内置工具、会话 memory、skills 和 sub-agent 的装配路径仍偏硬编码，定义多个可复用的 Agent 人格或任务型 Agent 成本较高。引入声明式 Agent 定义层后，可以通过 YAML 文件集中描述运行时资源和 Agent 组合关系，并在保留现有 CLI/API runtime 和会话隔离模型的前提下，让框架更容易扩展和维护。

## What Changes

- 新增 YAML 配置驱动的 Agent 定义方式，覆盖 LLM 资源、Tool 列表、Agent 列表、skills、memory 和 sub-agents。
- 支持在 YAML 中定义 LLM 资源：唯一名称、模型名称（包含 provider，格式遵循 DeepAgents 要求）、API Key、BaseUrl 以及其他 OpenAI-compatible 调用参数。
- LLM 资源的 API Key、模型名称和 BaseUrl 支持从环境变量注入；API Key 也允许明文配置，但 runtime、CLI 和 API 不得输出 secret 明文。
- 支持在 YAML 中定义 Tool 列表：唯一名称、Provider 类名，以及 provider 所需的自定义配置项，例如数据库连接信息。
- Tool 自定义配置项支持环境变量注入，用于数据库连接信息等部署相关参数。
- 支持在 YAML 中定义 Agent 列表：唯一名称、引用的 LLM 资源、引用的 Tool 列表、系统提示词、是否启用 SKILLS、是否启用 MEMORY、引用的 SubAgent 列表，以及其他 DeepAgents 支持的自定义参数。
- Agent 系统提示词支持在 YAML 中直接给出，也支持引用外部文件；相对路径按配置文件所在目录解析，绝对路径按原路径解析。
- 支持命名 Agent definition，并允许 CLI/API 在启动时通过参数选择不同 Agent；启动后不支持切换 Agent。
- API 通过 URL 表达 Agent，例如 `/agents/{agent_name}/chat/stream`。
- 允许 Agent definition 配置 SKILLS 和 MEMORY 的开关及额外路径；打开但未指定路径时使用 session 默认路径。
- 允许 Agent definition 声明 TOOL provider 或内置 tool id，并控制是否包含默认工具。
- 允许 Agent definition 通过名称引用已配置的 SubAgent，使主 Agent 可以通过 DeepAgents runtime 委派专门任务。
- 默认读取当前目录 `agents.yaml`，并支持通过 CLI/API 启动参数指定其他配置文件；同名定义采用覆盖策略。
- 未显式选择 Agent definition 时，保留现有默认行为。
- YAML schema 支持 API Key 和 provider 凭证字段，但文档应推荐使用环境变量引用；runtime、CLI 和 API 不得在日志、错误信息或事件流中输出 secret 明文。

## Capabilities

### New Capabilities

- `agent-definitions`：通过固定三段式 YAML 声明 LLM 资源、Tool 列表和 Agent 列表，支持环境变量注入、系统提示词内联或文件引用、SKILL/MEMORY 开关和额外路径、SubAgent 名称引用与 DeepAgents 参数组合。

### Modified Capabilities

无。

## Impact

- 影响 `src/agents/core/agent.py` 的 runtime 装配、`src/agents/application/bootstrap.py` 的 service/bootstrap wiring，以及 CLI/API 的 Agent 选择路径。
- 可能新增 Agent definition 相关的 domain/config model、YAML schema/loader、provider 类解析机制，以及项目级和 session 级 definition 文件加载器。
- 需要同步更新 README 和 `docs/architecture.md`，说明配置格式、选择行为和扩展点。
- 应保持现有命令、默认 settings、session 目录、memory/skills 行为和 tool provider 注入方式兼容。
