from __future__ import annotations

from oclaw.openclaw_runtime.relay_pointer import build_acp_relay_result, validate_relay_share_envelope


def test_validate_relay_share_envelope_ok() -> None:
    ok, err, env = validate_relay_share_envelope(
        {
            "schema_version": "v1",
            "attachments": {
                "scope_id": "s1",
                "count": 1,
                "total_bytes": 8,
                "pointers": [
                    {
                        "schema_version": "v1",
                        "pointer_uri": "relay://attachments/s1/abcdef123456",
                        "rel_path": "attachments/a.txt",
                        "mime_type": "text/plain",
                        "bytes": 8,
                        "sha256": "f" * 64,
                        "source_agent": "generalist",
                    }
                ],
            },
        }
    )
    assert ok is True
    assert err == ""
    assert isinstance(env.get("attachments"), dict)


def test_validate_relay_share_envelope_bad_version() -> None:
    ok, err, env = validate_relay_share_envelope({"schema_version": "v2", "attachments": {}})
    assert ok is False
    assert err == "relay_envelope_unsupported_version"
    assert env == {}


def test_build_acp_relay_result_includes_ids_and_error() -> None:
    out = build_acp_relay_result(
        parent_run_id="parent-1",
        child_run_id="child-1",
        relay_envelope={"schema_version": "v2", "attachments": {}},
    )
    assert out["acp_parent_run_id"] == "parent-1"
    assert out["acp_child_run_id"] == "child-1"
    assert out["relay_ok"] is False
    assert out["relay_error_code"] == "relay_envelope_unsupported_version"
    assert out["relay_pointer_count"] == 0


def test_validate_relay_share_envelope_missing_attachments() -> None:
    ok, err, env = validate_relay_share_envelope({"schema_version": "v1"})
    assert ok is False
    assert err == "relay_envelope_invalid"
    assert env == {}
