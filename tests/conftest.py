from pathlib import Path

import pytest

from infra_agent.inventory.store import InventoryStore


def _write(root: Path, rel: str, body: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def sample_inventory(tmp_path: Path) -> InventoryStore:
    _write(
        tmp_path,
        "servers/gpu01.md",
        """---
id: gpu-server-01
name: GPU Server 01
aliases:
  - gpu01
  - 5090 서버
type: gpu_server
network:
  hostname: gpu01.internal
  ip: 192.168.10.21
ssh:
  enabled: true
  port: 22022
  user: researcher
gpu:
  - model: NVIDIA RTX 5090
    count: 2
services:
  - name: ollama
    port: 11434
status: active
---

GPU inference server.
""",
    )
    _write(
        tmp_path,
        "servers/nas01.md",
        """---
id: nas01
name: NAS 01
aliases:
  - nas
type: nas
network:
  hostname: nas01.internal
  ip: 192.168.20.10
ssh:
  port: 22
  user: admin
---

Storage.
""",
    )
    _write(
        tmp_path,
        "networks/gpu-network.md",
        """---
id: gpu-network
name: GPU Network
cidr: 192.168.10.0/24
gateway: 192.168.10.1
servers:
  - gpu-server-01
---

GPU lab network.
""",
    )
    _write(
        tmp_path,
        "services/ollama.md",
        """---
id: ollama
name: Ollama
port: 11434
servers:
  - gpu-server-01
---

Local LLM runtime.
""",
    )
    return InventoryStore(tmp_path)


@pytest.fixture
def store(tmp_path: Path) -> InventoryStore:
    return sample_inventory(tmp_path)
