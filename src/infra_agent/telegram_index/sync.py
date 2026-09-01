"""Fetch Telegram group history via Telethon and write it to the local index."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from infra_agent.config import Settings
from infra_agent.telegram_index.store import IndexedMessage, MessageIndex

log = logging.getLogger("infra_agent.telegram_index")


def session_file(settings: Settings) -> Path:
    path = settings.resolved_telegram_session_path()
    if path.suffix == ".session":
        return path
    return path.with_suffix(".session")


def session_exists(settings: Settings) -> bool:
    return session_file(settings).is_file()


def session_name(settings: Settings) -> str:
    path = settings.resolved_telegram_session_path()
    if path.suffix == ".session":
        return str(path.with_suffix(""))
    return str(path)


async def login(settings: Settings) -> dict[str, Any]:
    client = _client(settings)
    await client.start(phone=settings.telegram_phone or None)
    me = await client.get_me()
    await client.disconnect()
    return _user_summary(me)


async def sync_chats(settings: Settings, store: MessageIndex | None = None) -> dict[str, Any]:
    if not settings.telegram_index_ready():
        raise RuntimeError(
            "TELEGRAM_API_ID, TELEGRAM_API_HASH, TELEGRAM_INDEX_CHATS 를 .env에 넣으세요."
        )
    if not session_exists(settings):
        raise RuntimeError(
            "텔레그램 세션이 없습니다. 서버에서 "
            "`python -m infra_agent.telegram_index login` 을 한 번 실행하세요."
        )
    if store is None:
        store = MessageIndex(settings.resolved_telegram_index_db())

    from telethon.errors import FloodWaitError, RPCError

    client = _client(settings)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        raise RuntimeError("세션이 만료되었습니다. login을 다시 실행하세요.")

    max_messages = int(settings.telegram_index_max_messages or 0)
    summaries: list[dict[str, Any]] = []
    try:
        for chat_id in settings.index_chat_ids():
            try:
                summary = await _sync_one(client, store, chat_id, max_messages)
            except FloodWaitError as exc:
                log.warning("flood wait chat_id=%s seconds=%s", chat_id, exc.seconds)
                summaries.append({"chat_id": chat_id, "error": f"flood wait {exc.seconds}s"})
                continue
            except (RPCError, ValueError) as exc:
                log.warning("sync failed chat_id=%s: %s", chat_id, exc)
                summaries.append({"chat_id": chat_id, "error": str(exc)})
                continue
            summaries.append(summary)
    finally:
        await client.disconnect()
    keep = set(settings.index_chat_ids())
    for item in summaries:
        cid = item.get("chat_id")
        if cid is not None:
            keep.add(int(cid))
    removed = store.prune_unlisted(list(keep))
    if removed:
        log.info(
            "pruned unlisted chats: %s",
            [(item["chat_id"], item.get("deleted_messages")) for item in removed],
        )
    return {"chats": summaries, "removed": removed, **store.stats()}


async def _sync_one(
    client: Any,
    store: MessageIndex,
    chat_id: int,
    max_messages: int,
) -> dict[str, Any]:
    entity = await _resolve_entity(client, chat_id)
    from telethon.utils import get_peer_id

    marked_id = int(get_peer_id(entity))
    title = _entity_title(entity)
    chat_type = entity.__class__.__name__
    store.upsert_chat(marked_id, title, chat_type)
    min_id = store.last_message_id(marked_id)
    added = 0
    batch: list[IndexedMessage] = []
    if min_id > 0:
        iterator = client.iter_messages(entity, min_id=min_id, reverse=True)
    elif max_messages > 0:
        iterator = client.iter_messages(entity, limit=max_messages)
    else:
        iterator = client.iter_messages(entity, reverse=True)

    async for message in iterator:
        sender = getattr(message, "sender", None)
        if sender is None:
            try:
                sender = await message.get_sender()
            except Exception:
                sender = None
        indexed = _to_indexed(message, marked_id, title, sender)
        if indexed is None:
            continue
        batch.append(indexed)
        if len(batch) >= 200:
            added += store.add_messages(batch)
            batch.clear()
    if batch:
        added += store.add_messages(batch)
    last_id = store.last_message_id(marked_id)
    log.info(
        "indexed chat_id=%s title=%s added=%s last_id=%s",
        marked_id,
        title,
        added,
        last_id,
    )
    return {
        "chat_id": marked_id,
        "title": title,
        "added": added,
        "last_message_id": last_id,
    }


async def _resolve_entity(client: Any, chat_id: int) -> Any:
    try:
        return await client.get_entity(chat_id)
    except (ValueError, TypeError):
        from telethon.tl.types import PeerChannel, PeerChat

        if chat_id < 0:
            raw = str(chat_id)
            if raw.startswith("-100"):
                return await client.get_entity(PeerChannel(int(raw[4:])))
            return await client.get_entity(PeerChat(-chat_id))
        raise


def _to_indexed(
    message: Any,
    chat_id: int,
    chat_title: str,
    sender: Any = None,
) -> IndexedMessage | None:
    text = (getattr(message, "message", None) or getattr(message, "text", None) or "").strip()
    if not text:
        return None
    msg_id = int(getattr(message, "id", 0) or 0)
    if msg_id <= 0:
        return None
    when = getattr(message, "date", None)
    if isinstance(when, datetime):
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        date = when.astimezone(timezone.utc).isoformat()
    else:
        date = datetime.now(timezone.utc).isoformat()
    if sender is None:
        sender = getattr(message, "sender", None)
    sender_id = None
    from_id = getattr(message, "from_id", None)
    if from_id is not None:
        sender_id = getattr(from_id, "user_id", None) or getattr(from_id, "channel_id", None)
    if sender is not None:
        sender_id = getattr(sender, "id", sender_id)
    return IndexedMessage(
        chat_id=chat_id,
        message_id=msg_id,
        date=date,
        sender_id=int(sender_id) if sender_id else None,
        sender_name=_entity_title(sender) if sender is not None else "",
        chat_title=chat_title,
        text=text,
    )


def _entity_title(entity: Any) -> str:
    if entity is None:
        return ""
    title = getattr(entity, "title", None)
    if title:
        return str(title)
    parts = [
        str(getattr(entity, "first_name", "") or ""),
        str(getattr(entity, "last_name", "") or ""),
    ]
    name = " ".join(p for p in parts if p).strip()
    if name:
        return name
    username = getattr(entity, "username", None)
    return f"@{username}" if username else str(getattr(entity, "id", "") or "")


def _user_summary(me: Any) -> dict[str, Any]:
    return {
        "id": getattr(me, "id", None),
        "username": getattr(me, "username", None),
        "name": _entity_title(me),
    }


def _client(settings: Settings) -> Any:
    from telethon import TelegramClient

    settings.resolved_telegram_session_path().parent.mkdir(parents=True, exist_ok=True)
    return TelegramClient(
        session_name(settings),
        int(settings.telegram_api_id),
        settings.telegram_api_hash.strip(),
    )
