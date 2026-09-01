from infra_agent.telegram_format import to_telegram_html


def test_bold_and_code_become_html():
    out = to_telegram_html("서버는 **gpu01** 이고 포트는 `22022`")
    assert "<b>gpu01</b>" in out
    assert "<code>22022</code>" in out
    assert "**" not in out


def test_html_special_chars_escaped():
    out = to_telegram_html("A < B & C")
    assert "&lt;" in out
    assert "&amp;" in out
