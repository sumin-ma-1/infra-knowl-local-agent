"""Phase 2 stub: Nextcloud WebDAV + local index + hybrid RAG.

Do not crawl WebDAV on every question. Sync incrementally by ETag/mtime,
then search the local index from search_nextcloud().
"""

from __future__ import annotations

from typing import Any


def search_nextcloud(query: str, limit: int = 5) -> dict[str, Any]:
    raise NotImplementedError("Nextcloud tool is planned for phase 2")


def read_nextcloud_file(path: str) -> dict[str, Any]:
    raise NotImplementedError("Nextcloud tool is planned for phase 2")
