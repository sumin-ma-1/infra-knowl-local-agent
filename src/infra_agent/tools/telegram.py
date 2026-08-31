"""Phase 3 stub: search *existing* Telegram group history.

This is not the bot frontend (`infra_agent.telegram_bot`). Bots cannot read
a group's past messages. History search needs a user-client API later.
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
