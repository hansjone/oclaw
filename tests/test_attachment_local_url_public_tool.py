from __future__ import annotations

from pathlib import Path

from runtime.tools.public.attachment_local_url_tool import attachment_local_url_tool


class _FakeMeta:
    mime = "image/png"
    name = "cat.png"
    bytes = 123


class _FakeStore:
    def get_meta(self, attachment_id: str) -> _FakeMeta | None:
        if attachment_id.startswith("a"):
            return _FakeMeta()
        return None

    def get_local_path(self, attachment_id: str) -> Path | None:
        if attachment_id.startswith("a"):
            return Path("D:/project/chatgpt/oclaw/data/attachments/aa/bb/cat.png")
        return None


def test_attachment_local_url_rejects_invalid_id() -> None:
    spec = attachment_local_url_tool()
    out = spec.handler({"attachment_id": "bad-id"})
    assert out.get("ok") is False
    assert out.get("error") == "attachment_id_invalid"


def test_attachment_local_url_builds_absolute_url(monkeypatch) -> None:
    monkeypatch.setattr("runtime.tools.public.attachment_local_url_tool.AttachmentAssetStore", _FakeStore)
    spec = attachment_local_url_tool()
    aid = "a" * 64
    out = spec.handler({"attachment_id": aid})
    assert out.get("ok") is True
    assert str(out.get("file_url") or "").startswith("file:///")
    assert out.get("mime") == "image/png"
    assert "exists" not in out
    assert "local_path" not in out
    assert "preferred_url" not in out


def test_attachment_local_url_verbose_includes_debug_fields(monkeypatch) -> None:
    monkeypatch.setattr("runtime.tools.public.attachment_local_url_tool.AttachmentAssetStore", _FakeStore)
    spec = attachment_local_url_tool()
    aid = "a" * 64
    out = spec.handler({"attachment_id": aid, "verbose": True})
    assert out.get("ok") is True
    assert out.get("exists") is True
    assert str(out.get("local_path") or "").endswith("cat.png")
    assert out.get("preferred_url") == out.get("file_url")


def test_attachment_local_url_is_visible_in_public_registry() -> None:
    from runtime.tools.catalog import default_registry

    names = [t.name for t in default_registry(expert="network_ops+memory", specialist="ops").list()]
    assert "attachment_local_url" in names
