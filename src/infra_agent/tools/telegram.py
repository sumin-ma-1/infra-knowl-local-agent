"""Search indexed Telegram group history (local SQLite, filled by Telethon)."""

from __future__ import annotations

from typing import Any

from infra_agent.config import Settings
from infra_agent.telegram_index.store import MessageIndex
from infra_agent.tools.inventory_tools import ToolRegistry


def register_telegram_index_tools(registry: ToolRegistry, settings: Settings) -> None:
    store = MessageIndex(settings.resolved_telegram_index_db())

    def search_telegram(
        query: str,
        chat_id: str | int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """인덱싱된 텔레그램 단체방 과거 메시지를 검색한다."""
        if not (query or "").strip():
            return {"error": "query가 비어 있습니다."}
        parsed = _optional_chat_id(chat_id)
        result = store.search(
            query=query,
            chat_id=parsed,
            start_date=start_date,
            end_date=end_date,
        )
        if result["count"] == 0:
            stats = store.stats()
            result["hint"] = (
                "인덱스에 맞는 메시지가 없습니다. "
                f"저장된 메시지 {stats['message_count']}개. "
                "서버에서 `python -m infra_agent.telegram_index sync` 를 실행했는지 확인하세요."
            )
        return result

    def get_recent_messages(
        chat_id: str | int | None = None,
        limit: int = 30,
    ) -> dict[str, Any]:
        """인덱싱된 텔레그램 방의 최근 메시지를 시간 역순으로 가져온다."""
        parsed = _optional_chat_id(chat_id)
        result = store.recent(chat_id=parsed, limit=limit)
        if result["count"] == 0:
            stats = store.stats()
            result["hint"] = (
                "인덱스가 비어 있습니다. "
                f"저장된 메시지 {stats['message_count']}개. "
                "`python -m infra_agent.telegram_index sync` 로 동기화하세요."
            )
        return result

    registry.register(
        {
            "type": "function",
            "function": {
                "name": "search_telegram",
                "description": (
                    "인덱싱해 둔 텔레그램 단체방 과거 대화를 검색한다. "
                    "누가 언제 뭐라고 했는지, 방 합의, 노트에 없는 맥락을 물을 때 사용한다. "
                    "서버 IP/SSH/Wi-Fi 같은 공식 현황은 read_lab_note를 먼저 쓴다. "
                    "query 예: 'SSH 포트', '시흥 서버', 'vpn'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "검색어",
                        },
                        "chat_id": {
                            "type": "string",
                            "description": "특정 방만 검색할 Bot API chat_id. 생략하면 인덱싱된 모든 방.",
                        },
                        "start_date": {
                            "type": "string",
                            "description": "이 시각 이후만. ISO 8601. 예: 2026-01-01",
                        },
                        "end_date": {
                            "type": "string",
                            "description": "이 시각 이전만. ISO 8601.",
                        },
                    },
                    "required": ["query"],
                },
            },
        },
        search_telegram,
    )
    registry.register(
        {
            "type": "function",
            "function": {
                "name": "get_recent_messages",
                "description": (
                    "인덱싱된 텔레그램 방의 최근 메시지를 가져온다. "
                    "방금 전에 방에서 나온 맥락이 필요할 때 사용한다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "chat_id": {
                            "type": "string",
                            "description": "Bot API chat_id. 생략하면 인덱싱된 모든 방에서 최근 글.",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "가져올 개수. 기본 30, 최대 80.",
                        },
                    },
                },
            },
        },
        get_recent_messages,
    )


def _optional_chat_id(chat_id: str | int | None) -> int | None:
    if chat_id is None or chat_id == "":
        return None
    return int(str(chat_id).strip())
