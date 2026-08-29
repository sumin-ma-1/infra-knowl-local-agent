from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from infra_agent.agent.loop import run_agent
from infra_agent.agent.ollama import OllamaClient
from infra_agent.config import get_settings
from infra_agent.inventory.store import InventoryStore
from infra_agent.tools.inventory_tools import build_registry

WEB_DIR = Path(__file__).resolve().parent / "web"

settings = get_settings()
store = InventoryStore(settings.resolved_inventory_dir())
tools = build_registry(store)
llm = OllamaClient(
    host=settings.ollama_host,
    model=settings.ollama_model,
    timeout=settings.agent_timeout_seconds,
)
sessions: dict[str, list[dict[str, Any]]] = {}

app = FastAPI(title="Infra Knowledge Agent", version="0.1.0")
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    conversation_id: str
    answer: str
    steps: int
    tool_calls: list[dict[str, Any]]


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "model": settings.ollama_model,
        "inventory_docs": len(store.docs),
    }


@app.post("/v1/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    conversation_id = req.conversation_id or str(uuid4())
    history = sessions.get(conversation_id, [])
    result = run_agent(
        question=req.message,
        llm=llm,
        tools=tools,
        max_steps=settings.agent_max_steps,
        history=history,
    )
    history = [
        *history,
        {"role": "user", "content": req.message},
        {"role": "assistant", "content": result.answer},
    ]
    sessions[conversation_id] = history[-12:]
    return ChatResponse(
        conversation_id=conversation_id,
        answer=result.answer,
        steps=result.steps,
        tool_calls=[
            {
                "name": t.name,
                "arguments": t.arguments,
                "result": _preview(t.result),
            }
            for t in result.tool_calls
        ],
    )


@app.post("/v1/inventory/reload")
def reload_inventory() -> dict[str, int]:
    store.reload()
    return {"docs": len(store.docs)}


@app.get("/v1/inventory")
def list_inventory() -> dict[str, Any]:
    store.reload_if_stale()
    return {
        "servers": [d.id for d in store.all("server")],
        "networks": [d.id for d in store.all("network")],
        "services": [d.id for d in store.all("service")],
    }


def _preview(text: str, limit: int = 1200) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "…"
