"""Rules for when the Telegram bot should answer.

Group chats only get a reply on /ask, an @mention, or a reply to the bot.
That way the bot can later join an existing group without answering every line.
"""

from __future__ import annotations

import re


def parse_id_list(raw: str) -> list[int]:
    """Parse comma-separated chat ids. Inline # comments are ignored."""
    text = (raw or "").split("#", 1)[0].strip()
    if not text:
        return []
    ids: list[int] = []
    seen: set[int] = set()
    for part in text.split(","):
        part = part.strip()
        if not part:
            continue
        value = int(part)
        if value in seen:
            continue
        seen.add(value)
        ids.append(value)
    return ids


def parse_allowed_chat_ids(raw: str) -> frozenset[int] | None:
    ids = parse_id_list(raw)
    if not ids:
        return None
    return frozenset(ids)


def chat_allowed(chat_id: int, allowed: frozenset[int] | None) -> bool:
    if allowed is None:
        return True
    return chat_id in allowed


def extract_ask_command(text: str) -> str | None:
    """Return the question after /ask or /ask@botname, or None if not that command."""
    if not text:
        return None
    match = re.match(r"^/ask(?:@[A-Za-z0-9_]+)?(?:\s+|$)(.*)$", text, flags=re.DOTALL)
    if not match:
        return None
    return match.group(1).strip()


def extract_mention_question(text: str, bot_username: str) -> str | None:
    if not text or not bot_username:
        return None
    pattern = re.compile(rf"@{re.escape(bot_username)}\b", re.IGNORECASE)
    if not pattern.search(text):
        return None
    cleaned = pattern.sub(" ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def group_question(
    text: str,
    *,
    bot_username: str,
    is_reply_to_bot: bool,
) -> str | None:
    """Question text if this group message is directed at the bot."""
    asked = extract_ask_command(text)
    if asked is not None:
        return asked
    mentioned = extract_mention_question(text, bot_username)
    if mentioned:
        return mentioned
    if is_reply_to_bot:
        return (text or "").strip()
    return None
