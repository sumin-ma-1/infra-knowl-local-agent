from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from infra_agent.inventory.store import InventoryStore
from infra_agent.inventory.models import InventoryDoc


ToolFn = Callable[..., Any]


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, tuple[dict[str, Any], ToolFn]] = {}

    def register(self, schema: dict[str, Any], fn: ToolFn) -> None:
        name = schema["function"]["name"]
        self._tools[name] = (schema, fn)

    def schemas(self) -> list[dict[str, Any]]:
        return [schema for schema, _ in self._tools.values()]

    def call(self, name: str, arguments: dict[str, Any] | str | None) -> str:
        if name not in self._tools:
            return json.dumps({"error": f"unknown tool: {name}"}, ensure_ascii=False)
        _, fn = self._tools[name]
        args = arguments or {}
        if isinstance(args, str):
            args = json.loads(args) if args.strip() else {}
        if not isinstance(args, dict):
            args = {}
        try:
            result = fn(**args)
        except TypeError as exc:
            return json.dumps({"error": f"invalid arguments: {exc}"}, ensure_ascii=False)
        except Exception as exc:  # noqa: BLE001 — surface tool errors to the LLM
            return json.dumps({"error": str(exc)}, ensure_ascii=False)
        if isinstance(result, str):
            return result
        return json.dumps(result, ensure_ascii=False, default=str)


def build_registry(store: InventoryStore) -> ToolRegistry:
    from infra_agent.config import get_settings

    registry = ToolRegistry()
    if store.docs:
        register_inventory_tools(registry, store)
    settings = get_settings()
    if settings.nextcloud_ready():
        register_lab_note_tool(registry, settings)
    return registry


def register_inventory_tools(registry: ToolRegistry, store: InventoryStore) -> None:
    def list_servers(type: str | None = None) -> dict[str, Any]:
        """등록된 서버 목록을 조회한다. type으로 gpu/nas/workstation 등을 필터할 수 있다."""
        store.reload_if_stale()
        servers = store.all("server")
        wanted = _normalize_type(type)
        items = []
        for doc in servers:
            server_type = str(doc.data.get("type", ""))
            if not _type_matches(server_type, wanted):
                continue
            items.append(_server_summary(doc.public_dict()))
        return {"count": len(items), "servers": items}

    def get_server(server_name: str) -> dict[str, Any]:
        """id, alias, hostname, IP로 특정 서버의 상세 정보를 조회한다."""
        store.reload_if_stale()
        doc = store.get(server_name)
        if doc is None or doc.kind != "server":
            matches = store.search(server_name, limit=5)
            suggestions = [
                {"id": d.id, "name": d.name, "kind": d.kind}
                for d, _, _ in matches
            ]
            return {
                "error": f"server not found: {server_name}",
                "suggestions": suggestions,
            }
        payload = doc.public_dict()
        payload["networks"] = _related_networks(store, doc)
        return payload

    def search_inventory(query: str) -> dict[str, Any]:
        """서버, 네트워크, 서비스 inventory를 keyword로 검색한다."""
        store.reload_if_stale()
        hits = store.search(query, limit=8)
        return {
            "query": query,
            "count": len(hits),
            "results": [
                {
                    "score": round(score, 2),
                    "matched": matched[:6],
                    **doc.public_dict(),
                }
                for doc, score, matched in hits
            ],
        }

    registry.register(
        {
            "type": "function",
            "function": {
                "name": "list_servers",
                "description": (
                    "등록된 인프라 서버 목록을 조회한다. "
                    "GPU 서버만 보려면 type='gpu' 또는 type='gpu_server'를 사용한다. "
                    "type을 생략하면 전체 서버를 반환한다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "서버 유형 필터. 예: gpu, gpu_server, nas, workstation",
                        }
                    },
                },
            },
        },
        list_servers,
    )
    registry.register(
        {
            "type": "function",
            "function": {
                "name": "get_server",
                "description": (
                    "특정 서버의 상세 정보(IP, hostname, SSH, GPU, services)를 조회한다. "
                    "서버 id, alias, hostname, IP 모두 사용할 수 있다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "server_name": {
                            "type": "string",
                            "description": "서버 id, alias, hostname 또는 IP. 예: gpu01, gpu-server-01",
                        }
                    },
                    "required": ["server_name"],
                },
            },
        },
        get_server,
    )
    registry.register(
        {
            "type": "function",
            "function": {
                "name": "search_inventory",
                "description": (
                    "서버/네트워크/서비스 Markdown inventory를 검색한다. "
                    "포트 번호, GPU 모델, 서비스명, CIDR, 별칭 등 정확한 값 조회에 사용한다. "
                    "예: '11434', 'RTX 5090', 'vpn', 'ollama'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "검색어",
                        }
                    },
                    "required": ["query"],
                },
            },
        },
        search_inventory,
    )


def register_lab_note_tool(registry: ToolRegistry, settings: Any) -> None:
    from infra_agent.tools.nextcloud import LabNoteClient, extract_sections

    client = LabNoteClient(settings)

    def read_lab_note(query: str | None = None) -> dict[str, Any]:
        """연구실 '개발서버 현황' 노트를 Nextcloud에서 읽어 관련 구간을 반환한다."""
        note = client.fetch()
        body = extract_sections(note.text, query or "")
        return {
            "source": "nextcloud",
            "path": note.path,
            "cached": note.cached,
            "query": query or "",
            "content": body,
        }

    registry.register(
        {
            "type": "function",
            "function": {
                "name": "read_lab_note",
                "description": (
                    "Nextcloud 옵시디언 노트 '개발서버 현황'을 조회한다. "
                    "판교/시흥 서버, 사무실 Wi-Fi, GitHub, Bookstack, AWS 접속 정보처럼 "
                    "연구실 위키에 있는 실제 현황을 물을 때 사용한다. "
                    "query에 키워드를 넣으면 관련 구간만 가져온다. "
                    "예: query='판교 wifi', query='시흥 서버', query='aws'."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "찾고 싶은 키워드. 비우면 노트 전체를 가져온다.",
                        }
                    },
                },
            },
        },
        read_lab_note,
    )


def _normalize_type(value: str | None) -> str:
    if not value:
        return ""
    text = value.strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "gpu": "gpu",
        "gpu_server": "gpu",
        "gpuserver": "gpu",
        "nas": "nas",
        "workstation": "workstation",
        "ws": "workstation",
    }
    return aliases.get(text, text)


def _type_matches(server_type: str, wanted: str) -> bool:
    if not wanted:
        return True
    st = server_type.strip().lower().replace("-", "_").replace(" ", "_")
    if not st:
        return False
    return wanted == st or st.startswith(f"{wanted}_") or wanted in st


def _server_summary(payload: dict[str, Any]) -> dict[str, Any]:
    network = payload.get("network") or {}
    gpu = payload.get("gpu") or []
    ssh = payload.get("ssh") or {}
    return {
        "id": payload.get("id"),
        "name": payload.get("name"),
        "aliases": payload.get("aliases") or [],
        "type": payload.get("type"),
        "ip": network.get("ip") if isinstance(network, dict) else None,
        "hostname": network.get("hostname") if isinstance(network, dict) else None,
        "ssh_port": ssh.get("port") if isinstance(ssh, dict) else None,
        "gpu": gpu,
        "status": payload.get("status"),
        "location": payload.get("location"),
    }


def _related_networks(store: InventoryStore, server: InventoryDoc) -> list[dict[str, Any]]:
    subnet = ""
    network = server.data.get("network") or {}
    if isinstance(network, dict):
        subnet = str(network.get("subnet") or "")
    related = []
    for doc in store.all("network"):
        members = doc.data.get("servers") or []
        cidr = str(doc.data.get("cidr") or "")
        if server.id in members or (subnet and cidr and subnet == cidr):
            related.append(
                {
                    "id": doc.id,
                    "name": doc.name,
                    "cidr": cidr,
                    "gateway": doc.data.get("gateway"),
                }
            )
    return related
