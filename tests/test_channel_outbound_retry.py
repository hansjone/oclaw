from __future__ import annotations

from svc.persistence.sqlite_store import SqliteStore


def _row(store: SqliteStore, msg_id: str) -> dict:
    with store._connect() as conn:  # noqa: SLF001 - test introspection
        got = conn.execute(
            """
            SELECT id, status, error, send_attempts, next_attempt_at, last_attempt_at
            FROM channel_outbound_message
            WHERE id = ?
            """,
            (msg_id,),
        ).fetchone()
    assert got is not None
    return dict(got)


def test_channel_outbound_retry_transitions(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    msg_id = store.enqueue_channel_outbound_message(
        channel="whatsapp",
        account_id="wa-default",
        chat_id="8615601877957@s.whatsapp.net",
        text="hello",
    )

    assert store.ack_channel_outbound_message(message_id=msg_id, ok=False, error="net down") is True
    first = _row(store, msg_id)
    assert first["status"] == "pending"
    assert int(first["send_attempts"] or 0) == 1
    assert str(first["next_attempt_at"] or "").strip()

    assert store.ack_channel_outbound_message(message_id=msg_id, ok=False, error="still down") is True
    assert store.ack_channel_outbound_message(message_id=msg_id, ok=False, error="final fail") is True
    final = _row(store, msg_id)
    assert final["status"] == "failed"
    assert int(final["send_attempts"] or 0) == 3
    assert not str(final["next_attempt_at"] or "").strip()


def test_channel_outbound_retry_success_clears_schedule(tmp_path) -> None:
    store = SqliteStore(str(tmp_path / "ops.sqlite"))
    msg_id = store.enqueue_channel_outbound_message(
        channel="whatsapp",
        account_id="wa-default",
        chat_id="8615601877957@s.whatsapp.net",
        text="hello",
    )
    assert store.ack_channel_outbound_message(message_id=msg_id, ok=False, error="temp") is True
    assert store.ack_channel_outbound_message(message_id=msg_id, ok=True, stanza_id="stanza-1") is True
    row = _row(store, msg_id)
    assert row["status"] == "sent"
    assert int(row["send_attempts"] or 0) == 2
    assert not str(row["next_attempt_at"] or "").strip()
