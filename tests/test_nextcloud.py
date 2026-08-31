from infra_agent.tools.nextcloud import dav_file_url, extract_sections


def test_dav_url_encodes_space_and_emoji():
    url = dav_file_url(
        "http://cloud.example:9500",
        "keti",
        "KETI_OBSIDIAN/📁서버환경/개발서버 현황.md",
    )
    assert url.startswith("http://cloud.example:9500/remote.php/dav/files/keti/")
    assert " " not in url
    assert "%F0%9F%93%81" in url
    assert "%ED%98%84%ED%99%A9.md" in url or "현황" not in url


def test_extract_sections_keeps_matching_heading():
    md = """# 판교

wifi: abc

# 시흥

ssh: 22
"""
    out = extract_sections(md, "시흥 ssh")
    assert "시흥" in out
    assert "ssh: 22" in out
    assert "wifi: abc" not in out
