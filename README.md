# Infra Knowledge Agent

로컬 LLM 기반 **Infrastructure Knowledge Agent**.

서버 IP, SSH 포트, GPU 모델처럼 정확해야 하는 값은 Vector RAG에 넣지 않습니다.
YAML front matter Markdown inventory를 메모리에 올리고, LLM이 Tool Calling으로 조회합니다.

```text
User Query
    │
    ▼
Local LLM (Ollama)
    │
    ├── list_servers
    ├── get_server
    └── search_inventory
            │
            ▼
     inventory/*.md
            │
            ▼
      자연어 답변
```

## 현재 단계: 1단계 MVP

| 단계 | 범위 | 상태 |
|------|------|------|
| 1 | MD Inventory + Ollama + FastAPI + Tool Calling | 구현됨 |
| 1b | Telegram 봇 (질문 UI, 단체방 추가 가능) | 구현됨 |
| 2 | Nextcloud WebDAV + 로컬 인덱스 + Hybrid RAG | stub |
| 3 | Telegram **대화 검색** (과거 메시지 인덱스) | stub |
| 4 | Inventory write + 사용자 승인 | 미착수 |

SSH 실행 Tool은 넣지 않습니다. 지식 조회와 서버 조작은 분리합니다.

## 요구 사항

- Python 3.10+
- [Ollama](https://ollama.com) — tool calling이 되는 모델
  - 기본값: `qwen2.5:7b`
  - 대안: `qwen3:14b`, `qwen3:32b`

## 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

웹 UI:

```bash
uvicorn infra_agent.api:app --reload --host 127.0.0.1 --port 8000
```

브라우저에서 `http://127.0.0.1:8000`

CLI:

```bash
python -m infra_agent.cli "GPU 서버 리스트 알려줘"
python -m infra_agent.cli
```

## Telegram 봇

웹 UI와 같은 Agent입니다. 개인 채팅에서 질문하면 되고, 나중에 기존 단체방에 봇만 추가하면 됩니다.

단체방에서는 모든 메시지에 답하지 않습니다.

- `/ask gpu01 SSH 포트 알려줘`
- `@봇이름 gpu01 SSH 포트 알려줘`
- 봇 답장에 이어서 질문 (reply)

1. [@BotFather](https://t.me/BotFather) 에서 `/newbot` → 토큰을 `.env` 의 `TELEGRAM_BOT_TOKEN` 에 넣기
2. `/setjoingroups` → Enable (단체방 초대 허용)
3. `/setprivacy` → **Enable 유지** (기본값). 꺼면 방의 모든 잡담을 봇이 보게 됩니다.
4. 실행:

```bash
python -m infra_agent.telegram_bot
```

5. 봇에게 `/start` → 표시되는 `chat_id` 를 복사
6. 단체방에 넣기 전에 `.env` 에 허용 채팅을 넣기:

```bash
TELEGRAM_ALLOWED_CHAT_IDS=123456789,-1001234567890
```

개인 `chat_id`는 양수, 단체방은 보통 `-100...` 음수입니다. 허용 목록이 비어 있으면 모든 채팅에 응답합니다.

봇은 **앞으로 오는 질문만** 답합니다. 기존 단체방의 과거 대화를 검색하는 기능은 Bot API로 불가능하고, 3단계(유저 클라이언트 인덱스)에서 다룹니다.

테스트:

```bash
pytest
```

## Inventory 형식

`inventory/servers/*.md` 는 YAML front matter + Markdown 설명입니다.

```md
---
id: gpu-server-01
name: GPU Server 01
aliases:
  - gpu01
type: gpu_server
network:
  hostname: gpu01.internal
  ip: 192.168.10.21
ssh:
  port: 22022
  user: researcher
gpu:
  - model: NVIDIA RTX 5090
    count: 2
---

# GPU Server 01

설명은 여기에.
```

네트워크는 `inventory/networks/`, 서비스는 `inventory/services/` 에 같은 형식으로 둡니다.

저장소에 들어 있는 서버 정보는 **예시 데이터**입니다. 실제 환경 값으로 바꾸면 됩니다. Markdown을 저장하면 다음 조회부터 자동으로 다시 읽습니다.

## Tool

MVP Tool은 3개입니다. 포트/GPU/IP마다 Tool을 쪼개지 않습니다. `get_server()`가 구조화 JSON을 반환하고, LLM이 필요한 필드만 답에 사용합니다.

1. `list_servers(type?)`
2. `get_server(server_name)`
3. `search_inventory(query)`

팩트 우선순위:

1. `inventory/*.md` (현재 등록값)
2. Nextcloud 공식 문서 (2단계)
3. Telegram 대화 (3단계, 논의일 뿐 현재값이 아님)

## 질문 예시

- GPU 서버 리스트 알려줘
- gpu01 IP 알려줘
- gpu01 SSH 포트 알려줘
- Ollama가 어디서 돌고 있어?
- 11434 쓰는 서버 알려줘
- gpu01은 어느 네트워크에 있어?
