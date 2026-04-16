from __future__ import annotations

import json
from collections.abc import Iterable, Iterator
from typing import Callable

from agents.domain.models import AgentEvent
from agents.interfaces.api.schemas import AgentEventResponse
from agents.sanitize import sanitize_text


def encode_sse_event(event: str, data: object) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {sanitize_text(event)}\ndata: {payload}\n\n"


def stream_agent_events(
    events: Iterable[AgentEvent],
    *,
    include_event_name: bool = False,
    encode_event: Callable[[AgentEvent], AgentEventResponse] | None = None,
) -> Iterator[str]:
    # 默认输出 data-only，便于前端直接按每条 JSON 处理；
    # 如需兼容依赖 event 名称分发的 SSE 客户端，可开启 include_event_name。
    serializer = encode_event or AgentEventResponse.from_event
    for agent_event in events:
        if agent_event.event_type == "internal_state":
            continue
        payload = serializer(agent_event).model_dump(by_alias=True)
        if include_event_name:
            yield encode_sse_event(agent_event.event_type, payload)
        else:
            yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
