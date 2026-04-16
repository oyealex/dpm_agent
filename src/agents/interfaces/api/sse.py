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
    encode_event: Callable[[AgentEvent], AgentEventResponse] | None = None,
) -> Iterator[str]:
    serializer = encode_event or AgentEventResponse.from_event
    for agent_event in events:
        if agent_event.event_type == "internal_state":
            continue
        payload = serializer(agent_event).model_dump(by_alias=True)
        yield encode_sse_event(agent_event.event_type, payload)
    yield encode_sse_event(
        "done",
        {
            "code": 0,
            "message": "",
            "error": "",
            "isFinish": True,
            "data": {
                "type": "text",
                "content": "",
            },
        },
    )
