from __future__ import annotations

from pathlib import Path

import pytest

from runtime.memory_stage import after_turn_memory, render_memory_context_block
from runtime.types import OclawMemoryContext
from svc.persistence.sqlite_store import SqliteStore


def test_render_memory_context_block_contains_sections() -> None:
    text = render_memory_context_block(
        OclawMemoryContext(
            short_term=("user prefers concise summary",),
            semantic_hits=({"content": "meeting summary style: bullets only", "score": 0.77},),
        )
    )
    assert "[short_term_digest]" in text
    assert "[semantic_memory_hits]" in text
    assert "0.7700" in text


def test_after_turn_memory_invokes_maybe_write_turn_memory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    def _fake_maybe_write(store: SqliteStore, **kwargs: object) -> dict:
        calls.append({"store": store, **kwargs})
        return {"ok": True, "written": 0, "reason": "stub"}

    monkeypatch.setattr("runtime.orchestration.memory.maybe_write_turn_memory", _fake_maybe_write)

    store = SqliteStore(str(tmp_path / "m.sqlite"))
    store.create_session("s1")
    after_turn_memory(
        store=store,
        session_id="s1",
        tenant_id="t1",
        user_id="u1",
        user_text="hello",
        assistant_text="world",
    )
    assert len(calls) == 1
    assert calls[0]["tenant_id"] == "t1"
    assert calls[0]["user_id"] == "u1"

