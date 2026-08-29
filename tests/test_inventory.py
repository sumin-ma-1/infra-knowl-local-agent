from infra_agent.inventory.models import parse_markdown
from infra_agent.tools.inventory_tools import build_registry


def test_parse_front_matter_and_aliases(store):
    doc = store.get("gpu01")
    assert doc is not None
    assert doc.id == "gpu-server-01"
    assert "5090 서버" in doc.aliases
    assert doc.data["ssh"]["port"] == 22022


def test_lookup_by_ip_and_hostname(store):
    assert store.get("192.168.10.21").id == "gpu-server-01"
    assert store.get("gpu01.internal").id == "gpu-server-01"


def test_search_by_port_and_gpu(store):
    port_hits = store.search("11434")
    assert any(d.id in {"gpu-server-01", "ollama"} for d, _, _ in port_hits)
    gpu_hits = store.search("5090")
    assert gpu_hits[0][0].id == "gpu-server-01"


def test_list_servers_type_filter(store):
    tools = build_registry(store)
    gpu = tools.call("list_servers", {"type": "gpu"})
    nas = tools.call("list_servers", {"type": "nas"})
    assert "gpu-server-01" in gpu
    assert "nas01" not in gpu
    assert "nas01" in nas


def test_get_server_and_search_tools(store):
    tools = build_registry(store)
    detail = tools.call("get_server", {"server_name": "gpu01"})
    assert "22022" in detail
    assert "11434" in detail
    found = tools.call("search_inventory", {"query": "192.168.10.0/24"})
    assert "gpu-network" in found
    assert "gpu-network" in detail


def test_parse_without_front_matter(tmp_path):
    path = tmp_path / "plain.md"
    path.write_text("# Hello\n\nworld\n", encoding="utf-8")
    doc = parse_markdown(path, "server")
    assert doc.id == "plain"
    assert "world" in doc.notes
