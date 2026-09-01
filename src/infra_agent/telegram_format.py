from __future__ import annotations

import html
import re

from telegram.constants import ParseMode


def to_telegram_html(text: str) -> str:
    """Turn common Markdown emphasis into Telegram HTML."""
    escaped = html.escape(text, quote=False)
    escaped = re.sub(r"```(?:\w+\n)?(.*?)```", r"<pre>\1</pre>", escaped, flags=re.DOTALL)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", escaped)
    return escaped


async def reply_markdownish(message, text: str) -> None:
    html_text = to_telegram_html(text)
    try:
        await message.reply_text(html_text, parse_mode=ParseMode.HTML)
    except Exception:
        await message.reply_text(text)
