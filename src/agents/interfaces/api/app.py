from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agents.config import Settings
from agents.core.service import AgentService
from agents.interfaces.api.schemas import ChatRequest, ChatResponse
from agents.interfaces.api.sse import stream_agent_events
from agents.application.bootstrap import build_service


def create_app(service: AgentService | None = None) -> FastAPI:
    app = FastAPI(title="DPM Agent API")
    settings = service.settings if service is not None else Settings()
    _configure_cors(app, settings)
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


def _configure_cors(app: FastAPI, settings: Settings) -> None:
    origins = settings.effective_cors_origins
    if not origins:
        return
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=settings.cors_allow_credentials,
        allow_methods=settings.effective_cors_allow_methods,
        allow_headers=settings.effective_cors_allow_headers,
    )


def main() -> None:
    from agents.interfaces.api.server import main as run_server

    run_server()


app = create_app()


if __name__ == "__main__":
    main()
