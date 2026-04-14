from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from dpm_agent.core.service import AgentService
from dpm_agent.interfaces.api.schemas import ChatRequest, ChatResponse
from dpm_agent.interfaces.api.sse import stream_agent_events
from dpm_agent.application.bootstrap import build_service


def create_app(service: AgentService | None = None) -> FastAPI:
    app = FastAPI(title="DPM Agent API")
    app.state.agent_service = service or build_service()

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        result = app.state.agent_service.chat(
            thread_id=request.thread_id,
            message=request.message,
        )
        return ChatResponse(thread_id=result.thread_id, reply=result.reply)

    @app.post("/chat/stream")
    def chat_stream(request: ChatRequest) -> StreamingResponse:
        events = app.state.agent_service.chat_stream(
            thread_id=request.thread_id,
            message=request.message,
        )
        return StreamingResponse(
            stream_agent_events(events),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return app


app = create_app()
