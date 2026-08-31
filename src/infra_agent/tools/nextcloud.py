"""Fetch a single Nextcloud Markdown note over WebDAV, cached by ETag."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx

from infra_agent.config import ROOT_DIR, Settings

CACHE_PATH = ROOT_DIR / "data" / "lab-note-cache.json"


def dav_file_url(base_url: str, user: str, file_path: str) -> str:
    root = base_url.rstrip("/")
    if root.endswith("/remote.php/webdav"):
        prefix = root
    elif "/remote.php/dav/files/" in root:
        prefix = root
    else:
        prefix = f"{root}/remote.php/dav/files/{quote(user.strip(), safe='')}"
    rel = file_path.strip().lstrip("/")
    encoded = "/".join(quote(part, safe="") for part in rel.split("/") if part)
    return f"{prefix}/{encoded}"


def extract_sections(markdown: str, query: str, limit: int = 6) -> str:
    query = (query or "").strip()
    if not query:
        return markdown
    tokens = [t.lower() for t in re.findall(r"[\w./:-]+", query, flags=re.UNICODE) if len(t) > 1]
    if not tokens:
        return markdown
    chunks = _split_headings(markdown)
    scored: list[tuple[int, str]] = []
    for chunk in chunks:
        lower = chunk.lower()
        score = sum(lower.count(token) for token in tokens)
        if score:
            scored.append((score, chunk))
    scored.sort(key=lambda item: -item[0])
    if not scored:
        return markdown
    return "\n\n".join(chunk for _, chunk in scored[:limit])


def _split_headings(markdown: str) -> list[str]:
    parts: list[str] = []
    current: list[str] = []
    for line in markdown.splitlines():
        if line.startswith("#") and current:
            parts.append("\n".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        parts.append("\n".join(current).strip())
    return [p for p in parts if p]


@dataclass
class NoteFetch:
    text: str
    etag: str
    cached: bool
    path: str
    bytes_len: int


class LabNoteClient:
    def __init__(self, settings: Settings, cache_path: Path = CACHE_PATH) -> None:
        self.settings = settings
        self.cache_path = cache_path
        self.url = dav_file_url(
            settings.nextcloud_url,
            settings.nextcloud_user,
            settings.nextcloud_file_path,
        )

    def fetch(self) -> NoteFetch:
        cached = _read_cache(self.cache_path)
        headers = {"Accept": "text/markdown, text/plain, */*"}
        if cached.get("etag") and cached.get("path") == self.settings.nextcloud_file_path:
            headers["If-None-Match"] = cached["etag"]
        try:
            with httpx.Client(timeout=30.0, follow_redirects=True) as client:
                response = client.get(
                    self.url,
                    auth=(self.settings.nextcloud_user, self.settings.nextcloud_app_password),
                    headers=headers,
                )
        except httpx.HTTPError as exc:
            if cached.get("text"):
                return NoteFetch(
                    text=str(cached["text"]),
                    etag=str(cached.get("etag") or ""),
                    cached=True,
                    path=self.settings.nextcloud_file_path,
                    bytes_len=len(str(cached["text"])),
                )
            raise RuntimeError(f"Nextcloud에 연결하지 못했습니다: {exc}") from exc

        if response.status_code == 304 and cached.get("text"):
            return NoteFetch(
                text=str(cached["text"]),
                etag=str(cached.get("etag") or ""),
                cached=True,
                path=self.settings.nextcloud_file_path,
                bytes_len=len(str(cached["text"])),
            )
        if response.status_code == 401:
            raise RuntimeError("Nextcloud 인증 실패. 앱 비밀번호와 아이디를 확인하세요.")
        if response.status_code == 404:
            raise RuntimeError(
                f"Nextcloud에서 파일을 찾지 못했습니다: {self.settings.nextcloud_file_path}"
            )
        if response.status_code >= 400:
            raise RuntimeError(f"Nextcloud HTTP {response.status_code}")

        text = response.content.decode("utf-8-sig")
        etag = (response.headers.get("etag") or "").strip()
        _write_cache(
            self.cache_path,
            {
                "etag": etag,
                "text": text,
                "path": self.settings.nextcloud_file_path,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        return NoteFetch(
            text=text,
            etag=etag,
            cached=False,
            path=self.settings.nextcloud_file_path,
            bytes_len=len(text),
        )


def _read_cache(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_cache(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
