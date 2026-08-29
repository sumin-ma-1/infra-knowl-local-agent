from __future__ import annotations

from pathlib import Path

from infra_agent.inventory.models import InventoryDoc, Kind, parse_markdown

KIND_DIRS: dict[Kind, str] = {
    "server": "servers",
    "network": "networks",
    "service": "services",
}


class InventoryStore:
    """In-memory inventory. Reloads when Markdown files change."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.docs: dict[str, InventoryDoc] = {}
        self._signature: tuple[tuple[str, float, int], ...] = ()
        self.reload()

    def reload_if_stale(self) -> None:
        if self._scan_signature() != self._signature:
            self.reload()

    def reload(self) -> None:
        docs: dict[str, InventoryDoc] = {}
        for kind, dirname in KIND_DIRS.items():
            directory = self.root / dirname
            if not directory.is_dir():
                continue
            for path in sorted(directory.glob("*.md")):
                doc = parse_markdown(path, kind)
                docs[doc.id] = doc
        self.docs = docs
        self._signature = self._scan_signature()

    def _scan_signature(self) -> tuple[tuple[str, float, int], ...]:
        entries: list[tuple[str, float, int]] = []
        for dirname in KIND_DIRS.values():
            directory = self.root / dirname
            if not directory.is_dir():
                continue
            for path in directory.glob("*.md"):
                stat = path.stat()
                entries.append((str(path), stat.st_mtime, stat.st_size))
        return tuple(sorted(entries))

    def all(self, kind: Kind | None = None) -> list[InventoryDoc]:
        docs = list(self.docs.values())
        if kind:
            docs = [d for d in docs if d.kind == kind]
        return sorted(docs, key=lambda d: d.id)

    def get(self, key: str) -> InventoryDoc | None:
        if not key:
            return None
        needle = key.strip().lower()
        for doc in self.docs.values():
            if needle in doc.lookup_keys():
                return doc
        return None

    def search(self, query: str, limit: int = 8) -> list[tuple[InventoryDoc, float, list[str]]]:
        query = (query or "").strip()
        if not query:
            return []
        scored: list[tuple[InventoryDoc, float, list[str]]] = []
        for doc in self.docs.values():
            score, matched = _score(doc, query)
            if score > 0:
                scored.append((doc, score, matched))
        scored.sort(key=lambda item: (-item[1], item[0].id))
        return scored[:limit]


def _score(doc: InventoryDoc, query: str) -> tuple[float, list[str]]:
    q = query.lower()
    tokens = [t for t in _tokenize(q) if t]
    matched: list[str] = []
    score = 0.0

    keys = doc.lookup_keys()
    if q in keys:
        return 100.0, ["exact"]

    text = doc.searchable_text()
    if q and q in text:
        score += 20.0
        matched.append("phrase")

    for token in tokens:
        if token in keys:
            score += 15.0
            matched.append(f"key:{token}")
        elif token in text:
            score += 4.0
            matched.append(f"text:{token}")

    return score, matched


def _tokenize(query: str) -> list[str]:
    buf: list[str] = []
    current: list[str] = []
    for ch in query:
        if ch.isalnum() or ch in ".-_/":
            current.append(ch)
        else:
            if current:
                buf.append("".join(current))
                current = []
    if current:
        buf.append("".join(current))
    return buf
