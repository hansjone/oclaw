from __future__ import annotations

import base64
from pathlib import Path

import pytest

from oclaw.openclaw_runtime.relay_pointer import (
    RelayPointerError,
    build_pointer_uri,
    decode_base64_payload,
    normalize_rel_path,
    parse_pointer_uri,
    safe_join_under_root,
    sha256_hex,
    validate_file_name,
)


def test_validate_file_name_rejects_path_injection() -> None:
    with pytest.raises(RelayPointerError):
        validate_file_name("../a.txt")
    with pytest.raises(RelayPointerError):
        validate_file_name("a/b.txt")


def test_normalize_rel_path_rejects_traversal() -> None:
    with pytest.raises(RelayPointerError):
        normalize_rel_path("../../etc/passwd")


def test_safe_join_under_root_stays_inside(tmp_path: Path) -> None:
    p = safe_join_under_root(tmp_path, "a/b.txt")
    assert str(p).startswith(str(tmp_path.resolve()))


def test_decode_base64_payload_respects_size_limit() -> None:
    raw = base64.b64encode(b"hello").decode("ascii")
    assert decode_base64_payload(raw, max_bytes=5) == b"hello"
    with pytest.raises(RelayPointerError):
        decode_base64_payload(raw, max_bytes=4)


def test_pointer_uri_build_and_parse_roundtrip() -> None:
    uri = build_pointer_uri("scope_1", "abcdef123456")
    assert uri == "relay://attachments/scope_1/abcdef123456"
    scope, file_id = parse_pointer_uri(uri)
    assert scope == "scope_1"
    assert file_id == "abcdef123456"


def test_sha256_hex_is_stable() -> None:
    assert sha256_hex(b"abc") == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
