## 1. 配置模型与依赖

- [x] 1.1 在 `pyproject.toml` 增加 YAML 解析依赖，并确认安装后的包元数据同步策略
- [x] 1.2 新增 Agent YAML 配置模型，覆盖 `llms`、`tools`、`agents` 固定三段结构
- [x] 1.3 实现唯一名称校验、必填字段校验和未知顶层结构错误提示
- [x] 1.4 实现 `${VAR}` 与 `${VAR:-default}` 环境变量解析工具，并覆盖 LLM 字段与 Tool `config` 字符串值
- [x] 1.5 实现 secret 脱敏工具，确保 API Key、BaseUrl 凭证片段和 Tool secret 配置不会出现在错误或日志中

## 2. YAML Loader 与引用校验

- [x] 2.1 实现默认从当前目录 `agents.yaml` 读取配置，且显式指定路径不存在时启动失败
- [x] 2.2 实现 YAML safe-load、Pydantic 校验和配置文件所在目录记录
- [x] 2.3 实现 LLM、Tool、SubAgent 名称引用校验
- [x] 2.4 实现 SubAgent 直接或间接循环引用检测
- [x] 2.5 实现同名定义覆盖策略，将 YAML 定义覆盖内置 registry 中的同名 Agent

## 3. Runtime 装配

- [x] 3.1 将配置化定义转换为 runtime 可用的 `AgentDefinition` 或等价结构
- [x] 3.2 调整 LLM 构建逻辑，支持按 Agent 引用的 LLM 资源构建 `ChatOpenAI`，并保持 `use_responses_api=False`
- [x] 3.3 实现 Tool Provider 类路径导入与结构化 `config` 初始化
- [x] 3.4 实现系统提示词内联配置和 `system_prompt_file` 文件读取，禁止二者同时配置
- [x] 3.5 实现 `skills` 布尔值和对象配置，支持默认 session 目录与额外路径
- [x] 3.6 实现 `memory` 布尔值和对象配置，支持默认 session Markdown 文件与额外路径
- [x] 3.7 实现额外路径解析规则：相对路径按 YAML 所在目录解析，绝对路径按原路径解析
- [x] 3.8 实现 SubAgent 名称引用到 DeepAgents `subagents` 参数的适配
- [x] 3.9 实现 DeepAgents 额外参数透传到 `create_deep_agent`
- [x] 3.10 确认禁用默认工具时不会注入内置 calculator provider

## 4. CLI 与 API 接入

- [x] 4.1 为 CLI 增加配置文件启动参数，并保留现有 Agent 名称位置参数行为
- [x] 4.2 在 CLI 启动阶段加载 registry，未知 Agent 时列出可用 Agent 名称
- [x] 4.3 为 API server 增加配置文件启动参数，并在应用启动阶段加载完整 registry
- [x] 4.4 新增 `/agents/{agent_name}/chat` 路由，按 URL 中的 Agent 名称处理同步聊天
- [x] 4.5 新增 `/agents/{agent_name}/chat/stream` 路由，按 URL 中的 Agent 名称处理 SSE 流式聊天
- [x] 4.6 保留或兼容现有 `/chat` 与 `/chat/stream` 默认 Agent 路由，避免破坏已有调用方
- [x] 4.7 确保 CLI/API 启动后不支持通过请求体切换 Agent

## 5. 测试与验证

- [x] 5.1 增加配置 loader 轻量测试或脚本验证，覆盖有效三段式 YAML、缺失顶层段、引用不存在资源和同名覆盖
- [x] 5.2 增加环境变量解析验证，覆盖 `${VAR}`、`${VAR:-default}`、未设置且无默认值错误
- [x] 5.3 增加系统提示词文件路径解析验证，覆盖相对路径、绝对路径和双来源冲突
- [x] 5.4 增加 skills/memory 开关与额外路径解析验证
- [x] 5.5 增加 SubAgent 循环引用检测验证
- [x] 5.6 验证无 `agents.yaml` 时默认 CLI、`default` Agent、`db_explorer` 和内置工具行为兼容
- [x] 5.7 验证 API 新路由和旧默认路由的 help/import 基础路径可用
- [x] 5.8 运行 `PYTHONDONTWRITEBYTECODE=1 python -m compileall -q src`
- [x] 5.9 运行 `git diff --check`

## 6. 文档同步

- [x] 6.1 更新 README，说明 `agents.yaml` 默认位置、CLI/API 配置文件参数和 Agent 选择方式
- [x] 6.2 更新 README，提供包含 `llms`、`tools`、`agents` 的完整 YAML 示例
- [x] 6.3 更新 README，说明环境变量注入、明文 secret 风险和日志脱敏行为
- [x] 6.4 更新 `docs/architecture.md`，记录配置化 Agent registry、loader、runtime 装配和 API URL 级 Agent 路由
- [x] 6.5 如继续跟踪 `src/agents.egg-info`，同步包元数据中依赖和 README 相关生成内容
