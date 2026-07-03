from __future__ import annotations

from types import SimpleNamespace

import pytest

from runtime.application.gateway.inbound_service import _channel_attachments_for_gateway
from runtime.chat.agent_messages import build_llm_messages
from svc.files.attachment_assets import AttachmentAssetStore
from svc.files.file_attachments import expand_attachment_ref
from svc.llm.chat_models import RuleBasedChatModel


@pytest.fixture
def att_store(tmp_path, monkeypatch):
    store = AttachmentAssetStore(root_dir=tmp_path / "att")

    def _factory(root_dir=None):
        if root_dir is None:
            return store
        return AttachmentAssetStore(root_dir=root_dir)

    monkeypatch.setattr("svc.files.file_attachments.AttachmentAssetStore", _factory)
    monkeypatch.setattr("runtime.chat.agent_messages.AttachmentAssetStore", _factory)
    return store


def _msg_text(message: dict) -> str:
    content = message.get("content")
    if isinstance(content, list):
        return "\n".join(str(x.get("text") or "") for x in content if isinstance(x, dict))
    return str(content or "")


def test_expand_attachment_ref_large_txt_becomes_text_ref(att_store) -> None:
    text = ("line\n" * 5000).strip()
    data = text.encode("utf-8")
    meta = att_store.save_bytes(data, filename="sites.txt", mime="text/plain")
    got = expand_attachment_ref({"type": "binary_ref", "attachment_id": meta.attachment_id})
    types = {str(x.get("type") or "") for x in got}
    assert "text_ref" in types
    assert "text" in types


def test_channel_attachments_for_gateway_parses_local_txt(tmp_path) -> None:
    p = tmp_path / "Site_List.txt"
    p.write_text("a\nb\nc\n", encoding="utf-8")
    got = _channel_attachments_for_gateway([{"local_path": str(p), "kind": "document", "mime": "text/plain"}])
    assert got
    assert any(str(x.get("type") or "") == "text" for x in got)


def test_build_llm_messages_binary_ref_meta_for_historical_turn(att_store) -> None:
    data = b"hello attachment"
    meta = att_store.save_bytes(data, filename="note.txt", mime="text/plain")
    rows = [
        SimpleNamespace(
            role="user",
            event_type="user_text",
            content="first",
            attachments=[{"type": "binary_ref", "attachment_id": meta.attachment_id}],
            tool_calls=None,
            turn_uuid="t1",
        ),
        SimpleNamespace(
            role="user",
            event_type="user_text",
            content="second",
            attachments=None,
            tool_calls=None,
            turn_uuid="t2",
        ),
    ]
    msgs = build_llm_messages(store_messages=rows, system_prompt="s", model=RuleBasedChatModel(), lang="zh")
    first_user = next(m for m in msgs if m.get("role") == "user" and "first" in _msg_text(m))
    content = _msg_text(first_user)
    assert "BinaryAttachment" in content
    assert meta.attachment_id in content


def test_build_llm_messages_binary_ref_expands_on_last_turn(att_store) -> None:
    text = ("row\n" * 4000).strip()
    data = text.encode("utf-8")
    meta = att_store.save_bytes(data, filename="Site_List.txt", mime="text/plain")
    rows = [
        SimpleNamespace(
            role="user",
            event_type="user_text",
            content="帮看一下有多少数据",
            attachments=[{"type": "binary_ref", "attachment_id": meta.attachment_id}],
            tool_calls=None,
            turn_uuid="t1",
        ),
    ]
    msgs = build_llm_messages(store_messages=rows, system_prompt="s", model=RuleBasedChatModel(), lang="zh")
    user = msgs[-1]
    content = _msg_text(user)
    assert "LongTextAttachment" in content or "text_id" in content
