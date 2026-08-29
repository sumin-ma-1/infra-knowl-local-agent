from infra_agent.agent.loop import run_agent
from infra_agent.tools.inventory_tools import build_registry


class ScriptedLLM:
    def __init__(self, responses):
        self.responses = list(responses)

    def chat(self, messages, tools=None):
        return self.responses.pop(0)


def test_agent_uses_get_server_then_answers(store):
    tools = build_registry(store)
    llm = ScriptedLLM(
        [
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_server",
                            "arguments": {"server_name": "gpu01"},
                        }
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "gpu01 SSH 포트는 22022입니다.",
            },
        ]
    )
    result = run_agent("gpu01 SSH 포트 알려줘", llm, tools)
    assert result.answer == "gpu01 SSH 포트는 22022입니다."
    assert result.tool_calls[0].name == "get_server"
    assert "22022" in result.tool_calls[0].result


def test_agent_parses_text_tool_calls(store):
    tools = build_registry(store)
    llm = ScriptedLLM(
        [
            {
                "role": "assistant",
                "content": (
                    "<tool_call>\n"
                    '{"name": "search_inventory", "arguments": {"query": "ollama"}}\n'
                    "</tool_call>"
                ),
            },
            {"role": "assistant", "content": "Ollama는 gpu-server-01에서 실행됩니다."},
        ]
    )
    result = run_agent("Ollama가 어디서 돌고 있어?", llm, tools)
    assert result.tool_calls[0].name == "search_inventory"
    assert "gpu-server-01" in result.tool_calls[0].result
    assert "gpu-server-01" in result.answer


def test_parse_truncated_tool_call_xml():
    from infra_agent.agent.loop import parse_text_tool_calls

    calls = parse_text_tool_calls(
        'leton\n{"name": "search_inventory", "arguments": {"query": "ollama"}}\n</tool_call>'
    )
    assert calls[0]["function"]["name"] == "search_inventory"
    assert calls[0]["function"]["arguments"]["query"] == "ollama"


def test_agent_nudges_when_first_reply_skips_tools(store):
    tools = build_registry(store)
    llm = ScriptedLLM(
        [
            {"role": "assistant", "content": "gpu01은 내부망에 있습니다."},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "get_server",
                            "arguments": {"server_name": "gpu01"},
                        }
                    }
                ],
            },
            {
                "role": "assistant",
                "content": "gpu01은 192.168.10.0/24 GPU 네트워크에 있습니다.",
            },
        ]
    )
    result = run_agent("gpu01은 어느 네트워크에 있어?", llm, tools)
    assert result.tool_calls[0].name == "get_server"
    assert "192.168.10" in result.answer
