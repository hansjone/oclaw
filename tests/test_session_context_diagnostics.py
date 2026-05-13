from __future__ import annotations

from svc.persistence.sqlite_store import SqliteStore
from runtime.chat.session_context_diagnostics import compute_session_context_stats


def test_compute_session_context_stats_detects_empty_assistant(tmp_path) -> None:  # noqa: ANN001
    db = tmp_path / "ops.sqlite"
    store = SqliteStore(str(db))
    sess = store.create_session("t")
    store.add_message(session_id=sess.id, role="user", content="hi", event_type="user_text")
    store.add_message(session_id=sess.id, role="assistant", content="", event_type="assistant_text")
    store.add_message(session_id=sess.id, role="tool", content="x" * 50, event_type="tool_result")
    store.add_message(session_id=sess.id, role="assistant", content="ok", event_type="assistant_text")

    st = compute_session_context_stats(store=store, session_id=sess.id, sample_n=50, last_n=10)
    assert st.session_id == sess.id
    assert st.total_messages >= 4
    assert st.sampled_messages >= 4
    assert st.empty_assistant_text_in_sampled == 1
    assert len(st.empty_assistant_text_ids) == 1
    assert st.last_n_total_chars >= 52
    assert st.last_n_max_tool_chars == 50

