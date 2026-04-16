from __future__ import annotations

from typing import Any, Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from agents.domain.models import AgentEvent, Message, ThreadSummary


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    thread_id: str = Field(
        alias="topicId",
        validation_alias=AliasChoices("topicId", "thread_id"),
        description="会话主题 ID（原 thread_id）。",
    )
    message: str = Field(
        alias="content",
        validation_alias=AliasChoices("content", "message"),
        description="用户发送内容。文本消息为纯文本；图片消息为 JSON 列表字符串。",
    )
    user_id: str | None = Field(
        default=None,
        alias="sendUserAccount",
        validation_alias=AliasChoices("sendUserAccount", "user_id"),
        description="发送用户账号（原 user_id），未传时使用默认用户。",
    )
    type: Literal["text", "IMAGE-V1"] = Field(
        default="text",
        description="消息类型：text 或 IMAGE-V1。",
    )
    im_group_id: str | None = Field(
        default=None,
        alias="imGroupId",
        validation_alias=AliasChoices("imGroupId", "im_group_id"),
        description="群 ID，可为空。",
    )
    client_lang: Literal["zh", "en"] = Field(
        default="zh",
        alias="clientLang",
        validation_alias=AliasChoices("clientLang", "client_lang"),
        description="客户端语言：zh 或 en。",
    )
    client_type: Literal["asst-pc", "asst-wecode"] | None = Field(
        default=None,
        alias="clientType",
        validation_alias=AliasChoices("clientType", "client_type"),
        description="客户端类型：asst-pc、asst-wecode，未知可为空。",
    )
    message_id: str | None = Field(
        default=None,
        alias="messageId",
        validation_alias=AliasChoices("messageId", "message_id"),
        description="消息 ID，用于追踪单次对话。",
    )
    chat_model: Literal["thin", "normal", "full"] = Field(
        default="thin",
        alias="chatModel",
        validation_alias=AliasChoices("chatModel", "chat_model"),
        description="聊天输出模式：thin/normal/full，默认 thin。",
    )

    @property
    def extension_fields(self) -> dict[str, Any]:
        return dict(self.model_extra or {})


class ChatResponseData(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str = Field(description="响应数据类型。当前仅输出 think 或 text。")
    content: str = Field(default="", description="响应文本内容。")
    planning: str = Field(default="", description="规划内容，当前固定空字符串。")
    searching: list[str] = Field(default_factory=list, description="搜索内容，当前固定空列表。")
    search_result: list[dict[str, Any]] = Field(
        default_factory=list,
        alias="searchResult",
        description="搜索结果，当前固定空列表。",
    )
    references: list[dict[str, Any]] = Field(default_factory=list, description="引用结果，当前固定空列表。")
    ask_more: list[str] = Field(default_factory=list, alias="askMore", description="追问内容，当前固定空列表。")
    sub_agent: str | None = Field(
        default=None,
        alias="subAgent",
        description="子 Agent 名称，仅在 chat_model=full 且事件来自子 Agent 时返回。",
    )


class ChatResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: int = Field(default=0, description='状态码，成功为 0，错误统一为 -1。')
    message: str = Field(default="", description="提示信息，当前固定空字符串。")
    error: str = Field(default="", description="异常信息，成功时为空。")
    is_finish: bool = Field(alias="isFinish", description="是否流式结束。同步接口恒为 true。")
    data: ChatResponseData = Field(description="响应载荷。")


class ThreadSummaryResponse(BaseModel):
    user_id: str
    thread_id: str
    title: str | None = None
    created_at: str
    updated_at: str

    @classmethod
    def from_summary(cls, summary: ThreadSummary) -> ThreadSummaryResponse:
        return cls(
            user_id=summary.user_id,
            thread_id=summary.thread_id,
            title=summary.title,
            created_at=summary.created_at,
            updated_at=summary.updated_at,
        )


class ChatListResponse(BaseModel):
    user_id: str
    items: list[ThreadSummaryResponse]
    limit: int
    offset: int
    has_more: bool


class MessageResponse(BaseModel):
    role: str
    message_type: str
    content: str
    metadata: dict[str, Any] | None = None
    created_at: str | None = None

    @classmethod
    def from_message(cls, message: Message) -> MessageResponse:
        return cls(
            role=message.role,
            message_type=message.message_type,
            content=message.content,
            metadata=message.metadata,
            created_at=message.created_at,
        )


class ChatHistoryResponse(BaseModel):
    user_id: str
    thread_id: str
    items: list[MessageResponse]
    limit: int
    offset: int
    has_more: bool


class AgentEventResponse(BaseModel):
    model_config = ConfigDict(extra="allow")

    code: int = Field(default=0, description='状态码，成功为 0，错误统一为 -1。')
    message: str = Field(default="", description="提示信息，当前固定空字符串。")
    error: str = Field(default="", description="异常信息，成功时为空。")
    is_finish: bool = Field(default=False, alias="isFinish", description="流式响应是否结束。")
    data: ChatResponseData = Field(description="事件载荷。")

    @classmethod
    def from_event(
        cls,
        event: AgentEvent,
        sub_agent: str | None = None,
        extension_fields: dict[str, Any] | None = None,
    ) -> AgentEventResponse:
        if event.event_type in {"assistant_message", "tool_call", "thinking"}:
            mapped_type = event.event_type
        else:
            mapped_type = "text"
        payload: dict[str, Any] = {
            "code": 0,
            "message": "",
            "error": "",
            "isFinish": False,
            "data": {
                "type": mapped_type,
                "content": event.content,
            },
        }
        if sub_agent:
            payload["data"]["subAgent"] = sub_agent
        if extension_fields:
            payload.update(extension_fields)
        return cls.model_validate(payload)
