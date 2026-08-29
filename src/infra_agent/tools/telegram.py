"""Phase 3 stub: Telegram conversation search.

Prefer BM25 + embedding hybrid search. Keyword matching is stronger for
ports, IPs, hostnames, and model numbers.
"""

from __future__ import annotations

from typing import Any


def search_telegram(
    query: str,
    chat_id: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    raise NotImplementedError("Telegram tool is planned for phase 3")


def get_recent_messages(chat_id: str, limit: int = 30) -> dict[str, Any]:
    raise NotImplementedError("Telegram tool is planned for phase 3")
