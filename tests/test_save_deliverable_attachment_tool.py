from __future__ import annotations

from runtime.tools.public.save_deliverable_attachment_tool import save_deliverable_attachment_tool


def test_save_deliverable_attachment_registers_file(tmp_path, monkeypatch) -> None:
    from svc.files.attachment_assets import AttachmentAssetStore

    store = AttachmentAssetStore(root_dir=tmp_path / "att")
    monkeypatch.setattr(
        "runtime.tools.public.save_deliverable_attachment_tool.AttachmentAssetStore",
        lambda root_dir=None: store if root_dir is None else AttachmentAssetStore(root_dir=root_dir),
    )
    monkeypatch.setattr(
        "runtime.tools.public.save_deliverable_attachment_tool.resolve_workspace_path",
        lambda raw: tmp_path / "report.txt",
    )
    report = tmp_path / "report.txt"
    report.write_text("hello deliverable\n", encoding="utf-8")

    spec = save_deliverable_attachment_tool()
    out = spec.handler({"path": "report.txt"})
    assert out.get("ok") is True
    assert out.get("deliverable") is True
    assert out.get("attachment_id")
    assert out.get("mime") == "text/plain"
    blob, meta = store.load_bytes(str(out["attachment_id"]))
    assert blob is not None
    assert blob.decode("utf-8").replace("\r\n", "\n") == "hello deliverable\n"
    assert meta is not None


def test_save_deliverable_attachment_marks_existing_attachment_id(tmp_path, monkeypatch) -> None:
    from svc.files.attachment_assets import AttachmentAssetStore

    store = AttachmentAssetStore(root_dir=tmp_path / "att")
    meta = store.save_bytes(b"png-bytes", filename="gen.png", mime="image/png")
    monkeypatch.setattr(
        "runtime.tools.public.save_deliverable_attachment_tool.AttachmentAssetStore",
        lambda root_dir=None: store if root_dir is None else AttachmentAssetStore(root_dir=root_dir),
    )

    spec = save_deliverable_attachment_tool()
    out = spec.handler({"attachment_id": meta.attachment_id})
    assert out.get("ok") is True
    assert out.get("deliverable") is True
    assert out.get("attachment_id") == meta.attachment_id
    assert out.get("mime") == "image/png"


def test_save_deliverable_attachment_requires_path_or_attachment_id() -> None:
    spec = save_deliverable_attachment_tool()
    out = spec.handler({})
    assert out.get("ok") is False
    assert out.get("error") == "path_or_attachment_id_required"
