from __future__ import annotations

from runtime.relay_pointer import build_manifest_from_attachment_refs
from runtime.types import RelayShareEnvelope, SharedAttachmentManifest, SharedFilePointer


def test_shared_pointer_roundtrip_with_extra_fields() -> None:
    raw = {
        "schema_version": "v1",
        "pointer_uri": "relay://attachments/scope-1/abcdef1234",
        "rel_path": "attachments/a.txt",
        "mime_type": "text/plain",
        "bytes": 12,
        "sha256": "x" * 64,
        "source_agent": "generalist",
        "created_at": "2026-01-01T00:00:00Z",
        "ttl_policy": "session",
        "custom_k": "custom_v",
    }
    p = SharedFilePointer.from_dict(raw)
    out = p.to_dict()
    assert out["pointer_uri"] == raw["pointer_uri"]
    assert out["ttl_policy"] == "session"
    assert out["custom_k"] == "custom_v"


def test_relay_share_envelope_roundtrip() -> None:
    p = SharedFilePointer(
        pointer_uri="relay://attachments/scope-2/abcdef1234",
        rel_path="attachments/x.bin",
        mime_type="application/octet-stream",
        bytes=7,
        sha256="f" * 64,
        source_agent="ops",
        ttl_policy="turn",
    )
    m = SharedAttachmentManifest(scope_id="scope-2", count=1, total_bytes=7, pointers=(p,))
    e = RelayShareEnvelope(schema_version="v1", trace_id="t1", run_id="r1", attempt_no=1, attachments=m)
    restored = RelayShareEnvelope.from_dict(e.to_dict())
    assert restored.schema_version == "v1"
    assert restored.trace_id == "t1"
    assert restored.attachments.scope_id == "scope-2"
    assert len(restored.attachments.pointers) == 1
    assert restored.attachments.pointers[0].pointer_uri.endswith("/abcdef1234")


def test_build_manifest_from_attachment_refs() -> None:
    manifest = build_manifest_from_attachment_refs(
        [
            {
                "type": "image_ref",
                "attachment_id": "abcdef123456",
                "name": "demo.png",
                "mime": "image/png",
                "bytes": 123,
            }
        ],
        scope_id="scope_a",
        source_agent="generalist",
    )
    assert manifest.scope_id == "scope_a"
    assert manifest.count == 1
    assert manifest.total_bytes == 123
    ptr = manifest.pointers[0]
    assert ptr.pointer_uri == "relay://attachments/scope_a/abcdef123456"
    assert ptr.extra.get("name") == "demo.png"
