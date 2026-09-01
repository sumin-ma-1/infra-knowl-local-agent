"""CLI: login once, then sync TELEGRAM_INDEX_CHATS into the local SQLite index."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys

from infra_agent.config import get_settings
from infra_agent.telegram_index.store import MessageIndex
from infra_agent.telegram_index.sync import login, session_exists, sync_chats


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Telegram group history indexer")
    parser.add_argument(
        "command",
        nargs="?",
        default="sync",
        choices=["login", "sync", "status", "drop"],
        help=(
            "login: 전화번호 인증(최초 1회). sync: 가져오기 + 목록에서 뺀 방 삭제. "
            "status: 인덱스 현황. drop: 특정 방만 로컬에서 삭제."
        ),
    )
    parser.add_argument(
        "--chat-id",
        type=int,
        default=None,
        help="drop 할 Bot API chat_id (음수 그룹 ID)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=logging.INFO,
    )
    settings = get_settings()
    if args.command == "login":
        return asyncio.run(_login(settings))
    if args.command == "status":
        store = MessageIndex(settings.resolved_telegram_index_db())
        print(json.dumps(store.stats(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "drop":
        if args.chat_id is None:
            print(
                "drop 에는 --chat-id 가 필요합니다. 예: --chat-id -5141393598",
                file=sys.stderr,
            )
            return 1
        store = MessageIndex(settings.resolved_telegram_index_db())
        result = store.delete_chat(args.chat_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    return asyncio.run(_sync(settings))


async def _login(settings) -> int:
    if not settings.telegram_user_ready():
        print(
            "TELEGRAM_API_ID 와 TELEGRAM_API_HASH 를 .env에 넣으세요. "
            "https://my.telegram.org",
            file=sys.stderr,
        )
        return 1
    info = await login(settings)
    print(json.dumps({"ok": True, "user": info}, ensure_ascii=False, indent=2))
    print("이제 `python -m infra_agent.telegram_index sync` 로 방 히스토리를 가져오세요.")
    return 0


async def _sync(settings) -> int:
    if not session_exists(settings):
        print(
            "세션이 없습니다. 먼저 `python -m infra_agent.telegram_index login` 을 실행하세요.",
            file=sys.stderr,
        )
        return 1
    try:
        result = await sync_chats(settings)
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
