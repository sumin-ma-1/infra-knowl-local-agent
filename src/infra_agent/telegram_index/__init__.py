"""Local index of Telegram group history (user-account client, not the bot)."""

from infra_agent.telegram_index.store import MessageIndex, IndexedMessage

__all__ = ["MessageIndex", "IndexedMessage"]
