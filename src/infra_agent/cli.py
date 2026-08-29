from __future__ import annotations

import argparse
import sys

from infra_agent.agent.loop import run_agent
from infra_agent.agent.ollama import OllamaClient
from infra_agent.config import get_settings
from infra_agent.inventory.store import InventoryStore
from infra_agent.tools.inventory_tools import build_registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Infra Knowledge Agent CLI")
    parser.add_argument("question", nargs="*", help="한 줄 질문. 없으면 대화 모드.")
    args = parser.parse_args(argv)

    settings = get_settings()
    store = InventoryStore(settings.resolved_inventory_dir())
    tools = build_registry(store)
    llm = OllamaClient(
        host=settings.ollama_host,
        model=settings.ollama_model,
        timeout=settings.agent_timeout_seconds,
    )
    history: list[dict] = []

    question = " ".join(args.question).strip()
    if question:
        _ask(question, llm, tools, settings.agent_max_steps, history)
        return 0

    print(f"Infra Knowledge Agent  ({settings.ollama_model})")
    print("종료: Ctrl-D 또는 /exit")
    while True:
        try:
            line = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not line or line in {"/exit", "/quit"}:
            return 0
        _ask(line, llm, tools, settings.agent_max_steps, history)


def _ask(question: str, llm, tools, max_steps: int, history: list[dict]) -> None:
    result = run_agent(
        question=question,
        llm=llm,
        tools=tools,
        max_steps=max_steps,
        history=history,
    )
    for trace in result.tool_calls:
        print(f"  tool {trace.name}({trace.arguments})")
    print()
    print(result.answer)
    print()
    history.append({"role": "user", "content": question})
    history.append({"role": "assistant", "content": result.answer})
    del history[:-12]


if __name__ == "__main__":
    sys.exit(main())
