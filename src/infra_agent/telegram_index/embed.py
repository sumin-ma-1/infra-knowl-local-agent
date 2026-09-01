"""Embed indexed Telegram messages via Ollama and write vectors to SQLite."""

from __future__ import annotations

import logging
from typing import Any

from infra_agent.agent.ollama import OllamaClient
from infra_agent.config import Settings
from infra_agent.telegram_index.store import IndexedMessage, MessageIndex

log = logging.getLogger("infra_agent.telegram_index")


class MessageEmbedder:
    def __init__(self, host: str, model: str, timeout: float = 120.0) -> None:
        self.model = model
        self.client = OllamaClient(host=host, model=model, timeout=timeout)

    @classmethod
    def from_settings(cls, settings: Settings) -> MessageEmbedder | None:
        getter = getattr(settings, "embed_model_name", None)
        model = getter() if callable(getter) else getattr(settings, "ollama_embed_model", "")
        model = (model or "").strip()
        if not model:
            return None
        return cls(
            host=getattr(settings, "ollama_host", "http://127.0.0.1:11434"),
            model=model,
            timeout=float(getattr(settings, "agent_timeout_seconds", 120) or 120),
        )

    def embed_query(self, query: str) -> list[float]:
        vectors = self.client.embed([query], model=self.model)
        return vectors[0]

    def index_texts(
        self,
        store: MessageIndex,
        rows: list[dict[str, Any]] | list[IndexedMessage],
    ) -> int:
        if not rows:
            return 0
        texts: list[str] = []
        keys: list[tuple[int, int]] = []
        for row in rows:
            if isinstance(row, IndexedMessage):
                text = row.text
                key = (row.chat_id, row.message_id)
            else:
                text = str(row.get("text") or "")
                key = (int(row["chat_id"]), int(row["message_id"]))
            if not text.strip():
                continue
            texts.append(text)
            keys.append(key)
        if not texts:
            return 0
        vectors = self.client.embed(texts, model=self.model)
        return store.upsert_embeddings(
            [
                (chat_id, message_id, self.model, vector)
                for (chat_id, message_id), vector in zip(keys, vectors)
            ]
        )

    def backfill(self, store: MessageIndex, batch_size: int = 32) -> dict[str, Any]:
        embedded = 0
        batches = 0
        while True:
            missing = store.messages_without_embedding(self.model, limit=batch_size)
            if not missing:
                break
            embedded += self.index_texts(store, missing)
            batches += 1
            log.info(
                "embedded %s messages model=%s total_stored=%s",
                embedded,
                self.model,
                store.embedding_count(self.model),
            )
        return {
            "model": self.model,
            "embedded": embedded,
            "batches": batches,
            "stored": store.embedding_count(self.model),
        }
