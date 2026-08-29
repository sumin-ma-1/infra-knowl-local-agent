from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Kind = Literal["server", "network", "service"]


class InventoryDoc(BaseModel):
    """One Markdown inventory record (YAML front matter + body)."""

    model_config = ConfigDict(extra="allow")

    kind: Kind
    path: str
    id: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    notes: str = ""
    data: dict[str, Any] = Field(default_factory=dict)

    def searchable_text(self) -> str:
        parts: list[str] = [self.id, self.name, *self.aliases, self.notes]
        parts.append(_flatten(self.data))
        return " ".join(p for p in parts if p).lower()

    def lookup_keys(self) -> set[str]:
        keys = {self.id.lower(), self.name.lower()}
        keys.update(a.lower() for a in self.aliases)
        data = self.data
        hostname = _nested_get(data, "network", "hostname") or data.get("hostname")
        ip = _nested_get(data, "network", "ip") or data.get("ip")
        for value in (hostname, ip):
            if isinstance(value, str) and value:
                keys.add(value.lower())
        return {k for k in keys if k}

    def public_dict(self) -> dict[str, Any]:
        payload = {
            "kind": self.kind,
            "id": self.id,
            "name": self.name,
            "aliases": self.aliases,
            **self.data,
            "notes": self.notes,
        }
        return payload


def _nested_get(data: dict[str, Any], *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _flatten(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(v) for v in value)
    return str(value)


def parse_markdown(path: Path, kind: Kind) -> InventoryDoc:
    text = path.read_text(encoding="utf-8")
    meta, notes = split_front_matter(text)
    if not isinstance(meta, dict):
        meta = {}

    doc_id = str(meta.pop("id", path.stem))
    name = str(meta.pop("name", doc_id))
    aliases = meta.pop("aliases", [])
    if isinstance(aliases, str):
        aliases = [aliases]
    if not isinstance(aliases, list):
        aliases = []
    aliases = [str(a) for a in aliases]

    return InventoryDoc(
        kind=kind,
        path=str(path),
        id=doc_id,
        name=name,
        aliases=aliases,
        notes=notes.strip(),
        data=meta,
    )


def split_front_matter(text: str) -> tuple[dict[str, Any], str]:
    import yaml

    stripped = text.lstrip("\ufeff")
    if not stripped.startswith("---"):
        return {}, stripped

    rest = stripped[3:]
    if rest.startswith("\n"):
        rest = rest[1:]
    end = rest.find("\n---")
    if end < 0:
        return {}, stripped
    raw_yaml = rest[:end]
    body = rest[end + 4 :]
    if body.startswith("\n"):
        body = body[1:]
    loaded = yaml.safe_load(raw_yaml) or {}
    if not isinstance(loaded, dict):
        loaded = {}
    return loaded, body
