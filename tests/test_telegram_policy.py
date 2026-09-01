from infra_agent.telegram_policy import (
    chat_allowed,
    extract_ask_command,
    extract_mention_question,
    group_question,
    parse_allowed_chat_ids,
    parse_id_list,
)


def test_parse_allowed_chat_ids():
    assert parse_allowed_chat_ids("") is None
    assert parse_allowed_chat_ids("  ") is None
    assert parse_allowed_chat_ids("-1001, 42") == frozenset({-1001, 42})
    assert parse_id_list("-5141393598, -5502317810     # 방 이름") == [
        -5141393598,
        -5502317810,
    ]


def test_chat_allowed():
    assert chat_allowed(1, None) is True
    assert chat_allowed(1, frozenset({1, 2})) is True
    assert chat_allowed(3, frozenset({1, 2})) is False


def test_extract_ask_command():
    assert extract_ask_command("/ask gpu01 SSH") == "gpu01 SSH"
    assert extract_ask_command("/ask@infra_bot gpu01 SSH") == "gpu01 SSH"
    assert extract_ask_command("/ask") == ""
    assert extract_ask_command("gpu01 SSH") is None


def test_group_question_requires_address():
    assert group_question("잡담입니다", bot_username="infra_bot", is_reply_to_bot=False) is None
    assert (
        group_question(
            "@infra_bot gpu01 SSH 포트",
            bot_username="infra_bot",
            is_reply_to_bot=False,
        )
        == "gpu01 SSH 포트"
    )
    assert (
        group_question("/ask gpu01 IP", bot_username="infra_bot", is_reply_to_bot=False)
        == "gpu01 IP"
    )
    assert (
        group_question("그 서버 GPU는?", bot_username="infra_bot", is_reply_to_bot=True)
        == "그 서버 GPU는?"
    )


def test_mention_is_case_insensitive():
    q = extract_mention_question("안녕 @Infra_Bot 포트 알려줘", "infra_bot")
    assert q == "안녕 포트 알려줘"
