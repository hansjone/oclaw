from __future__ import annotations

from runtime.session_auto_title import AUTO_TITLE_CHAR_MAX, finalize_auto_title, should_reject_auto_title


def test_should_reject_long_prose() -> None:
    blob = "您好！我是 Claude Code，一个软件工程助手。" + "x" * 80
    assert should_reject_auto_title(blob) is True


def test_should_reject_claude_code_intro() -> None:
    assert should_reject_auto_title("Hello! I am Claude Code, a software engineering assistant.") is True


def test_should_accept_short_title() -> None:
    assert should_reject_auto_title("告警查询配置") is False


def test_finalize_truncates_fallback() -> None:
    long_fb = "一二三四五六七八九十11121314151617181920"
    out = finalize_auto_title(raw="x" * 100, fallback=long_fb)
    assert len(out) == AUTO_TITLE_CHAR_MAX
    assert out == long_fb[:AUTO_TITLE_CHAR_MAX]


def test_finalize_uses_model_when_sane() -> None:
    assert finalize_auto_title(raw="  网管同步  ", fallback="fallback") == "网管同步"
