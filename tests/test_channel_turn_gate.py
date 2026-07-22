from __future__ import annotations

from runtime.application.gateway.channel_turn_gate import (
    ChannelTurnGate,
    merge_channel_pending_jobs,
    reset_channel_turn_gate_for_tests,
)


def test_try_begin_enqueues_when_busy() -> None:
    gate = ChannelTurnGate()
    first = gate.try_begin("sess-a", {"user_text": "A"})
    assert first is not None
    second = gate.try_begin("sess-a", {"user_text": "B"})
    assert second is None
    assert gate.pending_count("sess-a") == 1
    third = gate.try_begin("sess-a", {"user_text": "C"})
    assert third is None
    assert gate.pending_count("sess-a") == 2


def test_end_and_take_merged_combines_pending() -> None:
    gate = ChannelTurnGate()
    first = gate.try_begin("sess-a", {"user_text": "A", "lang": "en"})
    assert first is not None
    assert gate.try_begin("sess-a", {"user_text": "B question", "lang": "en", "attachments": [{"n": 1}]}) is None
    assert gate.try_begin("sess-a", {"user_text": "C question", "lang": "en", "attachments": [{"n": 2}]}) is None

    merged, nxt = gate.end_and_take_merged(first)
    assert nxt is not None
    assert merged is not None
    assert int(merged.get("merged_count") or 0) == 2
    text = str(merged.get("user_text") or "")
    assert "B question" in text
    assert "C question" in text
    assert "follow-up" in text.lower() or "Several" in text
    assert len(merged.get("attachments") or []) == 2
    assert gate.pending_count("sess-a") == 0

    done, nxt2 = gate.end_and_take_merged(nxt)
    assert done is None and nxt2 is None


def test_merge_channel_pending_jobs_zh_header() -> None:
    merged = merge_channel_pending_jobs(
        [
            {"user_text": "光功率？", "lang": "zh"},
            {"user_text": "还有告警吗？", "lang": "zh"},
        ]
    )
    assert "一并回答" in str(merged.get("user_text") or "")
    assert "1) 光功率？" in str(merged.get("user_text") or "")
    assert "2) 还有告警吗？" in str(merged.get("user_text") or "")


def test_isolated_sessions_and_reset() -> None:
    g1 = reset_channel_turn_gate_for_tests()
    a = g1.try_begin("a", {"user_text": "1"})
    b = g1.try_begin("b", {"user_text": "2"})
    assert a is not None and b is not None
    g2 = reset_channel_turn_gate_for_tests()
    assert g1 is not g2
    assert g2.pending_count("a") == 0
