from __future__ import annotations

from dataclasses import dataclass

from runtime.application.gateway.inbound_service import (
    _collect_reply_attachments_from_history,
    _collect_recent_tool_attachments,
    _get_channel_dispatch_setting,
    _latest_user_turn_uuid,
    _maybe_add_media_path_for_wechat_reply,
    _maybe_expand_reply_attachments_for_channel,
    _parse_message_attachments,
    _persist_channel_assistant_if_turn_missing,
    _resolve_channel_dispatch,
    _should_suppress_channel_reply,
    _user_facing_wechat_reply,
)


def test_should_suppress_weixin_openai_missing_api_key_message() -> None:
    text = '⚠️ Missing API key for provider "openai". Configure the gateway auth for that provider, then try again.'
    assert _should_suppress_channel_reply(channel="wechat", text=text) is True
    assert _should_suppress_channel_reply(channel="weixin", text=text) is True


def test_should_not_suppress_non_weixin_channel() -> None:
    text = '⚠️ Missing API key for provider "openai". Configure the gateway auth for that provider, then try again.'
    assert _should_suppress_channel_reply(channel="admin_chat", text=text) is False


def test_user_facing_wechat_reply_maps_empty_and_api_key_errors() -> None:
    assert _user_facing_wechat_reply(reply="") == "暂时无法回复，请稍后再试。"
    assert "API" in _user_facing_wechat_reply(
        reply='Missing API key for provider "openai". Configure the gateway auth for that provider.'
    )
    assert _user_facing_wechat_reply(reply="你好") == "你好"


def test_persist_channel_assistant_if_turn_missing_inserts_once() -> None:
    class _Msg:
        def __init__(self, role: str, turn_uuid: str) -> None:
            self.role = role
            self.turn_uuid = turn_uuid

    class _Store:
        def __init__(self) -> None:
            self.rows: list[_Msg] = [_Msg("user", "turn-1")]
            self.added: list[tuple[str, str, str]] = []

        def get_messages(self, *, session_id: str, limit: int = 80) -> list[_Msg]:
            _ = (session_id, limit)
            return list(self.rows)

        def add_message(self, **kwargs: object) -> None:
            self.added.append(
                (
                    str(kwargs.get("session_id") or ""),
                    str(kwargs.get("turn_uuid") or ""),
                    str(kwargs.get("content") or ""),
                )
            )
            self.rows.append(_Msg("assistant", str(kwargs.get("turn_uuid") or "")))

    store = _Store()
    _persist_channel_assistant_if_turn_missing(
        store=store,
        session_id="s1",
        turn_uuid="",
        final_text="暂时无法回复，请稍后再试。",
    )
    assert len(store.added) == 1
    assert store.added[0] == ("s1", "turn-1", "暂时无法回复，请稍后再试。")
    _persist_channel_assistant_if_turn_missing(
        store=store,
        session_id="s1",
        turn_uuid="turn-1",
        final_text="暂时无法回复，请稍后再试。",
    )
    assert len(store.added) == 1


def test_latest_user_turn_uuid() -> None:
    class _Msg:
        def __init__(self, role: str, turn_uuid: str) -> None:
            self.role = role
            self.turn_uuid = turn_uuid

    class _Store:
        def get_messages(self, *, session_id: str, limit: int = 80) -> list[_Msg]:
            _ = (session_id, limit)
            return [_Msg("assistant", "a1"), _Msg("user", "u2")]

    assert _latest_user_turn_uuid(_Store(), session_id="s") == "u2"


def test_channel_dispatch_wechat_reads_weixin_settings() -> None:
    class _Store:
        def get_setting(self, key: str) -> str:
            data = {
                "channel.dispatch.interaction_mode.weixin": "comprehensive",
                "channel.dispatch.specialist.weixin": "ops",
                "channel.dispatch.lang.weixin": "zh",
            }
            return str(data.get(key) or "")

    mode, spec, lang = _resolve_channel_dispatch(_Store(), channel="wechat", account=None)
    assert mode == "comprehensive"
    assert spec == "ops"
    assert lang == "zh"
    assert _get_channel_dispatch_setting(_Store(), "channel.dispatch.specialist.", "wechat") == "ops"


def test_parse_message_attachments_accepts_json_string() -> None:
    out = _parse_message_attachments('[{"type":"image_ref","attachment_id":"a1"}]')
    assert len(out) == 1
    assert out[0].get("attachment_id") == "a1"


@dataclass
class _Row:
    role: str
    content: str
    attachments: object


class _FakeStore:
    def __init__(self, rows: list[_Row]) -> None:
        self._rows = rows

    def get_messages(self, *, session_id: str, limit: int = 120) -> list[_Row]:
        _ = (session_id, limit)
        return list(self._rows)


def test_collect_reply_attachments_prefers_matching_assistant_text() -> None:
    rows = [
        _Row(role="assistant", content="old", attachments='[{"attachment_id":"old"}]'),
        _Row(role="assistant", content="target", attachments='[{"attachment_id":"new"}]'),
    ]
    out = _collect_reply_attachments_from_history(store=_FakeStore(rows), session_id="s1", reply_text="target")
    assert len(out) == 1
    assert out[0].get("attachment_id") == "new"


def test_collect_reply_attachments_does_not_reuse_stale_images_on_text_only_reply() -> None:
    rows = [
        _Row(role="assistant", content="here is a chart", attachments='[{"attachment_id":"old"}]'),
        _Row(role="assistant", content="ok", attachments=None),
    ]
    out = _collect_reply_attachments_from_history(store=_FakeStore(rows), session_id="s1", reply_text="ok")
    assert out == []


def test_collect_recent_tool_attachments_ignores_undeliverable_image_ref() -> None:
    rows = [
        _Row(role="user", content="draw", attachments=None),
        _Row(role="tool", content="{}", attachments='[{"type":"image_ref","attachment_id":"a1"}]'),
        _Row(role="assistant", content="x", attachments=None),
    ]
    out = _collect_recent_tool_attachments(store=_FakeStore(rows), session_id="s1")
    assert out == []


def test_collect_recent_tool_attachments_includes_deliverable_image_ref() -> None:
    rows = [
        _Row(role="user", content="draw", attachments=None),
        _Row(
            role="tool",
            content="{}",
            attachments='[{"type":"image_ref","attachment_id":"a1","mime":"image/png","deliverable":true}]',
        ),
        _Row(role="assistant", content="x", attachments=None),
    ]
    out = _collect_recent_tool_attachments(store=_FakeStore(rows), session_id="s1")
    assert len(out) == 1
    assert out[0].get("attachment_id") == "a1"
    assert out[0].get("deliverable") is True


def test_collect_recent_tool_attachments_ignores_media_from_prior_turn() -> None:
    rows = [
        _Row(role="user", content="old question", attachments=None),
        _Row(role="tool", content="{}", attachments='[{"type":"image_ref","attachment_id":"stale"}]'),
        _Row(role="assistant", content="old answer", attachments=None),
        _Row(role="user", content="new question", attachments=None),
        _Row(role="assistant", content="new answer", attachments=None),
    ]
    out = _collect_recent_tool_attachments(store=_FakeStore(rows), session_id="s1")
    assert out == []


def test_collect_recent_tool_attachments_ignores_text_ref_from_lookup_tools() -> None:
    rows = [
        _Row(role="user", content="analyze file", attachments=None),
        _Row(
            role="tool",
            content="{}",
            attachments='[{"type":"text_ref","attachment_id":"user-upload","name":"Site_List.txt","mime":"text/plain"}]',
        ),
        _Row(role="assistant", content="15,687 rows", attachments=None),
    ]
    out = _collect_recent_tool_attachments(store=_FakeStore(rows), session_id="s1")
    assert out == []


def test_collect_recent_tool_attachments_includes_deliverable_binary_ref() -> None:
    rows = [
        _Row(role="user", content="export", attachments=None),
        _Row(
            role="tool",
            content="{}",
            attachments='[{"type":"binary_ref","attachment_id":"gen-xlsx","name":"report.xlsx","mime":"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet","deliverable":true}]',
        ),
        _Row(role="assistant", content="done", attachments=None),
    ]
    out = _collect_recent_tool_attachments(store=_FakeStore(rows), session_id="s1")
    assert len(out) == 1
    assert out[0].get("attachment_id") == "gen-xlsx"
    assert out[0].get("deliverable") is True


def test_collect_recent_tool_attachments_includes_deliverable_text_ref() -> None:
    rows = [
        _Row(role="user", content="export", attachments=None),
        _Row(
            role="tool",
            content="{}",
            attachments='[{"type":"text_ref","attachment_id":"gen-txt","name":"out.txt","mime":"text/plain","deliverable":true}]',
        ),
        _Row(role="assistant", content="done", attachments=None),
    ]
    out = _collect_recent_tool_attachments(store=_FakeStore(rows), session_id="s1")
    assert len(out) == 1
    assert out[0].get("attachment_id") == "gen-txt"


def test_maybe_add_media_path_for_wechat_reply_sets_media_path(monkeypatch) -> None:
    # Avoid touching disk: stub AttachmentAssetStore.get_local_path.
    from pathlib import Path

    def _fake_get_local_path(self, attachment_id: str):  # noqa: ANN001
        assert attachment_id == "a1"
        return Path("D:/tmp/fake.png")

    monkeypatch.setattr(
        "svc.files.attachment_assets.AttachmentAssetStore.get_local_path",
        _fake_get_local_path,
    )
    r = {"channel": "wechat", "text": "hi", "attachments": [{"type": "image_ref", "attachment_id": "a1"}]}
    _maybe_add_media_path_for_wechat_reply(r)
    assert r.get("media_path") in {"D:/tmp/fake.png", "D:\\tmp\\fake.png"}


def test_maybe_expand_reply_attachments_for_channel_converts_ref_to_base64(monkeypatch) -> None:
    import base64

    class _Meta:
        mime = "image/png"
        name = "x.png"

    def _fake_load_bytes(self, attachment_id: str):  # noqa: ANN001
        assert attachment_id == "a1"
        return b"abc", _Meta()

    monkeypatch.setattr(
        "svc.files.attachment_assets.AttachmentAssetStore.load_bytes",
        _fake_load_bytes,
    )
    r = {"channel": "wechat", "attachments": [{"type": "image_ref", "attachment_id": "a1"}]}
    _maybe_expand_reply_attachments_for_channel(r)
    out = r.get("attachments")
    assert isinstance(out, list) and len(out) == 1
    assert out[0].get("data_base64") == base64.b64encode(b"abc").decode("ascii")
    assert out[0].get("mime") == "image/png"


def test_maybe_expand_reply_attachments_for_channel_works_for_whatsapp(monkeypatch) -> None:
    import base64

    class _Meta:
        mime = "image/png"
        name = "wa.png"

    def _fake_load_bytes(self, attachment_id: str):  # noqa: ANN001
        assert attachment_id == "wa1"
        return b"wa", _Meta()

    monkeypatch.setattr(
        "svc.files.attachment_assets.AttachmentAssetStore.load_bytes",
        _fake_load_bytes,
    )
    r = {"channel": "whatsapp", "attachments": [{"type": "image_ref", "attachment_id": "wa1"}]}
    _maybe_expand_reply_attachments_for_channel(r)
    out = r.get("attachments")
    assert isinstance(out, list) and len(out) == 1
    assert out[0].get("data_base64") == base64.b64encode(b"wa").decode("ascii")


def test_maybe_expand_deliverable_xlsx_for_weixin_channel(monkeypatch) -> None:
    import base64

    class _Meta:
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        name = "report.xlsx"

    def _fake_load_bytes(self, attachment_id: str):  # noqa: ANN001
        assert attachment_id == "x1"
        return b"xlsx-bytes", _Meta()

    monkeypatch.setattr(
        "svc.files.attachment_assets.AttachmentAssetStore.load_bytes",
        _fake_load_bytes,
    )
    r = {
        "channel": "weixin",
        "attachments": [
            {
                "type": "binary_ref",
                "attachment_id": "x1",
                "name": "report.xlsx",
                "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "deliverable": True,
            }
        ],
    }
    _maybe_expand_reply_attachments_for_channel(r)
    out = r.get("attachments")
    assert isinstance(out, list) and len(out) == 1
    assert out[0].get("data_base64") == base64.b64encode(b"xlsx-bytes").decode("ascii")
    assert out[0].get("name") == "report.xlsx"

