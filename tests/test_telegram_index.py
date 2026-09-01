from pathlib import Path

from infra_agent.telegram_index.store import IndexedMessage, MessageIndex
from infra_agent.telegram_index.sync import is_watched_chat
from infra_agent.tools.telegram import register_telegram_index_tools
from infra_agent.tools.inventory_tools import ToolRegistry


def _msg(
    chat_id: int,
    message_id: int,
    text: str,
    *,
    date: str = "2026-08-01T00:00:00+00:00",
    sender: str = "수민",
    title: str = "뉴로팀",
) -> IndexedMessage:
    return IndexedMessage(
        chat_id=chat_id,
        message_id=message_id,
        date=date,
        sender_id=1,
        sender_name=sender,
        chat_title=title,
        text=text,
    )


def test_search_matches_korean_and_english(tmp_path: Path):
    index = MessageIndex(tmp_path / "index.sqlite")
    index.add_messages(
        [
            _msg(-1001, 1, "GPU 서버 SSH 포트 22022로 바꿨어요", date="2026-08-02T10:00:00+00:00"),
            _msg(-1001, 2, "사무실 wifi는 별도 노트에 있음", date="2026-08-03T10:00:00+00:00"),
            _msg(-1002, 3, "다른 방 잡담", date="2026-08-04T10:00:00+00:00", title="잡담"),
        ]
    )
    hits = index.search("SSH 포트")
    assert hits["count"] == 1
    assert "22022" in hits["results"][0]["text"]
    only_other = index.search("잡담", chat_id=-1002)
    assert only_other["count"] == 1
    recent = index.recent(chat_id=-1001, limit=1)
    assert recent["results"][0]["message_id"] == 2


def test_search_stems_korean_endings(tmp_path: Path):
    index = MessageIndex(tmp_path / "index.sqlite")
    index.add_messages(
        [_msg(-1001, 1, "IRIS 암호 변경했습니다. secret-placeholder")]
    )
    hits = index.search("iris 변경된 암호")
    assert hits["count"] == 1
    assert "변경했습니다" in hits["results"][0]["text"]


def test_is_watched_chat_only_registered_rooms():
    keep = {-5141393598, -5502317810}
    assert is_watched_chat(-5141393598, keep) is True
    assert is_watched_chat(-5502317810, keep) is True
    assert is_watched_chat(-1, keep) is False
    assert is_watched_chat(None, keep) is False


def test_incremental_last_message_id(tmp_path: Path):
    index = MessageIndex(tmp_path / "index.sqlite")
    assert index.last_message_id(-1001) == 0
    index.add_messages([_msg(-1001, 10, "첫번째"), _msg(-1001, 11, "두번째")])
    assert index.last_message_id(-1001) == 11
    index.add_messages([_msg(-1001, 12, "세번째")])
    assert index.last_message_id(-1001) == 12
    stats = index.stats()
    assert stats["message_count"] == 3


def test_prune_unlisted_removes_only_dropped_chat(tmp_path: Path):
    index = MessageIndex(tmp_path / "index.sqlite")
    index.add_messages(
        [
            _msg(-5141393598, 1, "테스트방 기록", title="테스트"),
            _msg(-5502317810, 1, "실제방 기록", title="실제"),
        ]
    )
    removed = index.prune_unlisted([-5502317810])
    assert len(removed) == 1
    assert removed[0]["chat_id"] == -5141393598
    assert removed[0]["deleted_messages"] == 1
    assert index.search("테스트방")["count"] == 0
    assert index.search("실제방")["count"] == 1
    assert index.prune_unlisted([]) == []
    assert index.search("실제방")["count"] == 1


def test_search_telegram_tool_uses_index(tmp_path: Path):
    db = tmp_path / "index.sqlite"
    index = MessageIndex(db)
    index.add_messages([_msg(-5141393598, 1, "시흥 GPU SSH는 22022")])

    class FakeSettings:
        def resolved_telegram_index_db(self) -> Path:
            return db

    registry = ToolRegistry()
    register_telegram_index_tools(registry, FakeSettings())
    raw = registry.call("search_telegram", {"query": "시흥 GPU"})
    assert "22022" in raw
    recent = registry.call("get_recent_messages", {"chat_id": "-5141393598", "limit": 5})
    assert "22022" in recent
