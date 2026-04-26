from __future__ import annotations

import json
from pathlib import Path

from oclaw.platform.persistence.sqlite_store import SqliteStore
from oclaw.runtime.direct_loop import _build_model_context
from oclaw.platform.llm.chat_models import RuleBasedChatModel


def test_large_text_attachment_is_guarded_in_history_context(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "t.sqlite"))
    sess = store.create_session("t")
    big = "X" * 10000
    attachments = [{"type": "text", "name": "big.txt", "content": big}]
    store.add_message(session_id=sess.id, role="user", content="hi", attachments=attachments)

    msgs = _build_model_context(
        store=store,
        session_id=sess.id,
        max_messages=50,
        system_prompt="sys",
        model=RuleBasedChatModel(),
        lang="en",
        memory_context=None,
        trace_id=None,
        parent_span_id=None,
        tools=None,
        base_url="",
        user_text="",
        prompt_build_context=None,
        active_turn_uuid="different-turn",
    )
    # Ensure guard marker appears in injected context.
    joined = json.dumps(msgs, ensure_ascii=False)
    assert "Attachment (summarized for context replay)" in joined
    assert "attachment_truncated_for_context_replay" in joined


def test_text_attachment_is_collapsed_when_text_ref_present(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "t2.sqlite"))
    sess = store.create_session("t")
    big = "Y" * 6000
    attachments = [
        {"type": "text", "name": "doc.txt", "content": big},
        {"type": "text_ref", "name": "doc.txt", "text_id": "a" * 64, "chars": 6000, "chunks": 4, "source_kind": "txt"},
    ]
    store.add_message(session_id=sess.id, role="user", content="hi", attachments=attachments)

    msgs = _build_model_context(
        store=store,
        session_id=sess.id,
        max_messages=50,
        system_prompt="sys",
        model=RuleBasedChatModel(),
        lang="en",
        memory_context=None,
        trace_id=None,
        parent_span_id=None,
        tools=None,
        base_url="",
        user_text="",
        prompt_build_context=None,
        active_turn_uuid="different-turn",
    )
    joined = json.dumps(msgs, ensure_ascii=False)
    assert "Attachment (collapsed; text_ref available)" in joined
    assert "attachment_collapsed_for_context_replay" in joined


def test_large_image_tool_result_is_guarded_in_history_context(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "t3.sqlite"))
    sess = store.create_session("t")
    long_text = "OCR-LINE\n" * 1200
    payload = {
        "ok": True,
        "task": "ocr",
        "attachment_id": "b" * 64,
        "text": long_text,
        "backend_shape": "multi",
    }
    store.add_message(session_id=sess.id, role="tool", content=json.dumps(payload, ensure_ascii=False))

    msgs = _build_model_context(
        store=store,
        session_id=sess.id,
        max_messages=50,
        system_prompt="sys",
        model=RuleBasedChatModel(),
        lang="en",
        memory_context=None,
        trace_id=None,
        parent_span_id=None,
        tools=None,
        base_url="",
        user_text="",
        prompt_build_context=None,
        active_turn_uuid="different-turn",
    )
    joined = json.dumps(msgs, ensure_ascii=False)
    assert "image_tool_result_truncated_for_context_replay" in joined
    assert "_image_tool_result_guarded" in joined


def test_small_image_tool_result_not_guarded(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "t4.sqlite"))
    sess = store.create_session("t")
    payload = {
        "ok": True,
        "task": "describe",
        "attachment_id": "c" * 64,
        "text": "A concise description of an icon.",
    }
    store.add_message(session_id=sess.id, role="tool", content=json.dumps(payload, ensure_ascii=False))

    msgs = _build_model_context(
        store=store,
        session_id=sess.id,
        max_messages=50,
        system_prompt="sys",
        model=RuleBasedChatModel(),
        lang="en",
        memory_context=None,
        trace_id=None,
        parent_span_id=None,
        tools=None,
        base_url="",
        user_text="",
        prompt_build_context=None,
        active_turn_uuid="different-turn",
    )
    joined = json.dumps(msgs, ensure_ascii=False)
    assert "image_tool_result_truncated_for_context_replay" not in joined


def test_large_video_transcript_tool_result_is_guarded_in_history_context(tmp_path: Path) -> None:
    store = SqliteStore(str(tmp_path / "t5.sqlite"))
    sess = store.create_session("t")
    long_text = "LINE\n" * 2000
    payload = {
        "ok": True,
        "task": "transcript",
        "attachment_id": "d" * 64,
        "text": long_text,
    }
    store.add_message(session_id=sess.id, role="tool", content=json.dumps(payload, ensure_ascii=False))

    msgs = _build_model_context(
        store=store,
        session_id=sess.id,
        max_messages=50,
        system_prompt="sys",
        model=RuleBasedChatModel(),
        lang="en",
        memory_context=None,
        trace_id=None,
        parent_span_id=None,
        tools=None,
        base_url="",
        user_text="",
        prompt_build_context=None,
        active_turn_uuid="different-turn",
    )
    joined = json.dumps(msgs, ensure_ascii=False)
    assert "video_tool_result_truncated_for_context_replay" in joined

