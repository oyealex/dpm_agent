from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from agents.config import Settings
from agents.core.service import AgentService
from agents.interfaces.api.schemas import ChatRequest, ChatResponse
from agents.interfaces.api.sse import stream_agent_events
from agents.application.bootstrap import build_service
from agents.core.definitions import AgentConfigError, AgentRegistry, load_agent_registry


def create_app(
    service: AgentService | None = None,
    agent_name: str = "default",
    agent_config_path: Path | None = None,
    agent_registry: AgentRegistry | None = None,
) -> FastAPI:
    app = FastAPI(title="Agents API")
    settings = service.settings if service is not None else Settings()
    try:
        registry = agent_registry or load_agent_registry(agent_config_path)
    except AgentConfigError as exc:
        raise ValueError(str(exc)) from exc
    if agent_name not in registry.list_names():
        options = ", ".join(registry.list_names())
        raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_name}'. Available: {options}")
    _configure_cors(app, settings)
    app.state.agent_name = agent_name
    app.state.agent_config_path = agent_config_path
    app.state.agent_registry = registry
    app.state.agent_services = {}
    if service is not None:
        app.state.agent_services[agent_name] = service

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/chat", response_model=ChatResponse)
    def chat(request: ChatRequest) -> ChatResponse:
        return chat_for_agent(agent_name, request)

    @app.post("/chat/stream")
    def chat_stream(request: ChatRequest) -> StreamingResponse:
        return chat_stream_for_agent(agent_name, request)

    @app.post("/agents/{selected_agent_name}/chat", response_model=ChatResponse)
    def chat_for_agent(selected_agent_name: str, request: ChatRequest) -> ChatResponse:
        agent_service = _get_agent_service(app, selected_agent_name)
        result = agent_service.chat(
            thread_id=request.thread_id,
            message=request.message,
        )
        return ChatResponse(thread_id=result.thread_id, reply=result.reply)

    @app.post("/agents/{selected_agent_name}/chat/stream")
    def chat_stream_for_agent(selected_agent_name: str, request: ChatRequest) -> StreamingResponse:
        agent_service = _get_agent_service(app, selected_agent_name)
        events = agent_service.chat_stream(
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


def _get_agent_service(app: FastAPI, agent_name: str) -> AgentService:
    registry: AgentRegistry = app.state.agent_registry
    if agent_name not in registry.list_names():
        options = ", ".join(registry.list_names())
        raise ValueError(f"Unknown agent '{agent_name}'. Available: {options}")
    services: dict[str, AgentService] = app.state.agent_services
    if agent_name not in services:
        services[agent_name] = build_service(
            agent_config_path=app.state.agent_config_path,
            agent_registry=registry,
            agent_name=agent_name,
        )
    return services[agent_name]


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


app = create_app(agent_name="default")


if __name__ == "__main__":
    main()
