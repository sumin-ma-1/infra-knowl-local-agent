"""SQLite store for indexed Telegram messages."""

from __future__ import annotations

import re
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any


_TOKEN = re.compile(r"\w+", re.UNICODE)


@dataclass(frozen=True)
class IndexedMessage:
    chat_id: int
    message_id: int
    date: str
    sender_id: int | None
    sender_name: str
    chat_title: str
    text: str


class MessageIndex:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
            self._init_schema()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def upsert_chat(
        self,
        chat_id: int,
        title: str,
        chat_type: str,
        last_message_id: int | None = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO chats (chat_id, title, chat_type, last_message_id, indexed_at)
                VALUES (?, ?, ?, ?, datetime('now'))
                ON CONFLICT(chat_id) DO UPDATE SET
                    title = excluded.title,
                    chat_type = excluded.chat_type,
                    last_message_id = CASE
                        WHEN excluded.last_message_id > chats.last_message_id
                        THEN excluded.last_message_id
                        ELSE chats.last_message_id
                    END,
                    indexed_at = excluded.indexed_at
                """,
                (chat_id, title, chat_type, last_message_id or 0),
            )
            self._conn.commit()

    def last_message_id(self, chat_id: int) -> int:
        with self._lock:
            row = self._conn.execute(
                "SELECT last_message_id FROM chats WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
        return int(row["last_message_id"]) if row else 0

    def add_messages(self, messages: list[IndexedMessage]) -> int:
        if not messages:
            return 0
        with self._lock:
            self._conn.executemany(
                """
                INSERT INTO messages (
                    chat_id, message_id, date, sender_id, sender_name, chat_title, text
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, message_id) DO UPDATE SET
                    date = excluded.date,
                    sender_id = excluded.sender_id,
                    sender_name = excluded.sender_name,
                    chat_title = excluded.chat_title,
                    text = excluded.text
                """,
                [
                    (
                        m.chat_id,
                        m.message_id,
                        m.date,
                        m.sender_id,
                        m.sender_name,
                        m.chat_title,
                        m.text,
                    )
                    for m in messages
                ],
            )
            by_chat: dict[int, int] = {}
            titles: dict[int, str] = {}
            for m in messages:
                by_chat[m.chat_id] = max(by_chat.get(m.chat_id, 0), m.message_id)
                titles[m.chat_id] = m.chat_title
            for chat_id, last_id in by_chat.items():
                self._conn.execute(
                    """
                    INSERT INTO chats (chat_id, title, chat_type, last_message_id, indexed_at)
                    VALUES (?, ?, '', ?, datetime('now'))
                    ON CONFLICT(chat_id) DO UPDATE SET
                        title = CASE
                            WHEN excluded.title != '' THEN excluded.title
                            ELSE chats.title
                        END,
                        last_message_id = MAX(chats.last_message_id, excluded.last_message_id),
                        indexed_at = excluded.indexed_at
                    """,
                    (chat_id, titles[chat_id], last_id),
                )
            self._conn.commit()
        return len(messages)

    def search(
        self,
        query: str,
        chat_id: int | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        tokens = [t for t in _TOKEN.findall(query or "") if t]
        if not tokens:
            stripped = (query or "").strip()
            tokens = [stripped] if stripped else []
        if not tokens:
            return {
                "query": query,
                "count": 0,
                "hint": "검색어가 비어 있습니다.",
                "results": [],
            }

        clauses = ["1=1"]
        params: list[Any] = []
        for token in tokens:
            clauses.append("(text LIKE ? OR sender_name LIKE ? OR chat_title LIKE ?)")
            like = f"%{token}%"
            params.extend([like, like, like])
        if chat_id is not None:
            clauses.append("chat_id = ?")
            params.append(chat_id)
        if start_date:
            clauses.append("date >= ?")
            params.append(start_date)
        if end_date:
            clauses.append("date <= ?")
            params.append(end_date)
        limit = max(1, min(int(limit or 20), 50))
        sql = f"""
            SELECT chat_id, message_id, date, sender_id, sender_name, chat_title, text
            FROM messages
            WHERE {' AND '.join(clauses)}
            ORDER BY date DESC, message_id DESC
            LIMIT ?
        """
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        results = [_row_to_hit(row) for row in rows]
        return {
            "query": query,
            "chat_id": chat_id,
            "count": len(results),
            "results": results,
        }

    def recent(self, chat_id: int | None = None, limit: int = 30) -> dict[str, Any]:
        limit = max(1, min(int(limit or 30), 80))
        sql = """
            SELECT chat_id, message_id, date, sender_id, sender_name, chat_title, text
            FROM messages
        """
        params: list[Any] = []
        if chat_id is not None:
            sql += " WHERE chat_id = ?"
            params.append(chat_id)
        sql += " ORDER BY date DESC, message_id DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        results = [_row_to_hit(row) for row in rows]
        return {"chat_id": chat_id, "count": len(results), "results": results}

    def stats(self) -> dict[str, Any]:
        with self._lock:
            chats = [
                {
                    "chat_id": row["chat_id"],
                    "title": row["title"],
                    "chat_type": row["chat_type"],
                    "last_message_id": row["last_message_id"],
                    "indexed_at": row["indexed_at"],
                    "messages": row["messages"],
                }
                for row in self._conn.execute(
                    """
                    SELECT c.chat_id, c.title, c.chat_type, c.last_message_id, c.indexed_at,
                           COUNT(m.message_id) AS messages
                    FROM chats c
                    LEFT JOIN messages m ON m.chat_id = c.chat_id
                    GROUP BY c.chat_id
                    ORDER BY c.title
                    """
                ).fetchall()
            ]
            total = self._conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        return {"chats": chats, "message_count": int(total)}

    def delete_chat(self, chat_id: int) -> dict[str, Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT title FROM chats WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()
            deleted = self._conn.execute(
                "SELECT COUNT(*) FROM messages WHERE chat_id = ?",
                (chat_id,),
            ).fetchone()[0]
            self._conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
            self._conn.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))
            self._conn.commit()
        return {
            "chat_id": chat_id,
            "title": row["title"] if row else "",
            "deleted_messages": int(deleted),
        }

    def prune_unlisted(self, keep_ids: list[int]) -> list[dict[str, Any]]:
        """Delete chats that are not in keep_ids. Empty keep_ids is a no-op."""
        keep = {int(cid) for cid in keep_ids}
        if not keep:
            return []
        with self._lock:
            rows = self._conn.execute("SELECT chat_id FROM chats").fetchall()
        removed: list[dict[str, Any]] = []
        for row in rows:
            chat_id = int(row["chat_id"])
            if chat_id not in keep:
                removed.append(self.delete_chat(chat_id))
        return removed

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                chat_type TEXT NOT NULL DEFAULT '',
                last_message_id INTEGER NOT NULL DEFAULT 0,
                indexed_at TEXT
            );
            CREATE TABLE IF NOT EXISTS messages (
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                sender_id INTEGER,
                sender_name TEXT NOT NULL DEFAULT '',
                chat_title TEXT NOT NULL DEFAULT '',
                text TEXT NOT NULL,
                PRIMARY KEY (chat_id, message_id)
            );
            CREATE INDEX IF NOT EXISTS idx_messages_date ON messages(date);
            """
        )
        self._conn.commit()


def _row_to_hit(row: sqlite3.Row) -> dict[str, Any]:
    text = row["text"] or ""
    if len(text) > 800:
        text = text[:800] + "…"
    return {
        "chat_id": row["chat_id"],
        "chat_title": row["chat_title"],
        "message_id": row["message_id"],
        "date": row["date"],
        "sender": row["sender_name"],
        "text": text,
    }
