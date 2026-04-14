from __future__ import annotations

import json
from collections.abc import Iterable, Iterator

from dpm_agent.domain.models import AgentEvent
from dpm_agent.interfaces.api.schemas import AgentEventResponse
from dpm_agent.sanitize import sanitize_text


def encode_sse_event(event: str, data: object) -> str:
    payload = json.dumps(data, ensure_ascii=False)
    return f"event: {sanitize_text(event)}\ndata: {payload}\n\n"


def stream_agent_events(events: Iterable[AgentEvent]) -> Iterator[str]:
    for agent_event in events:
        payload = AgentEventResponse.from_event(agent_event).model_dump()
        yield encode_sse_event(agent_event.event_type, payload)
    yield encode_sse_event("done", {"status": "ok"})
