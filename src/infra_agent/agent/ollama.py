from __future__ import annotations

from typing import Any

import httpx


class OllamaError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, host: str, model: str, timeout: float = 120.0) -> None:
        self.host = host.rstrip("/")
        self.model = model
        self.timeout = timeout

    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {"temperature": 0.1},
        }
        if tools:
            payload["tools"] = tools
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(f"{self.host}/api/chat", json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama request failed: {exc}") from exc
        data = response.json()
        message = data.get("message")
        if not isinstance(message, dict):
            raise OllamaError(f"unexpected Ollama response: {data}")
        return message

    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]:
        if not texts:
            return []
        used = (model or self.model).strip()
        if not used:
            raise OllamaError("embedding model is empty")
        payload = {"model": used, "input": texts}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(f"{self.host}/api/embed", json=payload)
                if response.status_code == 404:
                    response = client.post(
                        f"{self.host}/api/embeddings",
                        json={"model": used, "prompt": texts[0]},
                    )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise OllamaError(f"Ollama embed failed: {exc}") from exc
        data = response.json()
        vectors = data.get("embeddings")
        if isinstance(vectors, list) and vectors and isinstance(vectors[0], list):
            if len(vectors) != len(texts):
                raise OllamaError("embedding count mismatch")
            return [[float(x) for x in row] for row in vectors]
        single = data.get("embedding")
        if isinstance(single, list) and len(texts) == 1:
            return [[float(x) for x in single]]
        raise OllamaError(f"unexpected Ollama embed response: {list(data)}")
