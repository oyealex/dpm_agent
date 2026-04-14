from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

from dpm_agent.bootstrap import build_service


class ChatRequest(BaseModel):
    thread_id: str
    message: str


app = FastAPI(title="DPM Agent API")
service = build_service()


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/chat")
def chat(request: ChatRequest) -> dict[str, str]:
    result = service.chat(thread_id=request.thread_id, message=request.message)
    return {"thread_id": result.thread_id, "reply": result.reply}
