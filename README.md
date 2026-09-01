# Infra Knowledge Agent

로컬 LLM 기반 **Infrastructure Knowledge Agent**.

연구실 현황은 Nextcloud에 있는 옵시디언 노트(`개발서버 현황.md`)를 Tool로 조회합니다.
질문마다 WebDAV 전체를 훑지 않고, 해당 파일만 ETag로 받아 캐시합니다.

```text
User Query (Telegram / CLI)
    │
    ▼
Local LLM (Ollama)
    ├── read_lab_note(query)     → Nextcloud 개발서버 현황.md
    └── search_telegram(query)   → 로컬 SQLite (Telethon이 단체방 히스토리를 채워 둠)
            │
            ▼
      자연어 답변
```

## 현재 단계

| 단계 | 범위 | 상태 |
|------|------|------|
| 1 | Ollama + CLI + Tool Calling | 구현됨 |
| 1b | Telegram 봇 (질문 UI, 단체방 추가 가능) | 구현됨 |
| 2 | Nextcloud 단일 노트 (`read_lab_note`) | 구현됨 |
| 3 | Telegram **대화 검색** (과거 메시지 인덱스) | 구현됨 |
| 4 | Inventory write + 사용자 승인 | 미착수 |

SSH 실행 Tool은 넣지 않습니다.

## 요구 사항

- Python 3.10+
- [Ollama](https://ollama.com) — tool calling이 되는 모델 (기본: `gemma4:e4b`)
- Nextcloud 앱 비밀번호, `개발서버 현황.md` 경로 (`.env`)

## 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
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

## 단체방 히스토리 인덱스

봇은 예전 단체방 글을 읽을 수 없습니다. **본인 텔레그램 계정**(Telethon)으로 `TELEGRAM_INDEX_CHATS`에 넣은 방을 가져와 로컬 SQLite에 저장합니다. 에이전트는 `search_telegram`으로 그 인덱스를 검색합니다.

계정은 해당 방의 **멤버**여야 합니다. 봇만 초대해 둔 것만으로는 부족합니다.

1. [my.telegram.org](https://my.telegram.org) → API development tools → `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`
2. `.env`에 `TELEGRAM_PHONE`, `TELEGRAM_INDEX_CHATS` (단체방 `chat_id`, 콤마 구분, 그룹은 음수)
3. **이 서버 터미널에서** 최초 1회 로그인 (휴대폰으로 온 코드를 입력):

```bash
python -m infra_agent.telegram_index login
python -m infra_agent.telegram_index sync
python -m infra_agent.telegram_index status
```

세션 파일은 `data/telegram-user.session`, 인덱스는 `data/telegram-index.sqlite` 입니다. git에 넣지 마세요.

봇이 떠 있고 로그인이 되어 있으면, 시작 때 빠진 글을 채운 뒤 **등록된 방에 새 글이 올 때마다** 인덱스에 넣습니다. 다른 방·개인 채팅은 보지 않습니다. 로그인 뒤에 봇을 재시작하면 수신을 시작합니다.

봇이 실시간 수신 중일 때는 같은 세션으로 `sync`/`login`을 동시에 돌리지 마세요. 세션 파일이 잠길 수 있습니다.

`TELEGRAM_INDEX_CHATS`에서 방을 빼면, 다음 봇 시작(또는 수동 `sync`) 때 그 방의 로컬 기록도 함께 지웁니다. `.env`를 바꾼 뒤에는 봇을 재시작하세요. 당장 지우려면:

```bash
python -m infra_agent.telegram_index drop --chat-id -5141393598
```

## Tool

현재 런타임 Tool은 질문 종류에 따라 등록됩니다.

1. `read_lab_note(query?)` — Nextcloud `개발서버 현황.md`
2. `search_telegram(query, chat_id?)` — 인덱싱된 단체방 과거 대화
3. `get_recent_messages(chat_id?, limit?)` — 인덱싱된 방의 최근 메시지

로컬 `inventory/*.md` 예시 데이터는 제거했습니다. 구조화 inventory 로더는 코드에 남아 있고, 파일이 있을 때만 Tool로 등록됩니다.

## 질문 예시

- 판교 사무실 wifi 알려줘
- 시흥 서버 SSH
- AWS 접속 정보
- Bookstack 주소
