"""Telegram Bot frontend for the Infra Knowledge Agent.

This is the chat UI, not the conversation-search tool.
Add the bot to an existing group later; it only answers /ask, @mentions,
or replies to its own messages. Registered group history is indexed live
by the user-account Telethon client (`run_live_index`).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from collections import defaultdict

from telegram import Update
from telegram.constants import ChatAction, ChatType
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from infra_agent.agent.loop import run_agent
from infra_agent.agent.ollama import OllamaClient
from infra_agent.config import get_settings
from infra_agent.inventory.store import InventoryStore
from infra_agent.telegram_format import reply_markdownish
from infra_agent.telegram_policy import chat_allowed, extract_ask_command, group_question
from infra_agent.tools.inventory_tools import build_registry

log = logging.getLogger("infra_agent.telegram")
TELEGRAM_MAX = 4000


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Infra Knowledge Agent Telegram bot")
    parser.parse_args(argv)
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    settings = get_settings()
    token = (settings.telegram_bot_token or "").strip()
    if not token:
        print(
            "TELEGRAM_BOT_TOKEN 이 없습니다. BotFather에서 봇을 만들고 .env에 넣으세요.",
            file=sys.stderr,
        )
        return 1

    store = InventoryStore(settings.resolved_inventory_dir())
    tools = build_registry(store)
    llm = OllamaClient(
        host=settings.ollama_host,
        model=settings.ollama_model,
        timeout=settings.agent_timeout_seconds,
    )
    allowed = settings.allowed_chat_id_set()
    histories: dict[int, list[dict]] = defaultdict(list)
    locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.effective_chat:
            log.info("chat_id=%s type=%s", update.effective_chat.id, update.effective_chat.type)
        if not update.message:
            return
        await update.message.reply_text(
            "인프라 조회 봇입니다.\n"
            "개인 채팅: 그냥 질문하세요. 예: 판교 사무실 wifi\n"
            "단체방: /ask 시흥 서버 SSH  또는  @봇이름 질문\n\n"
            f"chat_id: {update.effective_chat.id if update.effective_chat else '?'}"
        )

    async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if update.message:
            await update.message.reply_text(
                "예: 판교 사무실 wifi 알려줘\n"
                "단체방: /ask 시흥 서버 SSH"
            )

    async def ask_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not update.message or not update.message.text:
            return
        question = extract_ask_command(update.message.text) or ""
        if not question:
            await update.message.reply_text("질문을 같이 보내 주세요. 예: /ask 판교 wifi")
            return
        await _reply_with_agent(update, context, question)

    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.message
        if not message or not message.text or not update.effective_chat:
            return
        chat = update.effective_chat
        bot_username = context.bot.username or ""
        is_private = chat.type == ChatType.PRIVATE
        if is_private:
            await _reply_with_agent(update, context, message.text.strip())
            return
        reply_user = message.reply_to_message.from_user if message.reply_to_message else None
        is_reply_to_bot = bool(reply_user and reply_user.id == context.bot.id)
        question = group_question(
            message.text,
            bot_username=bot_username,
            is_reply_to_bot=is_reply_to_bot,
        )
        if not question:
            return
        await _reply_with_agent(update, context, question)

    async def _reply_with_agent(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        question: str,
    ) -> None:
        message = update.message
        chat = update.effective_chat
        if not message or not chat:
            return
        if not chat_allowed(chat.id, allowed):
            log.info("ignored chat_id=%s (not in TELEGRAM_ALLOWED_CHAT_IDS)", chat.id)
            return
        if not question.strip():
            await message.reply_text("질문이 비어 있습니다.")
            return

        lock = locks[chat.id]
        async with lock:
            history = histories[chat.id]
            stop_typing = asyncio.Event()
            typer = asyncio.create_task(
                _keep_typing(context.bot, chat.id, stop_typing)
            )
            try:
                result = await asyncio.to_thread(
                    run_agent,
                    question,
                    llm,
                    tools,
                    settings.agent_max_steps,
                    history,
                )
            except Exception:
                log.exception("agent failed chat_id=%s", chat.id)
                await message.reply_text("조회 중 오류가 났습니다. 잠시 후 다시 시도해 주세요.")
                return
            finally:
                stop_typing.set()
                await typer
            history.append({"role": "user", "content": question})
            history.append({"role": "assistant", "content": result.answer})
            del history[:-12]
            text = result.answer.strip() or "(빈 응답)"
            for chunk in _chunks(text):
                await reply_markdownish(message, chunk)

    async def on_startup(application: Application) -> None:
        from infra_agent.telegram_index.sync import run_live_index

        stop = asyncio.Event()
        application.bot_data["index_stop"] = stop
        application.bot_data["index_task"] = asyncio.create_task(
            run_live_index(settings, stop),
            name="telegram-index",
        )

    async def on_shutdown(application: Application) -> None:
        stop = application.bot_data.get("index_stop")
        if stop:
            stop.set()
        task = application.bot_data.get("index_task")
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    app = (
        Application.builder()
        .token(token)
        .post_init(on_startup)
        .post_shutdown(on_shutdown)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("ask", ask_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    log.info(
        "polling model=%s allowlist=%s index_chats=%s",
        settings.ollama_model,
        "open" if allowed is None else sorted(allowed),
        settings.index_chat_ids(),
    )
    app.run_polling(allowed_updates=["message"])
    return 0


def _chunks(text: str, limit: int = TELEGRAM_MAX) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    rest = text
    while rest:
        parts.append(rest[:limit])
        rest = rest[limit:]
    return parts


async def _keep_typing(bot, chat_id: int, stop: asyncio.Event) -> None:
    """Telegram typing indicators expire after ~5s; refresh until stop is set."""
    while not stop.is_set():
        try:
            await bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
        except Exception:
            log.debug("typing refresh failed", exc_info=True)
        try:
            await asyncio.wait_for(stop.wait(), timeout=4.0)
        except asyncio.TimeoutError:
            continue


if __name__ == "__main__":
    raise SystemExit(main())
