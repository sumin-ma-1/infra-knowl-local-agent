# Infra Knowledge Agent

로컬 LLM 기반 **Infrastructure Knowledge Agent**.

연구실 현황은 Nextcloud에 있는 옵시디언 노트(`개발서버 현황.md`)를 Tool로 조회합니다.
질문마다 WebDAV 전체를 훑지 않고, 해당 파일만 ETag로 받아 캐시합니다.

```text
User Query (Telegram / CLI / 웹)
    │
    ▼
Local LLM (Ollama)
    │
    └── read_lab_note(query)
            │
            ▼
     Nextcloud WebDAV
     개발서버 현황.md
            │
            ▼
      자연어 답변
```

## 현재 단계

| 단계 | 범위 | 상태 |
|------|------|------|
| 1 | Ollama + FastAPI + Tool Calling | 구현됨 |
| 1b | Telegram 봇 (질문 UI, 단체방 추가 가능) | 구현됨 |
| 2 | Nextcloud 단일 노트 (`read_lab_note`) | 구현됨 |
| 3 | Telegram **대화 검색** (과거 메시지 인덱스) | stub |
| 4 | Inventory write + 사용자 승인 | 미착수 |

SSH 실행 Tool은 넣지 않습니다.

## 요구 사항

- Python 3.10+
- [Ollama](https://ollama.com) — tool calling이 되는 모델 (기본: `qwen2.5:7b`)
- Nextcloud 앱 비밀번호, `개발서버 현황.md` 경로 (`.env`)

## 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

웹 UI:

```bash
uvicorn infra_agent.api:app --reload --host 127.0.0.1 --port 8001
```

CLI:

```bash
python -m infra_agent.cli "판교 사무실 wifi 알려줘"
```

## Telegram 봇

개인 채팅에서 질문하면 되고, 나중에 기존 단체방에 봇만 추가하면 됩니다.

단체방에서는 모든 메시지에 답하지 않습니다.

- `/ask 판교 사무실 wifi`
- `@봇이름 시흥 서버 SSH`
- 봇 답장에 이어서 질문 (reply)

1. [@BotFather](https://t.me/BotFather) 에서 `/newbot` → 토큰을 `.env` 의 `TELEGRAM_BOT_TOKEN` 에 넣기
2. `/setjoingroups` → Enable
3. `/setprivacy` → **Enable 유지**
4. 실행:

```bash
python -m infra_agent.telegram_bot
```

5. `/start` 로 `chat_id` 확인 후, 단체방 추가 전에 허용 목록 설정:

```bash
TELEGRAM_ALLOWED_CHAT_IDS=123456789,-1001234567890
```

## Tool

현재 런타임 Tool은 1개입니다.

1. `read_lab_note(query?)` — Nextcloud `개발서버 현황.md`

로컬 `inventory/*.md` 예시 데이터는 제거했습니다. 구조화 inventory 로더는 코드에 남아 있고, 파일이 있을 때만 Tool로 등록됩니다.

## 질문 예시

- 판교 사무실 wifi 알려줘
- 시흥 서버 SSH
- AWS 접속 정보
- Bookstack 주소
