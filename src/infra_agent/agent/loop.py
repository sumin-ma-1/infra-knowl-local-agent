from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from infra_agent.agent.prompts import SYSTEM_PROMPT
from infra_agent.tools.inventory_tools import ToolRegistry


class LLMClient(Protocol):
    def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        ...


@dataclass
class ToolTrace:
    name: str
    arguments: dict[str, Any]
    result: str


@dataclass
class AgentResult:
    answer: str
    tool_calls: list[ToolTrace] = field(default_factory=list)
    steps: int = 0


_TOOL_CALL_BLOCK = re.compile(
    r"<tool_call>\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL,
)
_TOOL_CALL_NAME_ARGS = re.compile(
    r"<tool_call>\s*([a-zA-Z_][\w]*)\s*(\{.*?\})\s*</tool_call>",
    re.DOTALL,
)
_JSON_TOOL = re.compile(
    r'\{\s*"name"\s*:\s*"([^"]+)"\s*,\s*"arguments"\s*:\s*(\{.*?\})\s*\}',
    re.DOTALL,
)
_CHITCHAT = re.compile(
    r"^(안녕|안녕하세요|안녕하십니까|하이|헬로|hello|hi|hey|ㅎㅇ|"
    r"고마워|감사합니다|감사|땡큐|thanks|thank you|"
    r"응|네|아니|ㅇㅋ|ok|okay|ㅎ)[\s!?.~ㅋㅎ]*$",
    re.IGNORECASE,
)
_INSTRUCTION_ACK = re.compile(
    r"알겠습니다|주의하겠|앞으로는|해당 도구|read_lab_note|"
    r"간결하게 답변|반드시.*사용|시스템 프롬프트",
    re.IGNORECASE,
)


def is_chitchat(text: str) -> bool:
    return bool(_CHITCHAT.match((text or "").strip()))


def _is_instruction_ack(text: str) -> bool:
    return bool(_INSTRUCTION_ACK.search(text or ""))


def run_agent(
    question: str,
    llm: LLMClient,
    tools: ToolRegistry,
    max_steps: int = 8,
    history: list[dict[str, Any]] | None = None,
) -> AgentResult:
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": question})

    traces: list[ToolTrace] = []
    schemas = tools.schemas()

    for step in range(1, max_steps + 1):
        message = llm.chat(messages, tools=schemas)
        tool_calls = list(message.get("tool_calls") or [])
        content = (message.get("content") or "").strip()
        if not tool_calls:
            tool_calls = parse_text_tool_calls(content)

        assistant_msg: dict[str, Any] = {
            "role": "assistant",
            "content": "" if tool_calls else (message.get("content") or ""),
        }
        if tool_calls:
            assistant_msg["tool_calls"] = tool_calls
        messages.append(assistant_msg)

        if not tool_calls:
            if (
                step == 1
                and not traces
                and not is_chitchat(question)
                and _is_instruction_ack(content)
            ):
                messages.append({"role": "user", "content": question})
                continue
            return AgentResult(answer=content, tool_calls=traces, steps=step)

        for call in tool_calls:
            name, arguments = _parse_tool_call(call)
            result = tools.call(name, arguments)
            traces.append(ToolTrace(name=name, arguments=arguments, result=result))
            messages.append(
                {
                    "role": "tool",
                    "tool_name": name,
                    "content": result,
                }
            )

    return AgentResult(
        answer="도구 호출이 너무 많아 중단했습니다. 질문을 더 구체적으로 해 주세요.",
        tool_calls=traces,
        steps=max_steps,
    )


def parse_text_tool_calls(content: str) -> list[dict[str, Any]]:
    if not content:
        return []
    calls: list[dict[str, Any]] = []
    for match in _TOOL_CALL_BLOCK.finditer(content):
        parsed = _tool_payload(match.group(1))
        if parsed:
            calls.append(parsed)
    if calls:
        return calls
    for match in _TOOL_CALL_NAME_ARGS.finditer(content):
        arguments = _load_json_object(match.group(2)) or {}
        calls.append(
            {"function": {"name": match.group(1), "arguments": arguments}}
        )
    if calls:
        return calls
    if "<tool_call>" in content or "</tool_call>" in content or content.lstrip().startswith("{"):
        for match in _JSON_TOOL.finditer(content):
            arguments = _load_json_object(match.group(2)) or {}
            calls.append(
                {"function": {"name": match.group(1), "arguments": arguments}}
            )
    return calls


def _tool_payload(raw: str) -> dict[str, Any] | None:
    parsed = _load_json_object(raw)
    if not parsed:
        return None
    name = str(parsed.get("name") or "")
    arguments = parsed.get("arguments") or parsed.get("parameters") or {}
    if isinstance(arguments, str):
        arguments = _load_json_object(arguments) or {}
    if name and isinstance(arguments, dict):
        return {"function": {"name": name, "arguments": arguments}}
    return None


def _load_json_object(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def _parse_tool_call(call: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    fn = call.get("function") or call
    name = str(fn.get("name") or call.get("name") or "")
    raw_args = fn.get("arguments", {})
    if isinstance(raw_args, str):
        raw_args = json.loads(raw_args) if raw_args.strip() else {}
    if not isinstance(raw_args, dict):
        raw_args = {}
    return name, raw_args
